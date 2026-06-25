from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DepartmentMember, GivingPlan, PointsLedger, Quarter, Team, TeamGroup, User
from app.schemas.api import GenerateIn, QuarterOut
from app.services.auth_service import get_current_user, require_admin
from app.services.member_sync import sync_active_users_to_members
from app.services.plan_generator import generate_balanced_plan

router = APIRouter(prefix="/quarters", tags=["quarters"])


def next_quarter(db):
    last = db.query(Quarter).order_by(Quarter.year.desc(), Quarter.quarter.desc()).first()
    if not last:
        now = datetime.utcnow(); return now.year, ((now.month - 1) // 3) + 1
    return (last.year + 1, 1) if last.quarter == 4 else (last.year, last.quarter + 1)


def current_calendar_quarter() -> tuple[int, int]:
    now = datetime.utcnow()
    return now.year, ((now.month - 1) // 3) + 1


def plan_rows(db, qid):
    rows = db.query(GivingPlan).filter(GivingPlan.quarter_id == qid).all()
    return [
        {
            "id": p.id, "quarter_id": p.quarter_id,
            "from_member_id": p.from_member_id, "to_member_id": p.to_member_id,
            "from_name": p.from_member.display_name, "to_name": p.to_member.display_name,
            "amount": p.amount, "acknowledged": p.acknowledged,
        }
        for p in rows
    ]


@router.get("", response_model=list[QuarterOut])
def list_quarters(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(Quarter).order_by(Quarter.year.desc(), Quarter.quarter.desc()).all()


# NOTE: /active must be declared before /{quarter_id} so FastAPI matches it first.
@router.get("/active")
def get_active(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return the active quarter's full plan — available to all authenticated users."""
    q = (
        db.query(Quarter)
        .filter(Quarter.is_active == True, Quarter.is_completed == False)  # noqa: E712
        .order_by(Quarter.id.desc())
        .first()
    )
    if not q:
        return {"quarter": None, "plans": [], "members": []}
    members = db.query(DepartmentMember).filter(DepartmentMember.active == True).all()  # noqa: E712
    return {
        "quarter": QuarterOut.model_validate(q),
        "plans": plan_rows(db, q.id),
        "members": [{"id": m.id, "display_name": m.display_name} for m in members],
    }


def overview_tree_payload(db: Session, q: Quarter | None):
    active_groups = db.query(TeamGroup).filter(TeamGroup.is_active == True).order_by(TeamGroup.display_order, TeamGroup.name).all()  # noqa: E712
    active_teams = db.query(Team).filter(Team.is_active == True).order_by(Team.display_order, Team.name).all()  # noqa: E712
    users_by_email = {u.email.lower(): u for u in db.query(User).all()}
    members = db.query(DepartmentMember).filter(DepartmentMember.active == True).order_by(DepartmentMember.display_name).all()  # noqa: E712
    plans = db.query(GivingPlan).filter(GivingPlan.quarter_id == q.id).all() if q else []
    sent = {m.id: 0 for m in members}
    received = {m.id: 0 for m in members}
    recipients = {m.id: set() for m in members}
    sources = {m.id: set() for m in members}
    for p in plans:
        sent[p.from_member_id] = sent.get(p.from_member_id, 0) + p.amount
        received[p.to_member_id] = received.get(p.to_member_id, 0) + p.amount
        recipients.setdefault(p.from_member_id, set()).add(p.to_member_id)
        sources.setdefault(p.to_member_id, set()).add(p.from_member_id)
    return {
        "quarter": QuarterOut.model_validate(q) if q else None,
        "team_groups": [
            {"id": g.id, "name": g.name, "description": g.description, "display_order": g.display_order, "is_active": g.is_active}
            for g in active_groups
        ],
        "teams": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "colour": t.colour,
                "display_order": t.display_order,
                "is_active": t.is_active,
                "group_id": t.group_id if t.group and t.group.is_active else None,
                "group_name": t.group.name if t.group and t.group.is_active else None,
            }
            for t in active_teams
        ],
        "users": [
            {
                "member_id": m.id,
                "user_id": users_by_email.get(m.email.lower()).id if users_by_email.get(m.email.lower()) else None,
                "display_name": users_by_email.get(m.email.lower()).display_name if users_by_email.get(m.email.lower()) else m.display_name,
                "email": m.email,
                "team_id": users_by_email.get(m.email.lower()).team_id if users_by_email.get(m.email.lower()) and users_by_email.get(m.email.lower()).team and users_by_email.get(m.email.lower()).team.is_active else None,
                "team_name": users_by_email.get(m.email.lower()).team.name if users_by_email.get(m.email.lower()) and users_by_email.get(m.email.lower()).team and users_by_email.get(m.email.lower()).team.is_active else None,
                "team_colour": users_by_email.get(m.email.lower()).team.colour if users_by_email.get(m.email.lower()) and users_by_email.get(m.email.lower()).team and users_by_email.get(m.email.lower()).team.is_active else None,
                "team_group_id": users_by_email.get(m.email.lower()).team.group_id if users_by_email.get(m.email.lower()) and users_by_email.get(m.email.lower()).team and users_by_email.get(m.email.lower()).team.is_active and users_by_email.get(m.email.lower()).team.group and users_by_email.get(m.email.lower()).team.group.is_active else None,
                "team_group_name": users_by_email.get(m.email.lower()).team.group.name if users_by_email.get(m.email.lower()) and users_by_email.get(m.email.lower()).team and users_by_email.get(m.email.lower()).team.is_active and users_by_email.get(m.email.lower()).team.group and users_by_email.get(m.email.lower()).team.group.is_active else None,
                "total_points_sent": sent.get(m.id, 0),
                "total_points_received": received.get(m.id, 0),
                "recipient_count": len(recipients.get(m.id, set())),
                "incoming_allocation_count": len(sources.get(m.id, set())),
            }
            for m in members
        ],
        "allocations": [
            {
                "allocation_id": p.id,
                "quarter_id": p.quarter_id,
                "quarter": p.quarter.label,
                "source_member_id": p.from_member_id,
                "recipient_member_id": p.to_member_id,
                "source_user_id": users_by_email.get(p.from_member.email.lower()).id if users_by_email.get(p.from_member.email.lower()) else None,
                "recipient_user_id": users_by_email.get(p.to_member.email.lower()).id if users_by_email.get(p.to_member.email.lower()) else None,
                "source_name": p.from_member.display_name,
                "recipient_name": p.to_member.display_name,
                "points": p.amount,
                "acknowledged": p.acknowledged,
                "allocation_date": p.quarter.generated_at,
            }
            for p in plans
        ],
    }


@router.get("/active/overview-tree")
def active_overview_tree(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = (
        db.query(Quarter)
        .filter(Quarter.is_active == True, Quarter.is_completed == False)  # noqa: E712
        .order_by(Quarter.id.desc())
        .first()
    )
    return overview_tree_payload(db, q)


@router.post("/regenerate")
def regenerate(force: bool = False, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Admin: wipe and regenerate the current active quarter's assignments.
    Normally refused if any points have already been marked as sent.
    Pass ?force=true to override — this also clears all sent marks for the quarter."""
    q = (
        db.query(Quarter)
        .filter(Quarter.is_active == True, Quarter.is_completed == False)  # noqa: E712
        .order_by(Quarter.id.desc())
        .first()
    )
    if q and db.query(PointsLedger).filter(PointsLedger.quarter_id == q.id).first():
        if not force:
            raise HTTPException(
                409,
                "Cannot regenerate: some points have already been marked as sent for this quarter.",
            )
        # force=True: wipe the ledger (sent marks) before regenerating
        db.query(PointsLedger).filter(PointsLedger.quarter_id == q.id).delete()
        db.commit()

    # Clear plans for the active quarter so history query below excludes them
    if q:
        db.query(GivingPlan).filter(GivingPlan.quarter_id == q.id).delete()
        db.commit()

    sync_active_users_to_members(db)
    db.commit()

    members_list = (
        db.query(DepartmentMember)
        .filter(DepartmentMember.active == True)  # noqa: E712
        .order_by(DepartmentMember.id)
        .all()
    )
    if len(members_list) < 2:
        raise HTTPException(
            400,
            f"Need at least 2 active members to generate a quarter (currently have {len(members_list)}).",
        )

    hist = []
    for p in db.query(GivingPlan).join(Quarter).order_by(Quarter.year, Quarter.quarter).all():
        hist.append({
            "quarter_id": p.quarter_id,
            "quarter_index": p.quarter.year * 4 + p.quarter.quarter,
            "from_member_id": p.from_member_id,
            "to_member_id": p.to_member_id,
            "amount": p.amount,
        })

    try:
        plan = generate_balanced_plan(
            [{"id": m.id, "display_name": m.display_name, "active": m.active} for m in members_list],
            hist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    year, quarter_num = current_calendar_quarter()

    # Deactivate any previous active quarters
    for old in db.query(Quarter).filter(Quarter.is_active == True):  # noqa: E712
        old.is_active = False

    if q:
        q.is_active = True
        q.is_completed = False
        q.generated_at = datetime.utcnow()
        quarter = q
    else:
        quarter = Quarter(
            year=year, quarter=quarter_num,
            label=f"Q{quarter_num} {year}",
            is_active=True, is_completed=False,
        )
        db.add(quarter)
        db.flush()

    for r in plan:
        db.add(GivingPlan(quarter_id=quarter.id, **r))
    db.commit()

    return {"quarter": QuarterOut.model_validate(quarter), "plans": plan_rows(db, quarter.id)}


@router.post("/generate")
def generate(data: GenerateIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    y, q = (data.year, data.quarter) if data.year and data.quarter else next_quarter(db)
    existing = db.query(Quarter).filter(Quarter.year == y, Quarter.quarter == q).first()
    if existing and db.query(PointsLedger).filter(PointsLedger.quarter_id == existing.id).first():
        raise HTTPException(409, "Cannot regenerate after sends are marked")
    sync_active_users_to_members(db)
    members = db.query(DepartmentMember).filter(DepartmentMember.active == True).order_by(DepartmentMember.id).all()  # noqa: E712
    hist = []
    for p in db.query(GivingPlan).join(Quarter).order_by(Quarter.year, Quarter.quarter).all():
        hist.append({"quarter_id": p.quarter_id, "quarter_index": p.quarter.year * 4 + p.quarter.quarter, "from_member_id": p.from_member_id, "to_member_id": p.to_member_id, "amount": p.amount})
    try:
        plan = generate_balanced_plan([{"id": m.id, "display_name": m.display_name, "active": m.active} for m in members], hist, seed=data.seed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if data.preview:
        return {"quarter": {"year": y, "quarter": q, "label": f"Q{q} {y}"}, "plan": plan}
    for old in db.query(Quarter).filter(Quarter.is_active == True):  # noqa: E712
        old.is_active = False
    if existing:
        db.query(GivingPlan).filter(GivingPlan.quarter_id == existing.id).delete()
        quarter = existing; quarter.is_active = True; quarter.is_completed = False; quarter.generated_at = datetime.utcnow()
    else:
        quarter = Quarter(year=y, quarter=q, label=f"Q{q} {y}", is_active=True, is_completed=False)
        db.add(quarter); db.flush()
    for r in plan:
        db.add(GivingPlan(quarter_id=quarter.id, **r))
    db.commit()
    return {"quarter": QuarterOut.model_validate(quarter), "plan": plan_rows(db, quarter.id)}


@router.get("/{quarter_id}")
def detail(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q:
        raise HTTPException(404, "Quarter not found")
    return {"quarter": QuarterOut.model_validate(q), "plan": plan_rows(db, q.id)}


@router.post("/{quarter_id}/complete")
def complete(quarter_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.get(Quarter, quarter_id)
    if not q:
        raise HTTPException(404, "Quarter not found")
    q.is_active = False; q.is_completed = True; db.commit()
    return {"ok": True}
