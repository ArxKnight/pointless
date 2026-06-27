from datetime import datetime, timedelta
from collections import defaultdict

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CompatibilityRule, Participant, Quarter, QuarterParticipant, User, GivingPlan, AdminInvitation, AuditLog
from app.services.auth_service import hash_password
from app.services.participant_service import create_participant, bulk_create_participants
from app.services.participant_generator import GenerationSettings, generate_distribution, validate_distribution, PERMITTED_AMOUNTS
from app.api.v1.participants import list_participants
from app.api.v1.invitations import create_invitation, accept_invitation, list_invitations, revoke_invitation, public_invitation
from app.api.v1.users import update_admin, delete_admin
from app.api.v1.quarters import create_quarter, delete_quarter, list_quarters
from app.api.v1.audit import list_audit_logs
from app.api.v1.auth import login
from app.schemas.api import AdminInvitationCreate, AdminInvitationAccept, UserAdminUpdate, QuarterCreateIn, LoginIn


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


def admin_user(db, username="owner", super_admin=True):
    user = User(username=username, display_name="Owner", email=f"{username}@example.com", password_hash=hash_password("password123"), is_admin=True, is_super_admin=super_admin, is_active=True)
    db.add(user); db.commit(); db.refresh(user)
    return user


def add_complete_compatibility(db, names):
    participants = [create_participant(db, name) for name in names]
    db.flush()
    for a in participants:
        for b in participants:
            if a.id != b.id:
                db.add(CompatibilityRule(from_participant_id=a.id, to_participant_id=b.id, is_allowed=True))
    db.commit()
    return participants


def totals(plan):
    sent = defaultdict(int); received = defaultdict(int)
    for row in plan:
        sent[row["from_participant_id"]] += row["amount"]
        received[row["to_participant_id"]] += row["amount"]
    return sent, received


def test_bulk_created_participants_are_returned_by_standard_list_endpoint_immediately(db):
    owner = admin_user(db)
    result = bulk_create_participants(db, "Participant D\nParticipant A\n\nParticipant A\nParticipant F")
    db.commit()
    listed = list_participants(include_inactive=True, db=db, admin=owner)
    names = [p["display_name"] for p in listed]
    assert [p.display_name for p in result.created] == ["Participant D", "Participant A", "Participant F"]
    assert names == ["Participant A", "Participant D", "Participant F"]
    assert result.duplicates == ["Participant A"]
    assert result.ignored_blank_lines == 1


def test_generator_uses_only_permitted_fixed_amounts_and_never_45_for_50_total(db):
    participants = add_complete_compatibility(db, ["Participant D", "Participant A", "Participant E", "Participant B", "Participant G", "Participant H", "Participant C"])
    plan = generate_distribution(participants, db.query(CompatibilityRule).all(), settings=GenerationSettings(seed=42))
    sent, received = totals(plan)
    assert all(sent[p.id] == 50 for p in participants)
    assert all(received[p.id] == 50 for p in participants)
    assert all(row["amount"] in PERMITTED_AMOUNTS for row in plan)
    assert all(row["amount"] != 45 for row in plan)
    assert not any(row["amount"] in {5, 12, 17, 22, 35} for row in plan)
    assert any(len([r for r in plan if r["from_participant_id"] == p.id]) != len([r for r in plan if r["to_participant_id"] == p.id]) for p in participants)
    validate_distribution(plan, participants, db.query(CompatibilityRule).all(), settings=GenerationSettings())


def test_generator_seed_is_deterministic_and_different_seeds_can_vary(db):
    participants = add_complete_compatibility(db, ["Participant D", "Participant A", "Participant E", "Participant B", "Participant G", "Participant H"])
    rules = db.query(CompatibilityRule).all()
    a = generate_distribution(participants, rules, settings=GenerationSettings(seed=1))
    b = generate_distribution(participants, rules, settings=GenerationSettings(seed=1))
    c = generate_distribution(participants, rules, settings=GenerationSettings(seed=2))
    assert a == b
    assert a != c


def test_invalid_amounts_and_duplicate_edges_are_rejected(db):
    participants = add_complete_compatibility(db, ["Participant A", "Participant B", "Participant C"])
    participant_a, participant_b, participant_c = participants
    with pytest.raises(ValueError, match="permitted"):
        validate_distribution([
            {"from_participant_id": participant_a.id, "to_participant_id": participant_b.id, "amount": 35},
            {"from_participant_id": participant_b.id, "to_participant_id": participant_c.id, "amount": 50},
            {"from_participant_id": participant_c.id, "to_participant_id": participant_a.id, "amount": 50},
        ], participants, db.query(CompatibilityRule).all())


def test_main_admin_invitation_single_use_and_revocable(db):
    owner = admin_user(db)
    created = create_invitation(AdminInvitationCreate(invitee_name="Participant A", invitee_email="user_a@example.com", expires_in_hours=24), db, owner)
    assert created["invitation_url"].startswith("/admin-invite/")
    listed = list_invitations(db, owner)[0]
    assert "token" not in listed
    assert listed["invitation_url"].startswith("/admin-invite/")
    assert created["token"] in listed["invitation_url"]
    token = created["token"]
    public = public_invitation(token, db)
    assert public["invitee_name"] == "Participant A"
    accepted = accept_invitation(token, AdminInvitationAccept(username="participant_a", email="user_a@example.com", password="password123", password_confirm="password123"), db)
    assert accepted["user"]["username"] == "participant_a"
    assert accepted["user"]["display_name"] == "participant_a"
    with pytest.raises(HTTPException) as reused:
        accept_invitation(token, AdminInvitationAccept(display_name="User A2", username="participant_a2", email="user_a2@example.com", password="password123", password_confirm="password123"), db)
    assert reused.value.status_code == 400

    second = create_invitation(AdminInvitationCreate(invitee_name="Participant E", expires_in_hours=24), db, owner)
    revoke_invitation(second["id"], db, owner)
    with pytest.raises(HTTPException) as revoked:
        public_invitation(second["token"], db)
    assert revoked.value.status_code == 400


def test_admin_invitation_allows_blank_optional_email_and_returns_one_time_url(db):
    owner = admin_user(db)

    created = create_invitation(AdminInvitationCreate(invitee_name="new_admin", invitee_email="", expires_in_hours=168), db, owner)

    assert created["invitee_name"] == "new_admin"
    assert created["invitee_email"] is None
    assert created["invitation_url"].startswith("/admin-invite/")
    assert created["token"] in created["invitation_url"]
    listed = list_invitations(db, owner)[0]
    assert listed["invitee_email"] is None
    assert "token" not in listed
    assert listed["invitation_url"].startswith("/admin-invite/")


def test_last_active_super_admin_cannot_be_removed(db):
    owner = admin_user(db)
    with pytest.raises(HTTPException):
        update_admin(owner.id, UserAdminUpdate(is_active=False), db, owner)
    with pytest.raises(HTTPException):
        delete_admin(owner.id, db, owner)

    other = admin_user(db, "other", super_admin=True)
    updated = update_admin(other.id, UserAdminUpdate(is_active=False), db, owner)
    assert updated["is_active"] is False


def test_installer_admin_cannot_be_deleted_even_when_another_super_admin_exists(db):
    owner = admin_user(db)
    other = admin_user(db, "other", super_admin=True)

    with pytest.raises(HTTPException) as blocked:
        delete_admin(owner.id, db, other)

    assert blocked.value.status_code == 400
    assert "cannot be deleted" in blocked.value.detail
    db.refresh(owner)
    assert owner.is_active is True


def test_admin_login_writes_audit_session_entry(db):
    owner = admin_user(db, "owner")
    request = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 12345), "server": ("testserver", 80), "scheme": "http"})
    response = Response()

    result = login(LoginIn(username="owner", password="password123"), request, response, db)

    assert result["user"].username == "owner"
    rows = list_audit_logs(limit=20, actor_user_id=owner.id, db=db, admin=owner)
    assert rows[0]["event_type"] == "admin_login"
    assert rows[0]["ip_address"] == "127.0.0.1"


def test_audit_log_can_filter_by_admin_actor(db):
    owner = admin_user(db, "owner")
    other = admin_user(db, "other")
    db.add(AuditLog(event_type="admin_login", actor_user_id=owner.id, actor_username=owner.username, message="Owner logged in"))
    db.add(AuditLog(event_type="admin_login", actor_user_id=other.id, actor_username=other.username, message="Other logged in"))
    db.add(AuditLog(event_type="public_link_viewed", actor_user_id=None, actor_username=None, message="Public link viewed"))
    db.commit()

    rows = list_audit_logs(limit=20, actor_user_id=owner.id, db=db, admin=owner)

    assert [row["actor_username"] for row in rows] == ["owner"]
    assert rows[0]["message"] == "Owner logged in"


def test_quarter_list_excludes_past_and_duplicate_create_requires_delete(db):
    owner = admin_user(db)
    past = Quarter(year=2025, quarter=1, label="Q1 2025", status="published", is_active=False, is_completed=False)
    current = Quarter(year=2026, quarter=2, label="Q2 2026", status="draft", is_active=False, is_completed=False)
    future = Quarter(year=2027, quarter=1, label="Q1 2027", status="draft", is_active=False, is_completed=False)
    db.add_all([past, current, future]); db.commit()

    labels = [q.label for q in list_quarters(False, db, owner)]
    assert "Q1 2025" not in labels
    assert "Q2 2026" in labels
    assert "Q1 2027" in labels

    with pytest.raises(HTTPException) as duplicate:
        create_quarter(QuarterCreateIn(year=2027, quarter=1), db, owner)
    assert duplicate.value.status_code == 409
    assert "already made" in duplicate.value.detail

    delete_quarter(future.id, db, owner)
    replacement = create_quarter(QuarterCreateIn(year=2027, quarter=1), db, owner)
    assert replacement.label == "Q1 2027"
