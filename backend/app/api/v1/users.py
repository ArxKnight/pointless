from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Team, User
from app.schemas.api import UserAdminOut, UserRoleUpdate, UserTeamUpdate
from app.services.auth_service import require_admin

router = APIRouter(prefix="/users", tags=["users"])


def user_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "team_id": user.team_id,
        "team_name": user.team.name if user.team and user.team.is_active else None,
    }


@router.get("", response_model=list[UserAdminOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return [user_out(u) for u in db.query(User).order_by(User.display_name).all()]


@router.patch("/{user_id}/role", response_model=UserAdminOut)
def set_user_role(user_id: int, data: UserRoleUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "You cannot change your own role")
    user.is_admin = data.is_admin
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.patch("/{user_id}/team", response_model=UserAdminOut)
def set_user_team(user_id: int, data: UserTeamUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if data.team_id is not None:
        team = db.get(Team, data.team_id)
        if not team or not team.is_active:
            raise HTTPException(404, "Active team not found")
    user.team_id = data.team_id
    db.commit()
    db.refresh(user)
    return user_out(user)
