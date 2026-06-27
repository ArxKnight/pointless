from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, User
from app.schemas.api import AuditLogOut
from app.services.auth_service import require_admin

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


def audit_out(row: AuditLog) -> dict:
    return {
        "id": row.id,
        "event_type": row.event_type,
        "actor_user_id": row.actor_user_id,
        "actor_username": row.actor_username,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "target_name": row.target_name,
        "message": row.message,
        "metadata_json": row.metadata_json,
        "ip_address": row.ip_address,
        "created_at": row.created_at,
    }


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(limit: int = 200, actor_user_id: int | None = None, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    limit = max(1, min(limit, 1000))
    query = db.query(AuditLog)
    if actor_user_id is not None:
        query = query.filter(AuditLog.actor_user_id == actor_user_id)
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()
    return [audit_out(row) for row in rows]
