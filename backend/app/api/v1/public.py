from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GivingPlan, Participant, ParticipantSlugRedirect, Quarter, QuarterParticipant

router = APIRouter(prefix="/public", tags=["public"])


def current_published_quarter(db: Session) -> Quarter | None:
    return db.query(Quarter).filter(Quarter.status == "published").order_by(Quarter.published_at.desc().nullslast(), Quarter.id.desc()).first()


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
        return {"status": "no_published_quarter", "message": "No giving distribution is currently available.", "participant": {"display_name": participant.display_name, "slug": participant.slug}, "quarter": None, "allocations": [], "total_allocated": 0}
    included = db.query(QuarterParticipant).filter_by(quarter_id=quarter.id, participant_id=participant.id).first()
    if not included:
        return {"status": "not_included", "message": "This participant does not have a giving tree for the current quarter.", "participant": {"display_name": participant.display_name, "slug": participant.slug}, "quarter": {"label": quarter.label, "year": quarter.year, "quarter": quarter.quarter}, "allocations": [], "total_allocated": 0}
    rows = db.query(GivingPlan).filter(GivingPlan.quarter_id == quarter.id, GivingPlan.from_participant_id == participant.id).all()
    allocations = [{"recipient_name": r.to_participant.display_name if r.to_participant else "Unknown", "amount": r.amount} for r in rows]
    return {
        "status": "ok",
        "redirected_from": redirected_from,
        "participant": {"display_name": participant.display_name, "slug": participant.slug},
        "quarter": {"label": quarter.label, "year": quarter.year, "quarter": quarter.quarter},
        "total_points": 50,
        "allocations": allocations,
        "total_allocated": sum(r["amount"] for r in allocations),
    }


@router.get("/tree/{slug}")
def public_tree(slug: str, response: Response, db: Session = Depends(get_db)):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    try:
        return public_tree_payload(db, slug)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
