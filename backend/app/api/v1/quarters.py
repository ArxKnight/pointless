from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CompatibilityRule, GivingPlan, Participant, PointsLedger, Quarter, QuarterParticipant, User
from app.schemas.api import AllocationEditIn, GenerateIn, QuarterCreateIn, QuarterOut, QuarterParticipantsIn, QuarterGenerateIn
from app.services.auth_service import get_current_user, require_admin
from app.services.participant_generator import GenerationSettings, generate_distribution, validate_distribution, validate_feasibility
from app.services.quarter_lookup import current_published_quarter

router = APIRouter(prefix="/quarters", tags=["quarters"])


def next_quarter(db):
    last = db.query(Quarter).order_by(Quarter.year.desc(), Quarter.quarter.desc()).first()
    if not last:
        now = datetime.utcnow(); return now.year, ((now.month - 1) // 3) + 1
    return (last.year + 1, 1) if last.quarter == 4 else (last.year, last.quarter + 1)


def current_calendar_quarter() -> tuple[int, int]:
    now = datetime.utcnow()
    return now.year, ((now.month - 1) // 3) + 1


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
def list_quarters(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(Quarter).order_by(Quarter.year.desc(), Quarter.quarter.desc()).all()


@router.post("", response_model=QuarterOut)
def create_quarter(data: QuarterCreateIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.query(Quarter).filter_by(year=data.year, quarter=data.quarter).first():
        raise HTTPException(409, "Quarter already exists")
    q = Quarter(
        year=data.year,
        quarter=data.quarter,
        label=data.label or f"Q{data.quarter} {data.year}",
        status="draft",
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


@router.get("/active/overview-tree")
def active_overview_tree(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = current_published_quarter(db)
    participants = quarter_participants(db, q.id) if q else []
    plans = db.query(GivingPlan).filter(GivingPlan.quarter_id == q.id).all() if q else []
    sent = {p.id: 0 for p in participants}; received = {p.id: 0 for p in participants}
    for row in plans:
        sent[row.from_participant_id] = sent.get(row.from_participant_id, 0) + row.amount
        received[row.to_participant_id] = received.get(row.to_participant_id, 0) + row.amount
    return {
        "quarter": QuarterOut.model_validate(q) if q else None,
        "team_groups": [],
        "teams": [],
        "users": [{"member_id": p.id, "user_id": None, "display_name": p.display_name, "email": "", "team_id": None, "team_name": None, "team_colour": None, "team_group_id": None, "team_group_name": None, "total_points_sent": sent.get(p.id, 0), "total_points_received": received.get(p.id, 0), "recipient_count": 0, "incoming_allocation_count": 0} for p in participants],
        "allocations": [{"allocation_id": r.id, "quarter_id": r.quarter_id, "quarter": q.label if q else "", "source_member_id": r.from_participant_id, "recipient_member_id": r.to_participant_id, "source_user_id": None, "recipient_user_id": None, "source_name": r.from_participant.display_name, "recipient_name": r.to_participant.display_name, "points": r.amount, "acknowledged": r.acknowledged, "allocation_date": q.published_at if q else None} for r in plans],
    }


@router.put("/{quarter_id}/participants")
def set_quarter_participants(quarter_id: int, data: QuarterParticipantsIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    if q.status == "published": raise HTTPException(409, "Cannot change participants on a published quarter")
    ids = sorted(set(data.participant_ids))
    participants = db.query(Participant).filter(Participant.id.in_(ids)).all() if ids else []
    if len(participants) != len(ids): raise HTTPException(404, "One or more participants were not found")
    db.query(QuarterParticipant).filter_by(quarter_id=q.id).delete()
    for pid in ids:
        db.add(QuarterParticipant(quarter_id=q.id, participant_id=pid))
    db.commit()
    return {"ok": True, "participant_count": len(ids)}


@router.post("/{quarter_id}/validate")
def validate_quarter(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    result = validate_feasibility(quarter_participants(db, q.id), db.query(CompatibilityRule).all(), settings_for(q))
    return {"valid": result.valid, "errors": result.errors, "warnings": result.warnings}


@router.post("/{quarter_id}/generate")
def generate_quarter(quarter_id: int, data: QuarterGenerateIn = QuarterGenerateIn(), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    if q.status == "published": raise HTTPException(409, "Cannot regenerate a published quarter")
    participants = quarter_participants(db, q.id)
    try:
        rows = generate_distribution(participants, db.query(CompatibilityRule).all(), settings_for(q, data.seed), history=[plan_row(r) for r in db.query(GivingPlan).filter(GivingPlan.quarter_id != q.id).order_by(GivingPlan.id.desc()).limit(200).all()])
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    db.query(GivingPlan).filter(GivingPlan.quarter_id == q.id).delete()
    for row in rows:
        db.add(GivingPlan(quarter_id=q.id, **row))
    q.status = "draft"; q.generated_at = datetime.utcnow()
    db.commit()
    return {"quarter": QuarterOut.model_validate(q), "plans": plan_rows(db, q.id), "validation": {"valid": True, "errors": [], "warnings": []}}


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


@router.post("/{quarter_id}/validate-draft")
def validate_draft(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    try:
        validate_distribution([{"from_participant_id": r.from_participant_id, "to_participant_id": r.to_participant_id, "amount": r.amount} for r in db.query(GivingPlan).filter_by(quarter_id=q.id).all()], quarter_participants(db, q.id), db.query(CompatibilityRule).all(), settings_for(q))
    except ValueError as exc:
        return {"valid": False, "errors": [str(exc)], "warnings": []}
    return {"valid": True, "errors": [], "warnings": []}


@router.post("/{quarter_id}/publish")
def publish_quarter(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    validation = validate_draft(quarter_id, db, admin)
    if not validation["valid"]: raise HTTPException(400, validation["errors"][0])
    for old in db.query(Quarter).filter(Quarter.status == "published").all():
        old.is_active = False
    q.status = "published"; q.is_active = True; q.is_completed = False; q.published_at = datetime.utcnow(); q.published_by_admin_id = admin.id
    db.commit(); db.refresh(q)
    return {"quarter": QuarterOut.model_validate(q), "plans": plan_rows(db, q.id)}


@router.post("/regenerate")
def legacy_regenerate(force: bool = False, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    y, qn = current_calendar_quarter()
    q = db.query(Quarter).filter_by(year=y, quarter=qn).first()
    if not q:
        q = Quarter(year=y, quarter=qn, label=f"Q{qn} {y}", status="draft", is_active=False, is_completed=False, allocation_min=10, allocation_max=50, preferred_max_recipients=3)
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
        existing = Quarter(year=y, quarter=qn, label=f"Q{qn} {y}", status="draft", is_active=False, is_completed=False, allocation_min=10, allocation_max=50, preferred_max_recipients=3)
        db.add(existing); db.flush()
        for p in db.query(Participant).filter(Participant.is_active == True).all():  # noqa: E712
            db.add(QuarterParticipant(quarter_id=existing.id, participant_id=p.id))
        db.commit()
    return generate_quarter(existing.id, QuarterGenerateIn(seed=data.seed), db, admin)


@router.get("/{quarter_id}")
def detail(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    participants = quarter_participants(db, q.id)
    return {"quarter": QuarterOut.model_validate(q), "participants": [{"id": p.id, "display_name": p.display_name, "slug": p.slug} for p in participants], "plan": plan_rows(db, q.id)}


@router.post("/{quarter_id}/complete")
def complete(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q: raise HTTPException(404, "Quarter not found")
    q.is_active = False; q.is_completed = True; q.status = "completed"; db.commit()
    return {"ok": True}
