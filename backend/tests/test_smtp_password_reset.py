from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.auth import change_password, confirm_password_reset, _hash_token
from app.models import PasswordResetToken, User
from app.database import Base
from app.schemas.api import PasswordChangeIn, PasswordResetConfirmIn
from app.services.auth_service import hash_password, verify_password
from app.runtime_config import save_smtp_settings, smtp_settings


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_logged_in_admin_can_change_own_password():
    db = make_db()
    user = User(username="owner", display_name="Owner", email="owner@example.com", password_hash=hash_password("oldpassword"), is_admin=True, is_super_admin=True, is_active=True)
    db.add(user); db.commit(); db.refresh(user)
    result = change_password(PasswordChangeIn(current_password="oldpassword", new_password="newpassword123"), db, user)
    assert result == {"ok": True}
    db.refresh(user)
    assert verify_password("newpassword123", user.password_hash)


def test_password_reset_token_sets_new_password_once():
    db = make_db()
    user = User(username="owner", display_name="Owner", email="owner@example.com", password_hash=hash_password("oldpassword"), is_admin=True, is_super_admin=True, is_active=True)
    db.add(user); db.commit(); db.refresh(user)
    raw = "reset-token-for-test-with-enough-length"
    token = PasswordResetToken(token_hash=_hash_token(raw), user_id=user.id, expires_at=datetime.utcnow() + timedelta(hours=1))
    db.add(token); db.commit()
    result = confirm_password_reset(PasswordResetConfirmIn(token=raw, new_password="newpassword123"), db)
    assert result == {"ok": True}
    db.refresh(user); db.refresh(token)
    assert verify_password("newpassword123", user.password_hash)
    assert token.used_at is not None


def test_smtp_settings_do_not_expose_password(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setenv("APP_CONFIG_PATH", str(path))
    saved = save_smtp_settings({"enabled": True, "host": "smtp.example.com", "port": 587, "username": "user", "password": "secret", "from_email": "noreply@example.com"})
    assert saved["password_set"] is True
    assert "password" not in saved
    public = smtp_settings()
    assert public["enabled"] is True
    assert public["password_set"] is True
    assert "password" not in public
