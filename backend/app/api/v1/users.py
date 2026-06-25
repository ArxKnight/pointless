from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas.api import UserAdminOut, UserRoleUpdate
from app.services.auth_service import get_current_user, require_admin

router = APIRouter(prefix="/users", tags=["users"])

@router.get("", response_model=list[UserAdminOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(User).order_by(User.display_name).all()

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
    return user
