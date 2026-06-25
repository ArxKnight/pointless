from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from fastapi import HTTPException
from .runtime_config import database_url, is_installed

_engine = None
SessionLocal = sessionmaker(autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or database_url()
    if not url:
        return None
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def configure_engine(force: bool = False):
    global _engine
    if _engine is not None and not force:
        return _engine
    url = database_url()
    if not url:
        _engine = None
        return None
    _engine = make_engine(url)
    SessionLocal.configure(bind=_engine)
    return _engine


def get_engine_required():
    engine = configure_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Application is not installed yet")
    return engine


def get_db():
    if not is_installed():
        raise HTTPException(status_code=503, detail="Application is not installed yet")
    configure_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
