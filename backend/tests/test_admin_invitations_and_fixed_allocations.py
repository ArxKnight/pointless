from datetime import datetime, timedelta
from collections import defaultdict

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CompatibilityRule, Participant, Quarter, QuarterParticipant, User, GivingPlan, AdminInvitation
from app.services.auth_service import hash_password
from app.services.participant_service import create_participant, bulk_create_participants
from app.services.participant_generator import GenerationSettings, generate_distribution, validate_distribution, PERMITTED_AMOUNTS
from app.api.v1.participants import list_participants
from app.api.v1.invitations import create_invitation, accept_invitation, list_invitations, revoke_invitation, public_invitation
from app.api.v1.users import update_admin, delete_admin
from app.schemas.api import AdminInvitationCreate, AdminInvitationAccept, UserAdminUpdate


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
    result = bulk_create_participants(db, "Adam\nAlex\n\nAlex\nJohn Smith")
    db.commit()
    listed = list_participants(include_inactive=True, db=db, admin=owner)
    names = [p["display_name"] for p in listed]
    assert [p.display_name for p in result.created] == ["Adam", "Alex", "John Smith"]
    assert names == ["Adam", "Alex", "John Smith"]
    assert result.duplicates == ["Alex"]
    assert result.ignored_blank_lines == 1


def test_generator_uses_only_permitted_fixed_amounts_and_never_45_for_50_total(db):
    participants = add_complete_compatibility(db, ["Adam", "Alex", "Billy", "Charlie", "John", "Marijus", "Uzzy"])
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
    participants = add_complete_compatibility(db, ["Adam", "Alex", "Billy", "Charlie", "John", "Marijus"])
    rules = db.query(CompatibilityRule).all()
    a = generate_distribution(participants, rules, settings=GenerationSettings(seed=1))
    b = generate_distribution(participants, rules, settings=GenerationSettings(seed=1))
    c = generate_distribution(participants, rules, settings=GenerationSettings(seed=2))
    assert a == b
    assert a != c


def test_invalid_amounts_and_duplicate_edges_are_rejected(db):
    participants = add_complete_compatibility(db, ["Alex", "Charlie", "Uzzy"])
    alex, charlie, uzzy = participants
    with pytest.raises(ValueError, match="permitted"):
        validate_distribution([
            {"from_participant_id": alex.id, "to_participant_id": charlie.id, "amount": 35},
            {"from_participant_id": charlie.id, "to_participant_id": uzzy.id, "amount": 50},
            {"from_participant_id": uzzy.id, "to_participant_id": alex.id, "amount": 50},
        ], participants, db.query(CompatibilityRule).all())


def test_main_admin_invitation_single_use_and_revocable(db):
    owner = admin_user(db)
    created = create_invitation(AdminInvitationCreate(invitee_name="Alex", invitee_email="alex@example.com", expires_in_hours=24), db, owner)
    assert created["invitation_url"].startswith("/admin-invite/")
    assert "token" not in list_invitations(db, owner)[0]
    token = created["token"]
    public = public_invitation(token, db)
    assert public["invitee_name"] == "Alex"
    accepted = accept_invitation(token, AdminInvitationAccept(display_name="Alex", username="alex", email="alex@example.com", password="password123", password_confirm="password123"), db)
    assert accepted["user"]["username"] == "alex"
    with pytest.raises(HTTPException) as reused:
        accept_invitation(token, AdminInvitationAccept(display_name="Alex2", username="alex2", email="alex2@example.com", password="password123", password_confirm="password123"), db)
    assert reused.value.status_code == 400

    second = create_invitation(AdminInvitationCreate(invitee_name="Billy", expires_in_hours=24), db, owner)
    revoke_invitation(second["id"], db, owner)
    with pytest.raises(HTTPException) as revoked:
        public_invitation(second["token"], db)
    assert revoked.value.status_code == 400


def test_last_active_super_admin_cannot_be_removed(db):
    owner = admin_user(db)
    with pytest.raises(HTTPException):
        update_admin(owner.id, UserAdminUpdate(is_active=False), db, owner)
    with pytest.raises(HTTPException):
        delete_admin(owner.id, db, owner)

    other = admin_user(db, "other", super_admin=True)
    updated = update_admin(other.id, UserAdminUpdate(is_active=False), db, owner)
    assert updated["is_active"] is False
