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
from app.api.v1.quarters import cancel_generation, generate_activate_quarter, generation_status, start_generate_activate_quarter
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
    participant = create_participant(db, "Participant A")
    db.commit()

    assert participant.id is not None
    assert participant.display_name == "Participant A"
    assert participant.slug == "participant-a"
    assert participant.is_active is True
    assert db.query(User).count() == 0


def test_bulk_participant_import_trims_blanks_detects_duplicates_and_generates_unique_slugs(db):
    create_participant(db, "Participant A")
    db.commit()

    result = bulk_create_participants(db, " Participant D\nParticipant A\n\nParticipant F\nParticipant A\nParticipant F ")
    db.commit()

    created_names = [p.display_name for p in result.created]
    assert created_names == ["Participant D", "Participant F"]
    assert sorted(result.duplicates) == ["Participant A", "Participant A", "Participant F"]
    assert db.query(Participant).filter_by(slug="participant-d").one()
    assert db.query(Participant).filter_by(slug="participant-f").one()


def test_slug_generation_adds_numeric_suffix(db):
    create_participant(db, "Participant A")
    create_participant(db, "Participant A!")
    db.commit()

    assert slugify_name("Participant A", db) == "participant-a-3"


def test_current_published_quarter_query_is_mysql_compatible(db):
    sql = str(current_published_quarter_query(db).limit(1).statement.compile(dialect=mysql.dialect()))

    assert "NULLS LAST" not in sql.upper()
    assert "ORDER BY quarters.is_active DESC, quarters.published_at DESC, quarters.id DESC" in sql


def test_compatibility_blocks_self_and_disallowed_edges(db):
    participant_a, participant_b, participant_e = add_participants(db, ["Participant A", "Participant B", "Participant E"])
    db.add(CompatibilityRule(from_participant_id=participant_a.id, to_participant_id=participant_b.id, is_allowed=True))
    db.add(CompatibilityRule(from_participant_id=participant_a.id, to_participant_id=participant_e.id, is_allowed=False))
    db.commit()

    edges = build_allowed_edges([participant_a, participant_b, participant_e], db.query(CompatibilityRule).all(), default_allowed=False)
    assert (participant_a.id, participant_a.id) not in edges
    assert (participant_a.id, participant_b.id) in edges
    assert (participant_a.id, participant_e.id) not in edges


def test_feasibility_reports_participant_with_no_recipients(db):
    participant_a, participant_e = add_participants(db, ["Participant A", "Participant E"])
    db.add(CompatibilityRule(from_participant_id=participant_e.id, to_participant_id=participant_a.id, is_allowed=True))
    db.commit()

    result = validate_feasibility([participant_a, participant_e], db.query(CompatibilityRule).all(), default_allowed=False)
    assert result.valid is False
    assert any("Participant A has no eligible recipients" in error for error in result.errors)


def test_generate_activate_quarter_creates_published_plan_without_draft_state(db):
    admin = User(username="admin", display_name="Admin", email="admin@example.com", password_hash=hash_password("password"), is_admin=True, is_super_admin=True, is_active=True)
    db.add(admin)
    participants = add_participants(db, ["Participant D", "Participant A", "Participant B", "Participant G", "Participant H", "Participant C"])
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
        participants = add_participants(db, ["Participant D", "Participant A", "Participant B", "Participant G", "Participant H", "Participant C", "Participant E"])
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
    participants = add_participants(db, ["Participant D", "Participant A", "Participant B", "Participant G", "Participant H", "Participant C", "Participant E"])
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


def test_generation_status_and_cancel_reports_stuck_stage(db):
    admin = User(username="admin", display_name="Admin", email="admin@example.com", password_hash=hash_password("password"), is_admin=True, is_super_admin=True, is_active=True)
    db.add(admin)
    participants = add_participants(db, ["Participant D", "Participant A", "Participant B"])
    db.commit()

    data = QuarterGenerateActivateIn(year=2026, quarter=2, label="Q2 2026", participant_ids=[p.id for p in participants], seed=7)
    start_generate_activate_quarter(data, BackgroundTasks(), db, admin)
    q = db.query(Quarter).filter_by(year=2026, quarter=2).one()

    status = generation_status(q.id, db, admin)
    cancelled = cancel_generation(q.id, db, admin)
    status_after = generation_status(q.id, db, admin)

    assert status["status"] == "generating"
    assert status["logs"]
    assert cancelled["ok"] is True
    assert status_after["cancel_requested"] is True
    assert "stage" in cancelled


def test_generator_creates_compatible_exact_50_uneven_whole_number_plan(db):
    participants = add_participants(db, ["Participant D", "Participant A", "Participant B", "Participant G", "Participant H", "Participant C"])
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
    participants = add_participants(db, ["Participant A", "Participant B", "Participant C", "Participant H", "Participant G"])
    participant_a = participants[0]
    participant_e = create_participant(db, "Participant E")
    selected = participants + [participant_e]
    for a in selected:
        for b in selected:
            if a.id != b.id:
                allowed = not ({a.display_name, b.display_name} == {"Participant A", "Participant E"})
                db.add(CompatibilityRule(from_participant_id=a.id, to_participant_id=b.id, is_allowed=allowed))
    db.commit()

    plan = generate_distribution(selected, db.query(CompatibilityRule).all(), settings=GenerationSettings(seed=7))
    assert not any(r["from_participant_id"] == participant_a.id and r["to_participant_id"] == participant_e.id for r in plan)
    assert not any(r["from_participant_id"] == participant_e.id and r["to_participant_id"] == participant_a.id for r in plan)


def test_public_tree_only_returns_published_quarter(db):
    participant_a, participant_b = add_participants(db, ["Participant A", "Participant B"])
    draft = Quarter(year=2026, quarter=3, label="Q3 2026", status="draft", is_active=True, is_completed=False)
    published = Quarter(year=2026, quarter=2, label="Q2 2026", status="published", is_active=False, is_completed=False, published_at=datetime.utcnow())
    db.add_all([draft, published])
    db.flush()
    db.add_all([
        QuarterParticipant(quarter_id=published.id, participant_id=participant_a.id),
        QuarterParticipant(quarter_id=published.id, participant_id=participant_b.id),
        GivingPlan(quarter_id=published.id, from_participant_id=participant_a.id, to_participant_id=participant_b.id, amount=50),
        GivingPlan(quarter_id=published.id, from_participant_id=participant_b.id, to_participant_id=participant_a.id, amount=50),
        GivingPlan(quarter_id=draft.id, from_participant_id=participant_a.id, to_participant_id=participant_b.id, amount=25),
    ])
    db.commit()

    payload = public_tree_payload(db, "participant-a")
    assert payload["status"] == "ok"
    assert payload["quarter"]["label"] == "Q2 2026"
    assert payload["participant"]["display_name"] == "Participant A"
    assert payload["total_allocated"] == 50
    assert payload["allocations"] == [{"recipient_name": "Participant B", "amount": 50}]
    assert payload["incoming_allocations"] == [{"sender_name": "Participant B", "amount": 50}]
    assert payload["total_incoming"] == 50
    assert "id" not in payload["participant"]


def test_public_tree_unknown_slug(db):
    with pytest.raises(LookupError):
        public_tree_payload(db, "missing")


def test_public_tree_uses_active_published_quarter_even_when_status_is_legacy(db):
    participant_a, participant_b = add_participants(db, ["Participant A", "Participant B"])
    active = Quarter(year=2026, quarter=2, label="Q2 2026", status="draft", is_active=True, is_completed=False, published_at=datetime.utcnow())
    db.add(active)
    db.flush()
    db.add_all([
        QuarterParticipant(quarter_id=active.id, participant_id=participant_a.id),
        QuarterParticipant(quarter_id=active.id, participant_id=participant_b.id),
        GivingPlan(quarter_id=active.id, from_participant_id=participant_a.id, to_participant_id=participant_b.id, amount=50),
    ])
    db.commit()

    payload = public_tree_payload(db, "participant-a")

    assert payload["status"] == "ok"
    assert payload["quarter"]["label"] == "Q2 2026"
    assert payload["allocations"] == [{"recipient_name": "Participant B", "amount": 50}]


def test_public_tree_not_included_mentions_next_scheduled_quarter(db):
    participant_a, participant_b = add_participants(db, ["Participant A", "Participant B"])
    current = Quarter(year=2026, quarter=2, label="Q2 2026", status="published", is_active=True, is_completed=False, published_at=datetime.utcnow())
    next_q = Quarter(year=2026, quarter=3, label="Q3 2026", status="draft", is_active=False, is_completed=False)
    db.add_all([current, next_q])
    db.flush()
    db.add(QuarterParticipant(quarter_id=current.id, participant_id=participant_b.id))
    db.add(QuarterParticipant(quarter_id=next_q.id, participant_id=participant_a.id))
    db.commit()

    payload = public_tree_payload(db, "participant-a")

    assert payload["status"] == "not_included"
    assert payload["next_quarter"]["label"] == "Q3 2026"
    assert "next scheduled for Q3 2026" in payload["message"]


def test_future_published_quarter_waits_until_calendar_quarter_is_live(db, monkeypatch):
    monkeypatch.setattr(quarter_lookup, "current_calendar_quarter", lambda now=None: (2026, 2))
    participant_a, participant_b = add_participants(db, ["Participant A", "Participant B"])
    q2 = Quarter(year=2026, quarter=2, label="Q2 2026", status="published", is_active=True, is_completed=False, published_at=datetime.utcnow())
    q3 = Quarter(year=2026, quarter=3, label="Q3 2026", status="published", is_active=True, is_completed=False, published_at=datetime.utcnow())
    db.add_all([q2, q3])
    db.flush()
    for q in (q2, q3):
        db.add_all([
            QuarterParticipant(quarter_id=q.id, participant_id=participant_a.id),
            QuarterParticipant(quarter_id=q.id, participant_id=participant_b.id),
            GivingPlan(quarter_id=q.id, from_participant_id=participant_a.id, to_participant_id=participant_b.id, amount=50),
        ])
    db.commit()

    assert current_published_quarter(db).id == q2.id
    payload = public_tree_payload(db, "participant-a")
    assert payload["status"] == "ok"
    assert payload["quarter"]["label"] == "Q2 2026"
