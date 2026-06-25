import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import DepartmentMember, Participant, ParticipantSlugRedirect

_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class BulkParticipantResult:
    created: list[Participant]
    duplicates: list[str]
    ignored_blank_lines: int


def base_slug(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug or "participant"


def slugify_name(value: str, db: Session, current_participant_id: int | None = None) -> str:
    base = base_slug(value)
    candidate = base
    suffix = 2
    while True:
        q = db.query(Participant).filter(func.lower(Participant.slug) == candidate.lower())
        if current_participant_id is not None:
            q = q.filter(Participant.id != current_participant_id)
        slug_taken = q.first() is not None
        redirect_taken = db.query(ParticipantSlugRedirect).filter(func.lower(ParticipantSlugRedirect.old_slug) == candidate.lower()).first() is not None
        if not slug_taken and not redirect_taken:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def create_participant(db: Session, display_name: str, slug: str | None = None, notes: str | None = None, is_active: bool = True, legacy_member_id: int | None = None) -> Participant:
    name = display_name.strip()
    if not name:
        raise ValueError("Participant name is required")
    final_slug = slugify_name(slug or name, db)
    participant = Participant(display_name=name, slug=final_slug, notes=notes, is_active=is_active, legacy_member_id=legacy_member_id)
    db.add(participant)
    db.flush()
    return participant


def bulk_create_participants(db: Session, text: str) -> BulkParticipantResult:
    created: list[Participant] = []
    duplicates: list[str] = []
    seen_names: set[str] = set()
    ignored = 0
    for raw in text.splitlines():
        name = raw.strip()
        if not name:
            ignored += 1
            continue
        key = name.lower()
        existing = db.query(Participant).filter(func.lower(Participant.display_name) == key).first()
        if key in seen_names or existing:
            duplicates.append(name)
            continue
        created.append(create_participant(db, name))
        seen_names.add(key)
    return BulkParticipantResult(created=created, duplicates=duplicates, ignored_blank_lines=ignored)


def update_participant_slug(db: Session, participant: Participant, new_slug: str) -> None:
    final_slug = slugify_name(new_slug, db, current_participant_id=participant.id)
    if final_slug != participant.slug:
        db.add(ParticipantSlugRedirect(participant_id=participant.id, old_slug=participant.slug))
        participant.slug = final_slug
    participant.updated_at = datetime.utcnow()


def backfill_participants_from_department_members(db: Session) -> int:
    created = 0
    for member in db.query(DepartmentMember).order_by(DepartmentMember.id).all():
        if db.query(Participant).filter(Participant.legacy_member_id == member.id).first():
            continue
        create_participant(
            db,
            member.display_name,
            is_active=member.active,
            legacy_member_id=member.id,
        )
        created += 1
    db.flush()
    return created
