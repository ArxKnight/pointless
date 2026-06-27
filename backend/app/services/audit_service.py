import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def _safe_json(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    try:
        return json.dumps(data, default=str, sort_keys=True)
    except Exception:
        return json.dumps({"unserializable": True}, sort_keys=True)


def add_audit_log(
    db: Session,
    event_type: str,
    *,
    actor: User | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    target_name: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog | None:
    """Append an audit event without committing. Never break the primary action."""
    try:
        row = AuditLog(
            event_type=event_type,
            actor_user_id=actor.id if actor else None,
            actor_username=actor.username if actor else None,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            message=message or event_type.replace("_", " ").title(),
            metadata_json=_safe_json(metadata),
            ip_address=ip_address,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        return row
    except Exception:
        return None
