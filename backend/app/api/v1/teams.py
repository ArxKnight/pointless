from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Team, TeamGroup, User
from app.schemas.api import (
    TeamCreate,
    TeamDeleteIn,
    TeamGroupCreate,
    TeamGroupOut,
    TeamGroupUpdate,
    TeamMemberUserOut,
    TeamOut,
    TeamUpdate,
)
from app.services.auth_service import get_current_user, require_admin

router = APIRouter(prefix="/teams", tags=["teams"])


def _group_or_404(db: Session, group_id: int | None):
    if group_id is None:
        return None
    group = db.get(TeamGroup, group_id)
    if not group:
        raise HTTPException(404, "Team group not found")
    return group


def _team_or_404(db: Session, team_id: int):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    return team


def _ensure_unique_team_name(db: Session, name: str, team_id: int | None = None):
    q = db.query(Team).filter(func.lower(Team.name) == name.lower())
    if team_id is not None:
        q = q.filter(Team.id != team_id)
    if q.first():
        raise HTTPException(409, "Team name already exists")


def _ensure_unique_group_name(db: Session, name: str, group_id: int | None = None):
    q = db.query(TeamGroup).filter(func.lower(TeamGroup.name) == name.lower())
    if group_id is not None:
        q = q.filter(TeamGroup.id != group_id)
    if q.first():
        raise HTTPException(409, "Team group name already exists")


def team_out(db: Session, team: Team) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "colour": team.colour,
        "display_order": team.display_order,
        "is_active": team.is_active,
        "group_id": team.group_id if team.group and team.group.is_active else None,
        "group_name": team.group.name if team.group and team.group.is_active else None,
        "created_at": team.created_at,
        "updated_at": team.updated_at,
        "user_count": db.query(User).filter(User.team_id == team.id).count(),
    }


def group_out(db: Session, group: TeamGroup) -> dict:
    teams = sorted(group.teams, key=lambda t: (t.display_order, t.name.lower()))
    active_teams = [t for t in teams if t.is_active]
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "display_order": group.display_order,
        "is_active": group.is_active,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
        "team_count": len(active_teams),
        "user_count": db.query(User).join(Team, User.team_id == Team.id).filter(Team.group_id == group.id, Team.is_active == True).count(),  # noqa: E712
        "teams": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "colour": t.colour,
                "display_order": t.display_order,
                "is_active": t.is_active,
                "group_id": t.group_id,
                "group_name": group.name,
            }
            for t in active_teams
        ],
    }


@router.get("/groups/", response_model=list[TeamGroupOut])
def list_groups(include_inactive: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(TeamGroup)
    if not include_inactive:
        q = q.filter(TeamGroup.is_active == True)  # noqa: E712
    groups = q.order_by(TeamGroup.display_order, TeamGroup.name).all()
    return [group_out(db, g) for g in groups]


@router.post("/groups/", response_model=TeamGroupOut)
def create_group(data: TeamGroupCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _ensure_unique_group_name(db, data.name)
    group = TeamGroup(**data.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group_out(db, group)


@router.get("/groups/{group_id}", response_model=TeamGroupOut)
def read_group(group_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return group_out(db, _group_or_404(db, group_id))


@router.patch("/groups/{group_id}", response_model=TeamGroupOut)
def update_group(group_id: int, data: TeamGroupUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    group = _group_or_404(db, group_id)
    values = data.model_dump(exclude_unset=True)
    if "name" in values:
        _ensure_unique_group_name(db, values["name"], group_id)
    for k, v in values.items():
        setattr(group, k, v)
    db.commit()
    db.refresh(group)
    return group_out(db, group)


@router.delete("/groups/{group_id}", response_model=TeamGroupOut)
def delete_group(group_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    group = _group_or_404(db, group_id)
    for team in group.teams:
        team.group_id = None
    group.is_active = False
    db.commit()
    db.refresh(group)
    return group_out(db, group)


@router.get("", response_model=list[TeamOut])
def list_teams(include_inactive: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Team)
    if not include_inactive:
        q = q.filter(Team.is_active == True)  # noqa: E712
    teams = q.order_by(Team.display_order, Team.name).all()
    return [team_out(db, t) for t in teams]


@router.post("", response_model=TeamOut)
def create_team(data: TeamCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _ensure_unique_team_name(db, data.name)
    _group_or_404(db, data.group_id)
    team = Team(**data.model_dump())
    db.add(team)
    db.commit()
    db.refresh(team)
    return team_out(db, team)


@router.get("/unassigned-users", response_model=list[TeamMemberUserOut])
def unassigned_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(User).filter(User.team_id.is_(None)).order_by(User.display_name).all()


@router.get("/{team_id}", response_model=TeamOut)
def read_team(team_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return team_out(db, _team_or_404(db, team_id))


@router.patch("/{team_id}", response_model=TeamOut)
def update_team(team_id: int, data: TeamUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    team = _team_or_404(db, team_id)
    values = data.model_dump(exclude_unset=True)
    if "name" in values:
        _ensure_unique_team_name(db, values["name"], team_id)
    if "group_id" in values:
        _group_or_404(db, values["group_id"])
    for k, v in values.items():
        setattr(team, k, v)
    db.commit()
    db.refresh(team)
    return team_out(db, team)


@router.delete("/{team_id}", response_model=TeamOut)
def delete_team(team_id: int, data: TeamDeleteIn | None = None, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    team = _team_or_404(db, team_id)
    target_id = data.move_users_to_team_id if data else None
    if target_id == team_id:
        raise HTTPException(400, "Cannot move users to the team being deleted")
    if target_id is not None:
        target = _team_or_404(db, target_id)
        if not target.is_active:
            raise HTTPException(400, "Cannot move users to an inactive team")
    for u in db.query(User).filter(User.team_id == team.id).all():
        u.team_id = target_id
    team.is_active = False
    db.commit()
    db.refresh(team)
    return team_out(db, team)


@router.get("/{team_id}/users", response_model=list[TeamMemberUserOut])
def users_by_team(team_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _team_or_404(db, team_id)
    return db.query(User).filter(User.team_id == team_id).order_by(User.display_name).all()
