from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Team, User
from app.schemas.api import UserAdminOut, UserAdminUpdate, UserRoleUpdate, UserTeamUpdate
from app.services.auth_service import hash_password, require_admin
from app.api.v1.invitations import require_super_admin

router = APIRouter(prefix="/users", tags=["users"])


def user_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "is_admin": user.is_admin,
        "is_super_admin": getattr(user, "is_super_admin", False),
        "is_active": user.is_active,
        "created_at": user.created_at,
        "last_login_at": getattr(user, "last_login_at", None),
        "team_id": user.team_id,
        "team_name": user.team.name if user.team and user.team.is_active else None,
    }


def active_super_admin_count(db: Session, excluding_user_id: int | None = None) -> int:
    q = db.query(User).filter(User.is_admin == True, User.is_super_admin == True, User.is_active == True)  # noqa: E712
    if excluding_user_id is not None:
        q = q.filter(User.id != excluding_user_id)
    return q.count()


def installer_admin_id(db: Session) -> int | None:
    row = db.query(User.id).filter(User.is_admin == True).order_by(User.id.asc()).first()  # noqa: E712
    return row[0] if row else None


def ensure_installer_admin_not_demoted(db: Session, user: User, data: UserAdminUpdate | None = None, deleting: bool = False) -> None:
    first_id = installer_admin_id(db)
    if first_id is None or user.id != first_id:
        return
    if deleting:
        raise HTTPException(400, "The installer-created Admin cannot be deleted")
    if data is not None and data.is_admin is False:
        raise HTTPException(400, "The installer-created Admin cannot be demoted from Admin")


def ensure_not_removing_last_super_admin(db: Session, user: User, data: UserAdminUpdate | None = None, deleting: bool = False) -> None:
    if not getattr(user, "is_super_admin", False) or not user.is_active or not user.is_admin:
        return
    would_remove = deleting
    if data is not None:
        if data.is_active is False or data.is_admin is False or data.is_super_admin is False:
            would_remove = True
    if would_remove and active_super_admin_count(db, excluding_user_id=user.id) == 0:
        raise HTTPException(400, "At least one active Main Admin must remain")


@router.get("", response_model=list[UserAdminOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return [user_out(u) for u in db.query(User).order_by(User.display_name).all()]


@router.patch("/{user_id}", response_model=UserAdminOut)
def update_admin(user_id: int, data: UserAdminUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    require_super_admin(admin)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    ensure_installer_admin_not_demoted(db, user, data)
    ensure_not_removing_last_super_admin(db, user, data)
    if data.username is not None:
        username = data.username.strip()
        if not username:
            raise HTTPException(400, "Username is required")
        exists = db.query(User).filter(func.lower(User.username) == username.lower(), User.id != user.id).first()
        if exists:
            raise HTTPException(409, "Username already exists")
        user.username = username
    if data.email is not None:
        email = str(data.email).lower()
        exists = db.query(User).filter(func.lower(User.email) == email, User.id != user.id).first()
        if exists:
            raise HTTPException(409, "Email address already exists")
        user.email = email
    if data.display_name is not None:
        display_name = data.display_name.strip()
        if not display_name:
            raise HTTPException(400, "Display name is required")
        user.display_name = display_name
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    if data.is_super_admin is not None:
        user.is_super_admin = data.is_super_admin
        if data.is_super_admin:
            user.is_admin = True
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        user.password_hash = hash_password(data.password)
    db.commit(); db.refresh(user)
    return user_out(user)


@router.delete("/{user_id}")
def delete_admin(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    require_super_admin(admin)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    ensure_installer_admin_not_demoted(db, user, deleting=True)
    ensure_not_removing_last_super_admin(db, user, deleting=True)
    # Preserve historical FK references by deactivating rather than physical delete.
    user.is_active = False
    db.commit(); db.refresh(user)
    return {"ok": True, "deactivated": True, "user": user_out(user)}


@router.patch("/{user_id}/role", response_model=UserAdminOut)
def set_user_role(user_id: int, data: UserRoleUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    patch = UserAdminUpdate(is_admin=data.is_admin)
    return update_admin(user_id, patch, db, admin)


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
    db.commit(); db.refresh(user)
    return user_out(user)
