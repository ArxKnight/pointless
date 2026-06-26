from datetime import datetime
import logging
import sys
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CompatibilityRule, GivingPlan, Participant, PointsLedger, Quarter, QuarterParticipant, User
from app.schemas.api import AllocationEditIn, GenerateIn, QuarterCreateIn, QuarterGenerateActivateIn, QuarterOut, QuarterParticipantsIn, QuarterGenerateIn, QuarterUpdateIn
from app.services.auth_service import get_current_user, require_admin
from app.services.participant_generator import GenerationSettings, generate_distribution, validate_distribution, validate_feasibility
from app.services.quarter_lookup import current_published_quarter, current_calendar_quarter

router = APIRouter(prefix="/quarters", tags=["quarters"])
logger = logging.getLogger("app.quarters")


def qlog(level: str, message: str, *args) -> None:
    getattr(logger, level)(message, *args)
    rendered = message % args if args else message
    print(f"[pointless] {rendered}", file=sys.stderr, flush=True)


def next_quarter(db):
    last = db.query(Quarter).order_by(Quarter.year.desc(), Quarter.quarter.desc()).first()
    if not last:
        now = datetime.utcnow(); return now.year, ((now.month - 1) // 3) + 1
    return (last.year + 1, 1) if last.quarter == 4 else (last.year, last.quarter + 1)


def remove_legacy_draft_status(db: Session, quarters: list[Quarter]) -> None:
    changed = False
    for q in quarters:
        if q.status == "draft":
            q.status = "published"
            changed = True
    if changed:
        db.commit()


def is_past_quarter(q: Quarter) -> bool:
    year, quarter = current_calendar_quarter()
    return (q.year, q.quarter) < (year, quarter)


def assert_not_existing_quarter(db: Session, year: int, quarter: int, exclude_id: int | None = None) -> None:
    existing = db.query(Quarter).filter(Quarter.year == year, Quarter.quarter == quarter)
    if exclude_id is not None:
        existing = existing.filter(Quarter.id != exclude_id)
    if existing.first():
        raise HTTPException(409, f"Q{quarter} {year} is already made. Delete the existing quarter first before making it again.")


def replace_quarter_participants(db: Session, q: Quarter, ids: list[int]) -> None:
    ids = sorted(set(ids))
    participants = db.query(Participant).filter(Participant.id.in_(ids)).all() if ids else []
    if len(participants) != len(ids):
        raise HTTPException(404, "One or more participants were not found")
    db.query(QuarterParticipant).filter_by(quarter_id=q.id).delete()
    for pid in ids:
        db.add(QuarterParticipant(quarter_id=q.id, participant_id=pid))
    # Production sessions deliberately run with autoflush=False, so make the
    # selected participant rows visible before generation immediately queries
    # quarter_participants(). Without this, Generate/Publish can see 0 selected
    # participants even though the request contained the selected IDs.
    db.flush()


def plan_row(p: GivingPlan):
    from_name = p.from_participant.display_name if p.from_participant else (p.from_member.display_name if p.from_member else "Unknown")
    to_name = p.to_participant.display_name if p.to_participant else (p.to_member.display_name if p.to_member else "Unknown")
    return {
        "id": p.id,
        "quarter_id": p.quarter_id,
        "from_member_id": p.from_member_id,
        "to_member_id": p.to_member_id,
        "from_participant_id": p.from_participant_id,
        "to_participant_id": p.to_participant_id,
        "from_name": from_name,
        "to_name": to_name,
        "amount": p.amount,
        "acknowledged": p.acknowledged,
    }


def plan_rows(db, qid):
    return [plan_row(p) for p in db.query(GivingPlan).filter(GivingPlan.quarter_id == qid).all()]


def quarter_participants(db: Session, qid: int) -> list[Participant]:
    return [qp.participant for qp in db.query(QuarterParticipant).filter_by(quarter_id=qid).join(Participant).order_by(Participant.display_name).all()]


def settings_for(q: Quarter, seed: int | None = None) -> GenerationSettings:
    return GenerationSettings(
        min_amount=10,
        max_amount=50,
        preferred_min_recipients=max(1, q.preferred_min_recipients or 2),
        preferred_max_recipients=max(2, q.preferred_max_recipients or 3),
        seed=seed,
    )


@router.get("", response_model=list[QuarterOut])
def list_quarters(include_history: bool = False, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    query = db.query(Quarter)
    if not include_history:
        year, quarter = current_calendar_quarter()
        query = query.filter((Quarter.year > year) | ((Quarter.year == year) & (Quarter.quarter >= quarter)))
    rows = query.order_by(Quarter.year.desc(), Quarter.quarter.desc()).all()
    remove_legacy_draft_status(db, rows)
    return rows


@router.get("/history", response_model=list[QuarterOut])
def list_historical_quarters(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    year, quarter = current_calendar_quarter()
    rows = db.query(Quarter).filter((Quarter.year < year) | ((Quarter.year == year) & (Quarter.quarter < quarter))).order_by(Quarter.year.desc(), Quarter.quarter.desc()).all()
    remove_legacy_draft_status(db, rows)
    return rows


@router.post("", response_model=QuarterOut)
def create_quarter(data: QuarterCreateIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    assert_not_existing_quarter(db, data.year, data.quarter)
    q = Quarter(
        year=data.year,
        quarter=data.quarter,
        label=data.label or f"Q{data.quarter} {data.year}",
        status="created",
        is_active=False,
        is_completed=False,
        allocation_min=10,
        allocation_max=50,
        preferred_min_recipients=data.preferred_min_recipients,
        preferred_max_recipients=data.preferred_max_recipients,
    )
    db.add(q); db.commit(); db.refresh(q)
    return q


@router.get("/active")
def get_active(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = current_published_quarter(db)
    if not q:
        return {"quarter": None, "plans": [], "members": []}
    participants = quarter_participants(db, q.id)
    return {"quarter": QuarterOut.model_validate(q), "plans": plan_rows(db, q.id), "members": [{"id": p.id, "display_name": p.display_name} for p in participants]}


def overview_tree_payload(db: Session, q: Quarter | None):
    """Legacy overview payload retained for older tests/clients.

    The core workflow no longer depends on teams, but this keeps historical
    team overview data readable until the old UI is fully removed.
    """
    from app.models import DepartmentMember, Team, TeamGroup
    active_groups = db.query(TeamGroup).filter(TeamGroup.is_active == True).order_by(TeamGroup.display_order, TeamGroup.name).all()  # noqa: E712
    active_teams = db.query(Team).filter(Team.is_active == True).order_by(Team.display_order, Team.name).all()  # noqa: E712
    users_by_email = {u.email.lower(): u for u in db.query(User).all()}
    members = db.query(DepartmentMember).filter(DepartmentMember.active == True).order_by(DepartmentMember.display_name).all()  # noqa: E712
    plans = db.query(GivingPlan).filter(GivingPlan.quarter_id == q.id).all() if q else []
    sent = {m.id: 0 for m in members}; received = {m.id: 0 for m in members}; recipients = {m.id: set() for m in members}; sources = {m.id: set() for m in members}
    for p in plans:
        source = p.from_member_id or p.from_participant_id
        target = p.to_member_id or p.to_participant_id
        if source is None or target is None: continue
        sent[source] = sent.get(source, 0) + p.amount; received[target] = received.get(target, 0) + p.amount
        recipients.setdefault(source, set()).add(target); sources.setdefault(target, set()).add(source)
    return {
        "quarter": QuarterOut.model_validate(q) if q else None,
        "team_groups": [{"id": g.id, "name": g.name, "description": g.description, "display_order": g.display_order, "is_active": g.is_active} for g in active_groups],
        "teams": [{"id": t.id, "name": t.name, "description": t.description, "colour": t.colour, "display_order": t.display_order, "is_active": t.is_active, "group_id": t.group_id if t.group and t.group.is_active else None, "group_name": t.group.name if t.group and t.group.is_active else None} for t in active_teams],
        "users": [{"member_id": m.id, "user_id": users_by_email.get(m.email.lower()).id if users_by_email.get(m.email.lower()) else None, "display_name": users_by_email.get(m.email.lower()).display_name if users_by_email.get(m.email.lower()) else m.display_name, "email": m.email, "team_id": users_by_email.get(m.email.lower()).team_id if users_by_email.get(m.email.lower()) and users_by_email.get(m.email.lower()).team and users_by_email.get(m.email.lower()).team.is_active else None, "team_name": users_by_email.get(m.email.lower()).team.name if users_by_email.get(m.email.lower()) and users_by_email.get(m.email.lower()).team and users_by_email.get(m.email.lower()).team.is_active else None, "team_colour": users_by_email.get(m.email.lower()).team.colour if users_by_email.get(m.email.lower()) and users_by_email.get(m.email.lower()).team and users_by_email.get(m.email.lower()).team.is_active else None, "team_group_id": users_by_email.get(m.email.lower()).team.group_id if users_by_email.get(m.email.lower()) and users_by_email.get(m.email.lower()).team and users_by_email.get(m.email.lower()).team.is_active and users_by_email.get(m.email.lower()).team.group and users_by_email.get(m.email.lower()).team.group.is_active else None, "team_group_name": users_by_email.get(m.email.lower()).team.group.name if users_by_email.get(m.email.lower()) and users_by_email.get(m.email.lower()).team and users_by_email.get(m.email.lower()).team.is_active and users_by_email.get(m.email.lower()).team.group and users_by_email.get(m.email.lower()).team.group.is_active else None, "total_points_sent": sent.get(m.id, 0), "total_points_received": received.get(m.id, 0), "recipient_count": len(recipients.get(m.id, set())), "incoming_allocation_count": len(sources.get(m.id, set()))} for m in members],
        "allocations": [{"allocation_id": p.id, "quarter_id": p.quarter_id, "quarter": p.quarter.label, "source_member_id": p.from_member_id or p.from_participant_id, "recipient_member_id": p.to_member_id or p.to_participant_id, "source_user_id": None, "recipient_user_id": None, "source_name": p.from_member.display_name if p.from_member else p.from_participant.display_name, "recipient_name": p.to_member.display_name if p.to_member else p.to_participant.display_name, "points": p.amount, "acknowledged": p.acknowledged, "allocation_date": p.quarter.generated_at} for p in plans],
    }


def participant_overview_tree_payload(db: Session, q: Quarter | None):
    participants = quarter_participants(db, q.id) if q else []
    plans = db.query(GivingPlan).filter(GivingPlan.quarter_id == q.id).all() if q else []
    sent = {p.id: 0 for p in participants}; received = {p.id: 0 for p in participants}; recipients = {p.id: set() for p in participants}; sources = {p.id: set() for p in participants}
    for row in plans:
        if row.from_participant_id is None or row.to_participant_id is None: continue
        sent[row.from_participant_id] = sent.get(row.from_participant_id, 0) + row.amount
        received[row.to_participant_id] = received.get(row.to_participant_id, 0) + row.amount
        recipients.setdefault(row.from_participant_id, set()).add(row.to_participant_id)
        sources.setdefault(row.to_participant_id, set()).add(row.from_participant_id)
    return {
        "quarter": QuarterOut.model_validate(q) if q else None,
        "team_groups": [],
        "teams": [],
        "users": [{"member_id": p.id, "user_id": None, "display_name": p.display_name, "email": "", "team_id": None, "team_name": None, "team_colour": None, "team_group_id": None, "team_group_name": None, "total_points_sent": sent.get(p.id, 0), "total_points_received": received.get(p.id, 0), "recipient_count": len(recipients.get(p.id, set())), "incoming_allocation_count": len(sources.get(p.id, set()))} for p in participants],
        "allocations": [{"allocation_id": r.id, "quarter_id": r.quarter_id, "quarter": q.label if q else "", "source_member_id": r.from_participant_id, "recipient_member_id": r.to_participant_id, "source_user_id": None, "recipient_user_id": None, "source_name": r.from_participant.display_name if r.from_participant else "Unknown", "recipient_name": r.to_participant.display_name if r.to_participant else "Unknown", "points": r.amount, "acknowledged": r.acknowledged, "allocation_date": q.published_at or q.generated_at if q else None} for r in plans],
    }


@router.get("/active/overview-tree")
def active_overview_tree(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return participant_overview_tree_payload(db, current_published_quarter(db))


@router.get("/{quarter_id}/overview-tree")
def quarter_overview_tree(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    return participant_overview_tree_payload(db, q)


@router.put("/{quarter_id}/participants")
def set_quarter_participants(quarter_id: int, data: QuarterParticipantsIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    if q.status == "published": raise HTTPException(409, "Cannot change participants on a published quarter")
    replace_quarter_participants(db, q, data.participant_ids)
    db.commit()
    return {"ok": True, "participant_count": len(set(data.participant_ids))}


@router.patch("/{quarter_id}", response_model=QuarterOut)
def update_quarter(quarter_id: int, data: QuarterUpdateIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    if q.status == "published": raise HTTPException(409, "Cannot edit a published quarter. Delete it and generate a replacement if needed.")
    new_year = data.year if data.year is not None else q.year
    new_quarter = data.quarter if data.quarter is not None else q.quarter
    if (new_year, new_quarter) != (q.year, q.quarter):
        assert_not_existing_quarter(db, new_year, new_quarter, exclude_id=q.id)
    q.year = new_year
    q.quarter = new_quarter
    q.label = data.label.strip() if data.label and data.label.strip() else f"Q{new_quarter} {new_year}"
    if data.participant_ids is not None:
        replace_quarter_participants(db, q, data.participant_ids)
        db.query(GivingPlan).filter(GivingPlan.quarter_id == q.id).delete()
        q.status = "created"
    db.commit(); db.refresh(q)
    return q


@router.delete("/{quarter_id}")
def delete_quarter(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    if db.query(PointsLedger).filter(PointsLedger.quarter_id == q.id).first():
        raise HTTPException(409, "This quarter has sent-point history and cannot be deleted safely")
    db.query(GivingPlan).filter(GivingPlan.quarter_id == q.id).delete()
    db.query(QuarterParticipant).filter(QuarterParticipant.quarter_id == q.id).delete()
    db.delete(q); db.commit()
    return {"ok": True}


@router.post("/{quarter_id}/validate")
def validate_quarter(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    result = validate_feasibility(quarter_participants(db, q.id), db.query(CompatibilityRule).all(), settings_for(q))
    return {"valid": result.valid, "errors": result.errors, "warnings": result.warnings}


def _generate_plan_rows(db: Session, q: Quarter, seed: int | None, admin: User) -> dict:
    qlog("info", "Quarter generation started: quarter_id=%s label=%s year=%s quarter=%s admin_id=%s seed=%s", q.id, q.label, q.year, q.quarter, admin.id, seed)
    participants = quarter_participants(db, q.id)
    active_count = sum(1 for p in participants if p.is_active)
    qlog("info", "Quarter generation loaded participants: quarter_id=%s selected=%s active=%s", q.id, len(participants), active_count)
    rules = db.query(CompatibilityRule).all()
    qlog("info", "Quarter generation loaded compatibility rules: quarter_id=%s rules=%s", q.id, len(rules))
    feasibility = validate_feasibility(participants, rules, settings_for(q, seed))
    if not feasibility.valid:
        qlog("error", "Quarter generation feasibility failed: quarter_id=%s errors=%s warnings=%s", q.id, feasibility.errors, feasibility.warnings)
        raise ValueError("Unable to generate a valid distribution. " + " ".join(feasibility.errors))
    if feasibility.warnings:
        qlog("warning", "Quarter generation feasibility warnings: quarter_id=%s warnings=%s", q.id, feasibility.warnings)
    history_rows = [plan_row(r) for r in db.query(GivingPlan).filter(GivingPlan.quarter_id != q.id).order_by(GivingPlan.id.desc()).limit(200).all()]
    qlog("info", "Quarter generation loaded history: quarter_id=%s history_rows=%s", q.id, len(history_rows))
    qlog("info", "Quarter generation solver starting: quarter_id=%s", q.id)
    rows = generate_distribution(participants, rules, settings_for(q, seed), history=history_rows)
    qlog("info", "Quarter generation solver finished: quarter_id=%s allocation_rows=%s", q.id, len(rows))
    deleted = db.query(GivingPlan).filter(GivingPlan.quarter_id == q.id).delete()
    qlog("info", "Quarter generation cleared old allocation rows: quarter_id=%s deleted_rows=%s", q.id, deleted)
    for row in rows:
        db.add(GivingPlan(quarter_id=q.id, **row))
    q.generated_at = datetime.utcnow()
    return {"valid": True, "errors": [], "warnings": feasibility.warnings}


@router.post("/generate-activate")
def generate_activate_quarter(data: QuarterGenerateActivateIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    assert_not_existing_quarter(db, data.year, data.quarter)
    q = Quarter(year=data.year, quarter=data.quarter, label=data.label or f"Q{data.quarter} {data.year}", status="generating", is_active=False, is_completed=False, allocation_min=10, allocation_max=50, preferred_min_recipients=data.preferred_min_recipients, preferred_max_recipients=data.preferred_max_recipients)
    db.add(q); db.flush()
    try:
        replace_quarter_participants(db, q, data.participant_ids)
        validation = _generate_plan_rows(db, q, data.seed, admin)
        _publish_quarter(db, q, admin)
        db.commit(); db.refresh(q)
        qlog("info", "Quarter generate-activate complete: quarter_id=%s label=%s status=%s active=%s", q.id, q.label, q.status, q.is_active)
        return {"quarter": QuarterOut.model_validate(q), "plans": plan_rows(db, q.id), "validation": validation}
    except HTTPException:
        db.rollback(); logger.exception("Quarter generate-activate failed: year=%s quarter=%s label=%s", data.year, data.quarter, data.label); raise
    except ValueError as exc:
        db.rollback(); logger.exception("Quarter generate-activate failed validation: year=%s quarter=%s label=%s", data.year, data.quarter, data.label); raise HTTPException(400, str(exc))
    except Exception:
        db.rollback(); logger.exception("Quarter generate-activate crashed: year=%s quarter=%s label=%s", data.year, data.quarter, data.label); raise


@router.post("/{quarter_id}/generate")
def generate_quarter(quarter_id: int, data: QuarterGenerateIn = QuarterGenerateIn(), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    if q.status == "published": raise HTTPException(409, "Cannot regenerate a published quarter. Delete it and generate a replacement if needed.")
    try:
        validation = _generate_plan_rows(db, q, data.seed, admin)
        _publish_quarter(db, q, admin)
        db.commit(); db.refresh(q)
        qlog("info", "Quarter generation complete: quarter_id=%s label=%s status=%s active=%s", q.id, q.label, q.status, q.is_active)
        return {"quarter": QuarterOut.model_validate(q), "plans": plan_rows(db, q.id), "validation": validation}
    except HTTPException:
        db.rollback(); raise
    except ValueError as exc:
        db.rollback(); logger.exception("Quarter generation failed validation: quarter_id=%s label=%s", q.id, q.label); raise HTTPException(400, str(exc))
    except Exception:
        db.rollback(); logger.exception("Quarter generation crashed: quarter_id=%s label=%s", q.id, q.label); raise


@router.post("/{quarter_id}/regenerate")
def regenerate_quarter(quarter_id: int, data: QuarterGenerateIn = QuarterGenerateIn(), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return generate_quarter(quarter_id, data, db, admin)


@router.patch("/{quarter_id}/allocations/{allocation_id}")
def edit_allocation(quarter_id: int, allocation_id: int, data: AllocationEditIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    if q.status == "published": raise HTTPException(409, "Cannot edit a published quarter")
    row = db.get(GivingPlan, allocation_id)
    if not row or row.quarter_id != q.id: raise HTTPException(404, "Allocation not found")
    row.from_participant_id = data.from_participant_id; row.to_participant_id = data.to_participant_id; row.amount = data.amount
    db.flush()
    try:
        validate_distribution([{"from_participant_id": r.from_participant_id, "to_participant_id": r.to_participant_id, "amount": r.amount} for r in db.query(GivingPlan).filter_by(quarter_id=q.id).all()], quarter_participants(db, q.id), db.query(CompatibilityRule).all(), settings_for(q))
    except ValueError as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    db.commit()
    return plan_row(row)


@router.post("/{quarter_id}/validate-generated")
def validate_generated(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    try:
        validate_distribution([{"from_participant_id": r.from_participant_id, "to_participant_id": r.to_participant_id, "amount": r.amount} for r in db.query(GivingPlan).filter_by(quarter_id=q.id).all()], quarter_participants(db, q.id), db.query(CompatibilityRule).all(), settings_for(q))
    except ValueError as exc:
        return {"valid": False, "errors": [str(exc)], "warnings": []}
    return {"valid": True, "errors": [], "warnings": []}


def _publish_quarter(db: Session, q: Quarter, admin: User) -> None:
    year, quarter = current_calendar_quarter()
    qlog("info", "Quarter activation started: quarter_id=%s label=%s calendar_year=%s calendar_quarter=%s", q.id, q.label, year, quarter)
    q.status = "published"
    q.is_completed = False
    q.published_at = datetime.utcnow()
    q.published_by_admin_id = admin.id
    for published in db.query(Quarter).filter(Quarter.status == "published", Quarter.is_completed == False).all():  # noqa: E712
        published.is_active = published.year == year and published.quarter == quarter
    q.is_active = q.year == year and q.quarter == quarter
    qlog("info", "Quarter activation finished: quarter_id=%s label=%s active=%s", q.id, q.label, q.is_active)


@router.post("/{quarter_id}/publish")
def publish_quarter(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    validation = validate_generated(quarter_id, db, admin)
    if not validation["valid"]: raise HTTPException(400, validation["errors"][0])
    _publish_quarter(db, q, admin)
    db.commit(); db.refresh(q)
    return {"quarter": QuarterOut.model_validate(q), "plans": plan_rows(db, q.id)}


@router.post("/{quarter_id}/generate-publish")
def generate_publish_quarter(quarter_id: int, data: QuarterGenerateIn = QuarterGenerateIn(), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return generate_quarter(quarter_id, data, db, admin)


@router.post("/regenerate")
def legacy_regenerate(force: bool = False, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    y, qn = current_calendar_quarter()
    q = db.query(Quarter).filter_by(year=y, quarter=qn).first()
    if not q:
        q = Quarter(year=y, quarter=qn, label=f"Q{qn} {y}", status="created", is_active=False, is_completed=False, allocation_min=10, allocation_max=50, preferred_max_recipients=3)
        db.add(q); db.flush()
        active = db.query(Participant).filter(Participant.is_active == True).all()  # noqa: E712
        for p in active:
            db.add(QuarterParticipant(quarter_id=q.id, participant_id=p.id))
        db.commit()
    return generate_quarter(q.id, QuarterGenerateIn(), db, admin)


@router.post("/generate")
def generate(data: GenerateIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    y, qn = (data.year, data.quarter) if data.year and data.quarter else next_quarter(db)
    existing = db.query(Quarter).filter(Quarter.year == y, Quarter.quarter == qn).first()
    if not existing:
        existing = Quarter(year=y, quarter=qn, label=f"Q{qn} {y}", status="created", is_active=False, is_completed=False, allocation_min=10, allocation_max=50, preferred_max_recipients=3)
        db.add(existing); db.flush()
        for p in db.query(Participant).filter(Participant.is_active == True).all():  # noqa: E712
            db.add(QuarterParticipant(quarter_id=existing.id, participant_id=p.id))
        db.commit()
    return generate_quarter(existing.id, QuarterGenerateIn(seed=data.seed), db, admin)


@router.get("/{quarter_id}")
def detail(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    remove_legacy_draft_status(db, [q])
    db.refresh(q)
    participants = quarter_participants(db, q.id)
    return {"quarter": QuarterOut.model_validate(q), "participants": [{"id": p.id, "display_name": p.display_name, "slug": p.slug} for p in participants], "plan": plan_rows(db, q.id)}


@router.post("/{quarter_id}/complete")
def complete(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    q.is_active = False; q.is_completed = True; q.status = "completed"; db.commit()
    return {"ok": True}
