from collections import defaultdict, deque
from datetime import datetime, timedelta
import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import PasswordResetToken, User
from app.schemas.api import LoginIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetRequestIn, UserOut
from app.services.auth_service import authenticate, create_access_token, get_current_user, hash_password, verify_password
from app.services.email_service import send_password_reset_email, smtp_is_enabled
from app.services.audit_service import add_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])
_attempts = defaultdict(deque)
_RESET_EXPIRES_MINUTES = 60


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _origin_from_request(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        return f"{forwarded_proto or request.url.scheme}://{forwarded_host}"
    return str(request.base_url).rstrip("/")


@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    now = datetime.utcnow(); bucket = _attempts[ip]
    while bucket and bucket[0] < now - timedelta(minutes=1): bucket.popleft()
    if len(bucket) >= 5: raise HTTPException(status_code=429, detail="Too many login attempts")
    user = authenticate(db, data.username, data.password)
    if not user:
        bucket.append(now); raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user)
    user.last_login_at = datetime.utcnow()
    if user.is_admin:
        add_audit_log(db, "admin_login", actor=user, target_type="admin", target_id=user.id, target_name=user.username, message=f"Admin {user.username} logged in", ip_address=ip)
    db.commit()
    response.set_cookie("access_token", token, httponly=True, samesite="lax", secure=settings.cookie_secure, max_age=settings.access_token_expire_minutes*60)
    return {"user": UserOut.model_validate(user)}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)): return user


@router.post("/change-password")
def change_password(data: PasswordChangeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"ok": True}


@router.get("/password-reset/enabled")
def password_reset_enabled():
    return {"enabled": smtp_is_enabled()}


@router.post("/password-reset/request")
def request_password_reset(data: PasswordResetRequestIn, request: Request, db: Session = Depends(get_db)):
    # Return the same response for every input so the login page cannot be used to enumerate admin accounts.
    generic = {"ok": True, "message": "If SMTP is configured and the account exists, a reset link has been emailed."}
    if not smtp_is_enabled():
        return generic
    lookup = data.username_or_email.strip().lower()
    if not lookup:
        return generic
    user = db.query(User).filter(User.is_active == True).filter((func.lower(User.username) == lookup) | (func.lower(User.email) == lookup)).first()  # noqa: E712
    if not user:
        return generic
    raw_token = secrets.token_urlsafe(32)
    reset = PasswordResetToken(
        token_hash=_hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(minutes=_RESET_EXPIRES_MINUTES),
        requested_ip=request.client.host if request.client else None,
    )
    db.add(reset); db.commit()
    reset_url = f"{_origin_from_request(request)}/reset-password/{raw_token}"
    try:
        send_password_reset_email(user.email, user.username, reset_url)
    except Exception:
        # Do not leak SMTP failure or account existence to the login page. Admins can use SMTP Settings test for diagnostics.
        pass
    return generic


@router.post("/password-reset/confirm")
def confirm_password_reset(data: PasswordResetConfirmIn, db: Session = Depends(get_db)):
    token_hash = _hash_token(data.token)
    reset = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    if not reset or reset.used_at is not None or reset.expires_at < datetime.utcnow():
        raise HTTPException(400, "Reset link is invalid or has expired")
    user = db.get(User, reset.user_id)
    if not user or not user.is_active:
        raise HTTPException(400, "Reset link is invalid or has expired")
    user.password_hash = hash_password(data.new_password)
    reset.used_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
