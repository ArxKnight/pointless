"""Shared quarter auto-generation logic used by startup and the install endpoint."""
import logging
from datetime import datetime

from app.models import DepartmentMember, GivingPlan, Quarter
from app.services.member_sync import sync_active_users_to_members
from app.services.plan_generator import generate_balanced_plan

logger = logging.getLogger("pointless.quarter_service")


def _current_quarter() -> tuple[int, int]:
    now = datetime.utcnow()
    return now.year, ((now.month - 1) // 3) + 1


def auto_generate_quarter(db) -> bool:
    """Auto-generate the current calendar quarter if no active quarter exists.

    Returns True if a new quarter was created or an existing one reactivated,
    False if one already existed or generation was not possible.
    """
    year, q = _current_quarter()

    # Already have an active quarter — nothing to do
    active = db.query(Quarter).filter(
        Quarter.is_active == True, Quarter.is_completed == False  # noqa: E712
    ).first()
    if active:
        logger.info(f"[quarter_service] Active quarter already exists: {active.label}")
        return False

    existing = db.query(Quarter).filter(Quarter.year == year, Quarter.quarter == q).first()
    if existing:
        # Quarter row exists but is inactive — just reactivate it
        for old in db.query(Quarter).filter(Quarter.is_active == True):  # noqa: E712
            old.is_active = False
        existing.is_active = True
        existing.is_completed = False
        db.commit()
        logger.info(f"[quarter_service] Reactivated existing quarter {existing.label}")
        return True

    # Sync members first so newly-created users appear
    sync_active_users_to_members(db)
    db.commit()

    members_list = (
        db.query(DepartmentMember)
        .filter(DepartmentMember.active == True)  # noqa: E712
        .order_by(DepartmentMember.id)
        .all()
    )
    if len(members_list) < 2:
        logger.warning(
            f"[quarter_service] Auto-generate skipped: only {len(members_list)} active member(s), need at least 2"
        )
        return False

    # Build history for duplicate-avoidance
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
        logger.error(f"[quarter_service] Auto-generate failed: {exc}")
        return False

    # Deactivate any previous active quarters
    for old in db.query(Quarter).filter(Quarter.is_active == True):  # noqa: E712
        old.is_active = False

    quarter = Quarter(year=year, quarter=q, label=f"Q{q} {year}", is_active=True, is_completed=False)
    db.add(quarter)
    db.flush()
    for r in plan:
        db.add(GivingPlan(quarter_id=quarter.id, **r))
    db.commit()
    logger.info(
        f"[quarter_service] Auto-generated Q{q} {year} with {len(plan)} plan rows for {len(members_list)} members"
    )
    return True
