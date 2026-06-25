from fastapi import FastAPI
import logging
import sys
from datetime import datetime
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, SessionLocal, configure_engine
from app.models import DepartmentMember, GivingPlan, Quarter, User
from app.runtime_config import is_installed
from app.services.auth_service import hash_password
from app.services.member_sync import sync_active_users_to_members
from app.services.plan_generator import generate_balanced_plan
from app.api.v1 import auth, members, quarters, plans, analytics, install

app=FastAPI(title="Quarterly Points Distribution", version="1.0.0")
logger = logging.getLogger("quarterly_points.startup")
app.add_middleware(CORSMiddleware, allow_origins=[], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(install.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(quarters.router, prefix="/api")
app.include_router(plans.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")

FRONTEND_ROOT = Path("/usr/share/nginx/html")


def _current_quarter_label() -> tuple[int, int]:
    now = datetime.utcnow()
    return now.year, ((now.month - 1) // 3) + 1


def _auto_generate_quarter(db) -> None:
    """Auto-generate the current calendar quarter if no active quarter exists."""
    active = db.query(Quarter).filter(Quarter.is_active == True, Quarter.is_completed == False).first()  # noqa: E712
    if active:
        return  # already have one

    year, q = _current_quarter_label()
    existing = db.query(Quarter).filter(Quarter.year == year, Quarter.quarter == q).first()
    if existing:
        # Quarter row exists but is not active; reactivate it
        for old in db.query(Quarter).filter(Quarter.is_active == True):  # noqa: E712
            old.is_active = False
        existing.is_active = True
        existing.is_completed = False
        db.commit()
        logger.info(f"[quarterly-points] Reactivated existing quarter Q{q} {year}")
        return

    # Build member list
    sync_active_users_to_members(db)
    db.commit()
    members_list = db.query(DepartmentMember).filter(DepartmentMember.active == True).order_by(DepartmentMember.id).all()  # noqa: E712
    if len(members_list) < 2:
        logger.warning("[quarterly-points] Auto-generate skipped: fewer than 2 active members")
        return

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
        logger.error(f"[quarterly-points] Auto-generate failed: {exc}")
        return

    # Deactivate any previous active quarters
    for old in db.query(Quarter).filter(Quarter.is_active == True):  # noqa: E712
        old.is_active = False

    quarter = Quarter(year=year, quarter=q, label=f"Q{q} {year}", is_active=True, is_completed=False)
    db.add(quarter)
    db.flush()
    for r in plan:
        db.add(GivingPlan(quarter_id=quarter.id, **r))
    db.commit()
    logger.info(f"[quarterly-points] Auto-generated quarter Q{q} {year} with {len(plan)} plan rows")


@app.on_event("startup")
def startup():
    if not is_installed():
        message = "First-run installer mode: no /data/config.json or DATABASE_URL found. Open the web UI to configure MySQL and create the admin user."
        logger.warning(message)
        print(f"[quarterly-points] {message}", file=sys.stderr, flush=True)
        return
    message = "Installed mode: saved database configuration found; initialising database models if needed."
    logger.info(message)
    print(f"[quarterly-points] {message}", file=sys.stderr, flush=True)
    engine = configure_engine()
    if engine is None:
        return
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).first() and settings.first_admin_username and settings.first_admin_password:
            db.add(User(username=settings.first_admin_username, display_name="Administrator", email=settings.first_admin_email, password_hash=hash_password(settings.first_admin_password), is_admin=True, is_active=True))
            db.commit()
        sync_active_users_to_members(db)
        db.commit()
        _auto_generate_quarter(db)
    finally:
        db.close()


@app.get("/api/health")
def health(): return {"ok": True, "installed": is_installed()}


if (FRONTEND_ROOT / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ROOT / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    requested = (FRONTEND_ROOT / full_path).resolve()
    root = FRONTEND_ROOT.resolve()
    if requested.is_file() and root in requested.parents:
        return FileResponse(requested)
    index = FRONTEND_ROOT / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend assets not found")
