from fastapi import APIRouter, Depends, HTTPException
from app.models import User
from app.runtime_config import access_settings, save_access_settings, smtp_settings, save_smtp_settings
from app.schemas.api import AccessSettingsIn, AccessSettingsOut, SmtpSettingsIn, SmtpSettingsOut, SmtpTestIn
from app.services.email_service import send_email
from app.services.auth_service import require_admin
from app.services.audit_service import add_audit_log
from app.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/access", response_model=AccessSettingsOut)
def get_access_settings(admin: User = Depends(require_admin)):
    return access_settings()


@router.patch("/access", response_model=AccessSettingsOut)
def update_access_settings(data: AccessSettingsIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    payload = data.model_dump(exclude_unset=True)
    updated = save_access_settings(payload)
    add_audit_log(db, "access_settings_changed", actor=admin, target_type="settings", target_name="Access control", message="Access-control settings were changed", metadata=payload)
    db.commit()
    return updated


@router.get("/smtp", response_model=SmtpSettingsOut)
def get_smtp_settings(admin: User = Depends(require_admin)):
    return smtp_settings()


@router.patch("/smtp", response_model=SmtpSettingsOut)
def update_smtp_settings(data: SmtpSettingsIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    payload = data.model_dump(exclude_unset=True)
    updated = {**smtp_settings(), **payload}
    if updated.get("use_ssl") and updated.get("use_tls"):
        raise HTTPException(400, "Choose either SSL or STARTTLS, not both")
    saved = save_smtp_settings(payload)
    audit_payload = {k: v for k, v in payload.items() if k != "password"}
    if "password" in payload: audit_payload["password_changed"] = True
    add_audit_log(db, "smtp_settings_changed", actor=admin, target_type="settings", target_name="SMTP", message="SMTP settings were changed", metadata=audit_payload)
    db.commit()
    return saved


@router.post("/smtp/test")
def test_smtp_settings(data: SmtpTestIn, admin: User = Depends(require_admin)):
    try:
        send_email(str(data.to_email), "Pointless SMTP test", "SMTP is working for Pointless password reset emails.")
    except Exception as exc:
        raise HTTPException(400, f"SMTP test failed: {exc}")
    return {"ok": True}
