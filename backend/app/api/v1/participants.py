from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GivingPlan, Participant, QuarterParticipant, User
from app.schemas.api import ParticipantBulkCreate, ParticipantBulkOut, ParticipantCreate, ParticipantOut, ParticipantUpdate
from app.services.auth_service import require_admin
from app.services.audit_service import add_audit_log
from app.services.participant_service import bulk_create_participants, create_participant, update_participant_slug
from app.services.quarter_lookup import current_published_quarter

router = APIRouter(prefix="/participants", tags=["participants"])


def participant_out(db: Session, p: Participant, request: Request | None = None) -> dict:
    published = current_published_quarter(db)
    included = False
    if published:
        included = db.query(QuarterParticipant).filter_by(quarter_id=published.id, participant_id=p.id).first() is not None
    return {
        "id": p.id,
        "display_name": p.display_name,
        "slug": p.slug,
        "is_active": p.is_active,
        "notes": p.notes,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "public_url": f"/{p.slug}",
        "included_in_current_quarter": included,
        "current_quarter_status": "deactivated_but_included" if included and not p.is_active else ("included" if included else "excluded"),
    }


@router.get("", response_model=list[ParticipantOut])
def list_participants(search: str | None = None, include_inactive: bool = True, db: Session = Depends(get_db), admin: User = Depends(require_admin), request: Request = None):
    q = db.query(Participant)
    if not include_inactive:
        q = q.filter(Participant.is_active == True)  # noqa: E712
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(or_(Participant.display_name.ilike(like), Participant.slug.ilike(like)))
    return [participant_out(db, p, request) for p in q.order_by(Participant.display_name).all()]


@router.post("", response_model=ParticipantOut)
def add_participant(data: ParticipantCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    try:
        p = create_participant(db, data.display_name, data.slug, data.notes, data.is_active)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    add_audit_log(db, "participant_created", actor=admin, target_type="participant", target_id=p.id, target_name=p.display_name, message=f"Participant {p.display_name} was created")
    db.commit(); db.refresh(p)
    return participant_out(db, p)


@router.post("/bulk", response_model=ParticipantBulkOut)
def add_participants_bulk(data: ParticipantBulkCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    result = bulk_create_participants(db, data.names)
    for p in result.created:
        add_audit_log(db, "participant_created", actor=admin, target_type="participant", target_id=p.id, target_name=p.display_name, message=f"Participant {p.display_name} was created by bulk import")
    db.commit()
    created_count = len(result.created)
    duplicate_count = len(result.duplicates)
    invalid_count = len(result.invalid)
    parts = []
    if created_count: parts.append(f"{created_count} participants created")
    if duplicate_count: parts.append(f"{duplicate_count} duplicates skipped")
    if invalid_count: parts.append(f"{invalid_count} invalid entries rejected")
    if result.ignored_blank_lines: parts.append(f"{result.ignored_blank_lines} blank lines ignored")
    message = "; ".join(parts) if parts else "No participants were created."
    if created_count == 0 and duplicate_count:
        message = "No participants were created because all submitted names already exist."
    return {"created": [participant_out(db, p) for p in result.created], "duplicates": result.duplicates, "invalid": result.invalid, "ignored_blank_lines": result.ignored_blank_lines, "created_count": created_count, "duplicate_count": duplicate_count, "invalid_count": invalid_count, "message": message}


@router.patch("/{participant_id}", response_model=ParticipantOut)
def update_participant(participant_id: int, data: ParticipantUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    p = db.get(Participant, participant_id)
    if not p:
        raise HTTPException(404, "Participant not found")
    values = data.model_dump(exclude_unset=True)
    if "display_name" in values and values["display_name"] is not None:
        p.display_name = values["display_name"].strip()
    if "notes" in values:
        p.notes = values["notes"]
    if "is_active" in values and values["is_active"] is not None:
        p.is_active = values["is_active"]
    if "slug" in values and values["slug"]:
        update_participant_slug(db, p, values["slug"])
    p.updated_at = datetime.utcnow()
    event = "participant_deactivated" if values.get("is_active") is False else ("participant_reactivated" if values.get("is_active") is True else "participant_updated")
    add_audit_log(db, event, actor=admin, target_type="participant", target_id=p.id, target_name=p.display_name, message=f"Participant {p.display_name} was updated", metadata=values)
    db.commit(); db.refresh(p)
    return participant_out(db, p)


@router.post("/{participant_id}/deactivate", response_model=ParticipantOut)
def deactivate_participant(participant_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    p = db.get(Participant, participant_id)
    if not p: raise HTTPException(404, "Participant not found")
    p.is_active = False; p.updated_at = datetime.utcnow(); add_audit_log(db, "participant_deactivated", actor=admin, target_type="participant", target_id=p.id, target_name=p.display_name, message=f"Participant {p.display_name} was deactivated"); db.commit(); db.refresh(p)
    return participant_out(db, p)


@router.post("/{participant_id}/reactivate", response_model=ParticipantOut)
def reactivate_participant(participant_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    p = db.get(Participant, participant_id)
    if not p: raise HTTPException(404, "Participant not found")
    p.is_active = True; p.updated_at = datetime.utcnow(); add_audit_log(db, "participant_reactivated", actor=admin, target_type="participant", target_id=p.id, target_name=p.display_name, message=f"Participant {p.display_name} was reactivated"); db.commit(); db.refresh(p)
    return participant_out(db, p)


@router.delete("/{participant_id}")
def delete_participant(participant_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    p = db.get(Participant, participant_id)
    if not p: raise HTTPException(404, "Participant not found")
    used = db.query(GivingPlan).filter((GivingPlan.from_participant_id == p.id) | (GivingPlan.to_participant_id == p.id)).first() or db.query(QuarterParticipant).filter_by(participant_id=p.id).first()
    if used:
        raise HTTPException(409, "Participant has historical distribution data and cannot be deleted. Deactivate instead.")
    add_audit_log(db, "participant_deleted", actor=admin, target_type="participant", target_id=p.id, target_name=p.display_name, message=f"Participant {p.display_name} was deleted")
    db.delete(p); db.commit()
    return {"ok": True}
