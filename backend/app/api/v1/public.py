from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GivingPlan, Participant, ParticipantSlugRedirect, Quarter, QuarterParticipant
from app.services.quarter_lookup import current_published_quarter

router = APIRouter(prefix="/public", tags=["public"])


def current_calendar_quarter() -> tuple[int, int]:
    from datetime import datetime
    now = datetime.utcnow()
    return now.year, ((now.month - 1) // 3) + 1


def next_scheduled_quarter(db: Session, participant_id: int, exclude_quarter_id: int | None = None) -> Quarter | None:
    year, quarter = current_calendar_quarter()
    query = (
        db.query(Quarter)
        .join(QuarterParticipant, QuarterParticipant.quarter_id == Quarter.id)
        .filter(QuarterParticipant.participant_id == participant_id)
        .filter((Quarter.year > year) | ((Quarter.year == year) & (Quarter.quarter >= quarter)))
    )
    if exclude_quarter_id is not None:
        query = query.filter(Quarter.id != exclude_quarter_id)
    return query.order_by(Quarter.year.asc(), Quarter.quarter.asc(), Quarter.id.asc()).first()


def quarter_public(q: Quarter | None) -> dict | None:
    return {"label": q.label, "year": q.year, "quarter": q.quarter} if q else None


def public_tree_payload(db: Session, slug: str) -> dict:
    participant = db.query(Participant).filter(Participant.slug == slug).first()
    redirected_from = None
    if not participant:
        redirect = db.query(ParticipantSlugRedirect).filter(ParticipantSlugRedirect.old_slug == slug).first()
        if redirect:
            participant = db.get(Participant, redirect.participant_id)
            redirected_from = slug
    if not participant:
        raise LookupError("Giving tree not found.")
    quarter = current_published_quarter(db)
    if not quarter:
        next_quarter = next_scheduled_quarter(db, participant.id)
        if next_quarter:
            return {"status": "not_currently_participating", "message": f"{participant.display_name} is not currently participating in an active quarterly tree. They are next scheduled for {next_quarter.label}.", "participant": {"display_name": participant.display_name, "slug": participant.slug}, "quarter": None, "next_quarter": quarter_public(next_quarter), "allocations": [], "total_allocated": 0}
        return {"status": "not_currently_participating", "message": f"{participant.display_name} is not currently participating in any quarterly tree.", "participant": {"display_name": participant.display_name, "slug": participant.slug}, "quarter": None, "next_quarter": None, "allocations": [], "total_allocated": 0}
    included = db.query(QuarterParticipant).filter_by(quarter_id=quarter.id, participant_id=participant.id).first()
    if not included:
        next_quarter = next_scheduled_quarter(db, participant.id, exclude_quarter_id=quarter.id)
        if next_quarter:
            message = f"{participant.display_name} is not currently participating in the active quarterly tree. They are next scheduled for {next_quarter.label}."
        else:
            message = f"{participant.display_name} is not currently participating in any quarterly tree."
        return {"status": "not_included", "message": message, "participant": {"display_name": participant.display_name, "slug": participant.slug}, "quarter": quarter_public(quarter), "next_quarter": quarter_public(next_quarter), "allocations": [], "total_allocated": 0}
    outgoing_rows = db.query(GivingPlan).filter(GivingPlan.quarter_id == quarter.id, GivingPlan.from_participant_id == participant.id).all()
    incoming_rows = db.query(GivingPlan).filter(GivingPlan.quarter_id == quarter.id, GivingPlan.to_participant_id == participant.id).all()
    allocations = [{"recipient_name": r.to_participant.display_name if r.to_participant else "Unknown", "amount": r.amount} for r in outgoing_rows]
    incoming_allocations = [{"sender_name": r.from_participant.display_name if r.from_participant else "Unknown", "amount": r.amount} for r in incoming_rows]
    return {
        "status": "ok",
        "redirected_from": redirected_from,
        "participant": {"display_name": participant.display_name, "slug": participant.slug},
        "quarter": {"label": quarter.label, "year": quarter.year, "quarter": quarter.quarter},
        "total_points": 50,
        "allocations": allocations,
        "incoming_allocations": incoming_allocations,
        "total_allocated": sum(r["amount"] for r in allocations),
        "total_incoming": sum(r["amount"] for r in incoming_allocations),
    }


@router.get("/tree/{slug}")
def public_tree(slug: str, response: Response, db: Session = Depends(get_db)):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    try:
        return public_tree_payload(db, slug)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
