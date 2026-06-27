import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminInvitation, User
from app.schemas.api import AdminInvitationAccept, AdminInvitationCreate
from app.services.auth_service import hash_password, require_admin
from app.services.audit_service import add_audit_log

router = APIRouter(prefix="/admin-invitations", tags=["admin-invitations"])


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def require_super_admin(admin: User) -> None:
    if not admin.is_admin or not getattr(admin, "is_super_admin", False):
        raise HTTPException(403, "Main Admin only")


def invitation_status(inv: AdminInvitation, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    if inv.revoked_at:
        return "revoked"
    if inv.used_at:
        return "used"
    if inv.expires_at <= now:
        return "expired"
    return "pending"


def is_never_expiring(inv: AdminInvitation) -> bool:
    return inv.expires_at.year >= datetime.utcnow().year + 50


def invitation_out(inv: AdminInvitation, db: Session, include_token: str | None = None) -> dict:
    creator = db.get(User, inv.created_by_admin_id) if inv.created_by_admin_id else None
    data = {
        "id": inv.id,
        "invitee_name": inv.invitee_name,
        "invitee_email": inv.invitee_email,
        "created_by_admin_id": inv.created_by_admin_id,
        "created_by_name": creator.display_name if creator else None,
        "created_at": inv.created_at,
        "expires_at": inv.expires_at,
        "used_at": inv.used_at,
        "revoked_at": inv.revoked_at,
        "status": invitation_status(inv),
        "expires_label": "Never" if is_never_expiring(inv) else None,
    }
    link_token = include_token or (inv.raw_token if invitation_status(inv) == "pending" else None)
    if link_token:
        if include_token:
            data["token"] = include_token
        data["invitation_url"] = f"/admin-invite/{link_token}"
    return data


def load_valid_invitation(token: str, db: Session) -> AdminInvitation:
    inv = db.query(AdminInvitation).filter(AdminInvitation.token_hash == token_hash(token)).first()
    if not inv:
        raise HTTPException(404, "Invalid invitation link")
    status = invitation_status(inv)
    if status == "expired":
        raise HTTPException(400, "Invitation has expired")
    if status == "revoked":
        raise HTTPException(400, "Invitation has been revoked")
    if status == "used":
        raise HTTPException(400, "Invitation has already been used")
    return inv


@router.get("")
def list_invitations(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    require_super_admin(admin)
    invitations = db.query(AdminInvitation).order_by(AdminInvitation.created_at.desc(), AdminInvitation.id.desc()).all()
    return [invitation_out(inv, db) for inv in invitations]


@router.post("")
def create_invitation(data: AdminInvitationCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    require_super_admin(admin)
    raw_token = secrets.token_urlsafe(32)
    while db.query(AdminInvitation).filter(AdminInvitation.token_hash == token_hash(raw_token)).first():
        raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + (timedelta(days=365 * 100) if data.expires_in_hours == 0 else timedelta(hours=data.expires_in_hours))
    inv = AdminInvitation(
        token_hash=token_hash(raw_token),
        raw_token=raw_token,
        invitee_name=data.invitee_name.strip(),
        invitee_email=str(data.invitee_email).lower() if data.invitee_email else None,
        created_by_admin_id=admin.id,
        expires_at=expires_at,
    )
    db.add(inv); db.flush()
    add_audit_log(db, "invite_created", actor=admin, target_type="admin_invitation", target_id=inv.id, target_name=inv.invitee_name, message=f"Admin invitation for {inv.invitee_name} was created", metadata={"expires_at": expires_at, "has_email": bool(inv.invitee_email)})
    db.commit(); db.refresh(inv)
    return invitation_out(inv, db, raw_token)


@router.delete("/{invitation_id}")
def revoke_invitation(invitation_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    require_super_admin(admin)
    inv = db.get(AdminInvitation, invitation_id)
    if not inv:
        raise HTTPException(404, "Invitation not found")
    if inv.used_at:
        raise HTTPException(400, "Used invitations cannot be revoked")
    if not inv.revoked_at:
        inv.revoked_at = datetime.utcnow(); inv.raw_token = None; add_audit_log(db, "invite_revoked", actor=admin, target_type="admin_invitation", target_id=inv.id, target_name=inv.invitee_name, message=f"Admin invitation for {inv.invitee_name} was revoked"); db.commit(); db.refresh(inv)
    return invitation_out(inv, db)


@router.get("/{token}")
def public_invitation(token: str, db: Session = Depends(get_db)):
    inv = load_valid_invitation(token, db)
    return {"invitee_name": inv.invitee_name, "invitee_email": inv.invitee_email, "expires_at": inv.expires_at, "status": "pending"}


@router.post("/{token}/accept")
def accept_invitation(token: str, data: AdminInvitationAccept, db: Session = Depends(get_db)):
    inv = load_valid_invitation(token, db)
    if data.password != data.password_confirm:
        raise HTTPException(400, "Password confirmation does not match")
    username = data.username.strip()
    email = str(data.email).lower()
    if not username:
        raise HTTPException(422, "Username is required")
    if db.query(User).filter(func.lower(User.username) == username.lower()).first():
        raise HTTPException(409, "Username already exists")
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "Email address already exists")
    display_name = (data.display_name or username).strip()
    user = User(
        username=username,
        display_name=display_name or username,
        email=email,
        password_hash=hash_password(data.password),
        is_admin=True,
        is_super_admin=False,
        is_active=True,
    )
    db.add(user); db.flush()
    inv.used_at = datetime.utcnow(); inv.used_by_admin_id = user.id; inv.raw_token = None
    add_audit_log(db, "admin_created", actor=user, target_type="admin", target_id=user.id, target_name=user.username, message=f"Admin {user.username} was created from invitation")
    add_audit_log(db, "invite_accepted", actor=user, target_type="admin_invitation", target_id=inv.id, target_name=inv.invitee_name, message=f"Admin invitation for {inv.invitee_name} was accepted")
    db.commit(); db.refresh(user)
    return {"message": "Administrator account created", "user": {"id": user.id, "username": user.username, "display_name": user.display_name, "email": user.email, "is_admin": user.is_admin, "is_super_admin": user.is_super_admin, "is_active": user.is_active}}
