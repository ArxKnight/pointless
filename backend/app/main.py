from fastapi import FastAPI
import logging
import sys
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, SessionLocal, configure_engine
from app.models import User
from app.runtime_config import is_installed
from app.services.auth_service import hash_password
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
    db=SessionLocal()
    try:
        if not db.query(User).first() and settings.first_admin_username and settings.first_admin_password:
            db.add(User(username=settings.first_admin_username,display_name="Administrator",email=settings.first_admin_email,password_hash=hash_password(settings.first_admin_password),is_admin=True,is_active=True)); db.commit()
    finally: db.close()

@app.get("/api/health")
def health(): return {"ok":True, "installed": is_installed()}
