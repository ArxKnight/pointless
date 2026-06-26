from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app.models import DepartmentMember, GivingPlan, Quarter, Team, TeamGroup, User
from app.schemas.api import TeamCreate, TeamDeleteIn, TeamGroupCreate, TeamGroupUpdate, TeamUpdate, UserTeamUpdate
from app.services.auth_service import hash_password, require_admin
from app.services.team_seed import ensure_initial_team_data
from app.api.v1.teams import create_group, create_team, delete_team, list_groups, list_teams, update_group, update_team, unassigned_users
from app.api.v1.users import set_user_team
from app.api.v1.quarters import overview_tree_payload


def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def make_user(username="participant_a", email="user_a@example.com", display_name="Participant A", admin=False, team_id=None):
    return User(username=username, email=email, display_name=display_name, password_hash=hash_password("password123"), is_admin=admin, is_active=True, team_id=team_id)


def test_seed_creates_initial_empty_team_groups_and_teams_without_users():
    db = session()
    ensure_initial_team_data(db)
    assert [g.name for g in db.query(TeamGroup).order_by(TeamGroup.display_order)] == ["Shift A + Shift B", "Shift C + Shift D", "Others"]
    assert [t.name for t in db.query(Team).order_by(Team.display_order)] == ["Shift A", "Shift B", "Shift C", "Shift D", "Others"]
    assert db.query(User).count() == 0


def test_create_edit_rename_group_and_team_and_duplicate_validation():
    db = session(); admin = make_user(admin=True); db.add(admin); db.commit()
    group = create_group(TeamGroupCreate(name="Support", description="", display_order=1, is_active=True), db, admin)
    team = create_team(TeamCreate(name="Network", description=None, colour="#123456", display_order=2, is_active=True, group_id=group["id"]), db, admin)
    renamed = update_team(team["id"], TeamUpdate(name="Network Ops"), db, admin)
    update_group(group["id"], TeamGroupUpdate(name="Support Group"), db, admin)
    assert renamed["name"] == "Network Ops"
    try:
        create_team(TeamCreate(name="Network Ops", colour="#654321", display_order=3, is_active=True, group_id=None), db, admin)
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Duplicate team name should fail")


def test_assign_move_remove_user_team_and_list_unassigned():
    db = session(); admin = make_user("admin", "admin@example.com", "Admin", True); user = make_user(); db.add_all([admin, user]); db.commit()
    a = Team(name="A", colour="#111111", display_order=1); b = Team(name="B", colour="#222222", display_order=2); db.add_all([a, b]); db.commit()
    assert user.id in [u.id for u in unassigned_users(db, admin)]
    moved = set_user_team(user.id, UserTeamUpdate(team_id=a.id), db, admin); assert moved["team_id"] == a.id
    moved = set_user_team(user.id, UserTeamUpdate(team_id=b.id), db, admin); assert moved["team_id"] == b.id
    moved = set_user_team(user.id, UserTeamUpdate(team_id=None), db, admin); assert moved["team_id"] is None


def test_delete_team_with_assigned_users_unassigns_or_moves_without_deleting_users():
    db = session(); admin = make_user("admin", "admin@example.com", "Admin", True); db.add(admin); db.commit()
    old = Team(name="Old", colour="#111111", display_order=1); new = Team(name="New", colour="#222222", display_order=2); db.add_all([old, new]); db.commit()
    u = make_user(team_id=old.id); db.add(u); db.commit()
    deleted = delete_team(old.id, TeamDeleteIn(move_users_to_team_id=None), db, admin)
    db.refresh(u)
    assert deleted["is_active"] is False and u.team_id is None and db.query(User).count() == 2
    u.team_id = new.id; db.commit()
    delete_team(new.id, TeamDeleteIn(move_users_to_team_id=None), db, admin)
    db.refresh(u); assert u.team_id is None


def test_empty_groups_and_inactive_groups_are_handled_in_lists():
    db = session(); admin = make_user(admin=True); db.add(admin); db.commit()
    empty = TeamGroup(name="Empty", display_order=1, is_active=True); inactive = TeamGroup(name="Inactive", display_order=2, is_active=False); db.add_all([empty, inactive]); db.commit()
    active = list_groups(False, db, admin); all_groups = list_groups(True, db, admin)
    assert [g["name"] for g in active] == ["Empty"]
    assert {g["name"] for g in all_groups} == {"Empty", "Inactive"}


def test_non_admin_dependency_rejects_team_management():
    user = make_user(admin=False)
    try:
        require_admin(user)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Non-admin should not pass require_admin")


def test_overview_tree_groups_api_data_cross_group_unassigned_and_cycles():
    db = session(); g1 = TeamGroup(name="G1", display_order=1); g2 = TeamGroup(name="G2", display_order=2); db.add_all([g1, g2]); db.flush()
    t1 = Team(name="T1", colour="#111111", display_order=1, group_id=g1.id); t2 = Team(name="T2", colour="#222222", display_order=2, group_id=g2.id); db.add_all([t1, t2]); db.flush()
    u1 = make_user("a", "a@example.com", "A", team_id=t1.id); u2 = make_user("b", "b@example.com", "B", team_id=t2.id); u3 = make_user("c", "c@example.com", "C", team_id=None); db.add_all([u1, u2, u3]); db.flush()
    m1 = DepartmentMember(display_name="A", email="a@example.com", active=True); m2 = DepartmentMember(display_name="B", email="b@example.com", active=True); m3 = DepartmentMember(display_name="C", email="c@example.com", active=True); db.add_all([m1, m2, m3]); db.flush()
    q = Quarter(year=2026, quarter=2, label="Q2 2026", is_active=True, is_completed=False); db.add(q); db.flush()
    db.add_all([GivingPlan(quarter_id=q.id, from_member_id=m1.id, to_member_id=m2.id, amount=20, acknowledged=False), GivingPlan(quarter_id=q.id, from_member_id=m2.id, to_member_id=m1.id, amount=10, acknowledged=False), GivingPlan(quarter_id=q.id, from_member_id=m3.id, to_member_id=m1.id, amount=5, acknowledged=False)])
    db.commit()
    payload = overview_tree_payload(db, q)
    assert {g["name"] for g in payload["team_groups"]} == {"G1", "G2"}
    by_name = {u["display_name"]: u for u in payload["users"]}
    assert by_name["A"]["team_name"] == "T1" and by_name["B"]["team_group_name"] == "G2"
    assert by_name["C"]["team_name"] is None and by_name["C"]["total_points_sent"] == 5
    assert len(payload["allocations"]) == 3
