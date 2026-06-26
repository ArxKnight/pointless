from collections import defaultdict
from datetime import datetime

import pytest
from starlette.background import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CompatibilityRule, GivingPlan, Participant, Quarter, QuarterParticipant, User
from app.services.auth_service import hash_password
from app.services.participant_service import bulk_create_participants, create_participant, slugify_name
from app.services import quarter_lookup
from app.services.quarter_lookup import current_published_quarter, current_published_quarter_query
from app.services.participant_generator import (
    GenerationSettings,
    build_allowed_edges,
    generate_distribution,
    validate_distribution,
    validate_feasibility,
)
from app.api.v1.public import public_tree_payload
from app.api.v1.quarters import generate_activate_quarter, start_generate_activate_quarter
from app.schemas.api import QuarterGenerateActivateIn


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def add_participants(db, names):
    return [create_participant(db, name) for name in names]


def totals(plan):
    sent = defaultdict(int)
    received = defaultdict(int)
    for row in plan:
        sent[row["from_participant_id"]] += row["amount"]
        received[row["to_participant_id"]] += row["amount"]
    return sent, received


def test_participants_do_not_require_login_account(db):
    participant = create_participant(db, "Alex")
    db.commit()

    assert participant.id is not None
    assert participant.display_name == "Alex"
    assert participant.slug == "alex"
    assert participant.is_active is True
    assert db.query(User).count() == 0


def test_bulk_participant_import_trims_blanks_detects_duplicates_and_generates_unique_slugs(db):
    create_participant(db, "Alex")
    db.commit()

    result = bulk_create_participants(db, " Adam\nAlex\n\nJohn Smith\nAlex\nJohn Smith ")
    db.commit()

    created_names = [p.display_name for p in result.created]
    assert created_names == ["Adam", "John Smith"]
    assert sorted(result.duplicates) == ["Alex", "Alex", "John Smith"]
    assert db.query(Participant).filter_by(slug="adam").one()
    assert db.query(Participant).filter_by(slug="john-smith").one()


def test_slug_generation_adds_numeric_suffix(db):
    create_participant(db, "Alex")
    create_participant(db, "Alex!")
    db.commit()

    assert slugify_name("Alex", db) == "alex-3"


def test_current_published_quarter_query_is_mysql_compatible(db):
    sql = str(current_published_quarter_query(db).limit(1).statement.compile(dialect=mysql.dialect()))

    assert "NULLS LAST" not in sql.upper()
    assert "ORDER BY quarters.is_active DESC, quarters.published_at DESC, quarters.id DESC" in sql


def test_compatibility_blocks_self_and_disallowed_edges(db):
    alex, charlie, billy = add_participants(db, ["Alex", "Charlie", "Billy"])
    db.add(CompatibilityRule(from_participant_id=alex.id, to_participant_id=charlie.id, is_allowed=True))
    db.add(CompatibilityRule(from_participant_id=alex.id, to_participant_id=billy.id, is_allowed=False))
    db.commit()

    edges = build_allowed_edges([alex, charlie, billy], db.query(CompatibilityRule).all(), default_allowed=False)
    assert (alex.id, alex.id) not in edges
    assert (alex.id, charlie.id) in edges
    assert (alex.id, billy.id) not in edges


def test_feasibility_reports_participant_with_no_recipients(db):
    alex, billy = add_participants(db, ["Alex", "Billy"])
    db.add(CompatibilityRule(from_participant_id=billy.id, to_participant_id=alex.id, is_allowed=True))
    db.commit()

    result = validate_feasibility([alex, billy], db.query(CompatibilityRule).all(), default_allowed=False)
    assert result.valid is False
    assert any("Alex has no eligible recipients" in error for error in result.errors)


def test_generate_activate_quarter_creates_published_plan_without_draft_state(db):
    admin = User(username="admin", display_name="Admin", email="admin@example.com", password_hash=hash_password("password"), is_admin=True, is_super_admin=True, is_active=True)
    db.add(admin)
    participants = add_participants(db, ["Adam", "Alex", "Charlie", "John", "Marijus", "Uzzy"])
    for a in participants:
        for b in participants:
            if a.id != b.id:
                db.add(CompatibilityRule(from_participant_id=a.id, to_participant_id=b.id, is_allowed=True))
    db.commit()

    result = generate_activate_quarter(QuarterGenerateActivateIn(year=2026, quarter=4, label="Q4 2026", participant_ids=[p.id for p in participants], seed=7), db, admin)
    q = db.query(Quarter).filter_by(year=2026, quarter=4).one()

    assert q.status == "published"
    assert q.status != "draft"
    assert len(result["plans"]) > 0
    assert db.query(QuarterParticipant).filter_by(quarter_id=q.id).count() == len(participants)
    assert db.query(GivingPlan).filter_by(quarter_id=q.id).count() == len(result["plans"])


def test_generate_activate_flushes_selected_participants_when_session_autoflush_is_disabled():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    db = Session()
    try:
        admin = User(username="admin", display_name="Admin", email="admin@example.com", password_hash=hash_password("password"), is_admin=True, is_super_admin=True, is_active=True)
        db.add(admin)
        participants = add_participants(db, ["Adam", "Alex", "Charlie", "John", "Marijus", "Uzzy", "Billy"])
        for a in participants:
            for b in participants:
                if a.id != b.id:
                    db.add(CompatibilityRule(from_participant_id=a.id, to_participant_id=b.id, is_allowed=True))
        db.commit()

        result = generate_activate_quarter(QuarterGenerateActivateIn(year=2026, quarter=3, label="Q3 2026", participant_ids=[p.id for p in participants], seed=7), db, admin)
        q = db.query(Quarter).filter_by(year=2026, quarter=3).one()

        assert q.status == "published"
        assert db.query(QuarterParticipant).filter_by(quarter_id=q.id).count() == len(participants)
        assert len(result["plans"]) > 0
    finally:
        db.close()


def test_generate_activate_route_queues_background_work_and_reuses_generating_quarter(db):
    admin = User(username="admin", display_name="Admin", email="admin@example.com", password_hash=hash_password("password"), is_admin=True, is_super_admin=True, is_active=True)
    db.add(admin)
    participants = add_participants(db, ["Adam", "Alex", "Charlie", "John", "Marijus", "Uzzy", "Billy"])
    db.commit()

    tasks = BackgroundTasks()
    data = QuarterGenerateActivateIn(year=2026, quarter=3, label="Q3 2026", participant_ids=[p.id for p in participants], seed=7)
    first = start_generate_activate_quarter(data, tasks, db, admin)
    second = start_generate_activate_quarter(data, BackgroundTasks(), db, admin)
    q = db.query(Quarter).filter_by(year=2026, quarter=3).one()

    assert q.status == "generating"
    assert first["validation"]["pending"] is True
    assert second["validation"]["pending"] is True
    assert len(tasks.tasks) == 1
    assert db.query(QuarterParticipant).filter_by(quarter_id=q.id).count() == len(participants)


def test_generator_creates_compatible_exact_50_uneven_whole_number_plan(db):
    participants = add_participants(db, ["Adam", "Alex", "Charlie", "John", "Marijus", "Uzzy"])
    for a in participants:
        for b in participants:
            if a.id != b.id:
                db.add(CompatibilityRule(from_participant_id=a.id, to_participant_id=b.id, is_allowed=True))
    db.commit()

    settings = GenerationSettings(min_amount=5, max_amount=25, preferred_min_recipients=2, preferred_max_recipients=5, seed=4)
    plan = generate_distribution(participants, db.query(CompatibilityRule).all(), settings=settings)
    sent, received = totals(plan)

    assert all(sent[p.id] == 50 for p in participants)
    assert all(received[p.id] == 50 for p in participants)
    assert all(row["amount"] > 0 and row["amount"] == int(row["amount"]) for row in plan)
    assert all(row["amount"] <= 25 for row in plan)
    assert all(row["from_participant_id"] != row["to_participant_id"] for row in plan)
    assert any(len({r["amount"] for r in plan if r["from_participant_id"] == p.id}) > 1 for p in participants)
    validate_distribution(plan, participants, db.query(CompatibilityRule).all(), settings=settings)


def test_generator_never_uses_blocked_pair(db):
    participants = add_participants(db, ["Alex", "Charlie", "Uzzy", "Marijus", "John"])
    alex = participants[0]
    billy = create_participant(db, "Billy")
    selected = participants + [billy]
    for a in selected:
        for b in selected:
            if a.id != b.id:
                allowed = not ({a.display_name, b.display_name} == {"Alex", "Billy"})
                db.add(CompatibilityRule(from_participant_id=a.id, to_participant_id=b.id, is_allowed=allowed))
    db.commit()

    plan = generate_distribution(selected, db.query(CompatibilityRule).all(), settings=GenerationSettings(seed=7))
    assert not any(r["from_participant_id"] == alex.id and r["to_participant_id"] == billy.id for r in plan)
    assert not any(r["from_participant_id"] == billy.id and r["to_participant_id"] == alex.id for r in plan)


def test_public_tree_only_returns_published_quarter(db):
    alex, charlie = add_participants(db, ["Alex", "Charlie"])
    draft = Quarter(year=2026, quarter=3, label="Q3 2026", status="draft", is_active=True, is_completed=False)
    published = Quarter(year=2026, quarter=2, label="Q2 2026", status="published", is_active=False, is_completed=False, published_at=datetime.utcnow())
    db.add_all([draft, published])
    db.flush()
    db.add_all([
        QuarterParticipant(quarter_id=published.id, participant_id=alex.id),
        QuarterParticipant(quarter_id=published.id, participant_id=charlie.id),
        GivingPlan(quarter_id=published.id, from_participant_id=alex.id, to_participant_id=charlie.id, amount=50),
        GivingPlan(quarter_id=published.id, from_participant_id=charlie.id, to_participant_id=alex.id, amount=50),
        GivingPlan(quarter_id=draft.id, from_participant_id=alex.id, to_participant_id=charlie.id, amount=25),
    ])
    db.commit()

    payload = public_tree_payload(db, "alex")
    assert payload["status"] == "ok"
    assert payload["quarter"]["label"] == "Q2 2026"
    assert payload["participant"]["display_name"] == "Alex"
    assert payload["total_allocated"] == 50
    assert payload["allocations"] == [{"recipient_name": "Charlie", "amount": 50}]
    assert payload["incoming_allocations"] == [{"sender_name": "Charlie", "amount": 50}]
    assert payload["total_incoming"] == 50
    assert "id" not in payload["participant"]


def test_public_tree_unknown_slug(db):
    with pytest.raises(LookupError):
        public_tree_payload(db, "missing")


def test_public_tree_uses_active_published_quarter_even_when_status_is_legacy(db):
    alex, charlie = add_participants(db, ["Alex", "Charlie"])
    active = Quarter(year=2026, quarter=2, label="Q2 2026", status="draft", is_active=True, is_completed=False, published_at=datetime.utcnow())
    db.add(active)
    db.flush()
    db.add_all([
        QuarterParticipant(quarter_id=active.id, participant_id=alex.id),
        QuarterParticipant(quarter_id=active.id, participant_id=charlie.id),
        GivingPlan(quarter_id=active.id, from_participant_id=alex.id, to_participant_id=charlie.id, amount=50),
    ])
    db.commit()

    payload = public_tree_payload(db, "alex")

    assert payload["status"] == "ok"
    assert payload["quarter"]["label"] == "Q2 2026"
    assert payload["allocations"] == [{"recipient_name": "Charlie", "amount": 50}]


def test_public_tree_not_included_mentions_next_scheduled_quarter(db):
    alex, charlie = add_participants(db, ["Alex", "Charlie"])
    current = Quarter(year=2026, quarter=2, label="Q2 2026", status="published", is_active=True, is_completed=False, published_at=datetime.utcnow())
    next_q = Quarter(year=2026, quarter=3, label="Q3 2026", status="draft", is_active=False, is_completed=False)
    db.add_all([current, next_q])
    db.flush()
    db.add(QuarterParticipant(quarter_id=current.id, participant_id=charlie.id))
    db.add(QuarterParticipant(quarter_id=next_q.id, participant_id=alex.id))
    db.commit()

    payload = public_tree_payload(db, "alex")

    assert payload["status"] == "not_included"
    assert payload["next_quarter"]["label"] == "Q3 2026"
    assert "next scheduled for Q3 2026" in payload["message"]


def test_future_published_quarter_waits_until_calendar_quarter_is_live(db, monkeypatch):
    monkeypatch.setattr(quarter_lookup, "current_calendar_quarter", lambda now=None: (2026, 2))
    alex, charlie = add_participants(db, ["Alex", "Charlie"])
    q2 = Quarter(year=2026, quarter=2, label="Q2 2026", status="published", is_active=True, is_completed=False, published_at=datetime.utcnow())
    q3 = Quarter(year=2026, quarter=3, label="Q3 2026", status="published", is_active=True, is_completed=False, published_at=datetime.utcnow())
    db.add_all([q2, q3])
    db.flush()
    for q in (q2, q3):
        db.add_all([
            QuarterParticipant(quarter_id=q.id, participant_id=alex.id),
            QuarterParticipant(quarter_id=q.id, participant_id=charlie.id),
            GivingPlan(quarter_id=q.id, from_participant_id=alex.id, to_participant_id=charlie.id, amount=50),
        ])
    db.commit()

    assert current_published_quarter(db).id == q2.id
    payload = public_tree_payload(db, "alex")
    assert payload["status"] == "ok"
    assert payload["quarter"]["label"] == "Q2 2026"
