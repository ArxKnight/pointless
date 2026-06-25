import pymysql
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.database import Base, SessionLocal, configure_engine
from app.models import User
from app.runtime_config import install_status, is_installed, save_install_config
from app.schemas.api import InstallDatabaseIn, InstallIn
from app.services.auth_service import hash_password
from app.services.member_sync import sync_active_users_to_members
from app.services.quarter_service import auto_generate_quarter
from app.services.schema_upgrade import ensure_team_schema
from app.services.team_seed import ensure_initial_team_data

router = APIRouter(prefix="/install", tags=["install"])
REQUIRED_TABLES = ["users", "department_members", "quarters", "giving_plans", "points_ledger"]


def _quote_identifier(value: str) -> str:
    if not value or len(value) > 64:
        raise HTTPException(status_code=400, detail="Invalid database name")
    return "`" + value.replace("`", "``") + "`"


def _base_mysql_config(db: dict) -> dict:
    return {
        "host": db["host"],
        "port": int(db["port"]),
        "user": db["username"],
        "password": db["password"],
        "connect_timeout": 10,
        "charset": "utf8mb4",
    }


def _probe_database(db: dict) -> dict:
    conn = pymysql.connect(**_base_mysql_config(db), autocommit=True)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT SCHEMA_NAME AS schema_name FROM information_schema.schemata WHERE SCHEMA_NAME = %s LIMIT 1",
                (db["database"],),
            )
            database_exists = cursor.fetchone() is not None
        schema_detected = False
        missing_tables = REQUIRED_TABLES.copy()
        existing_admin = None
        if database_exists:
            db_conn = pymysql.connect(**_base_mysql_config(db), database=db["database"])
            try:
                with db_conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    placeholders = ",".join(["%s"] * len(REQUIRED_TABLES))
                    cursor.execute(
                        f"SELECT TABLE_NAME AS table_name FROM information_schema.tables WHERE table_schema = %s AND table_name IN ({placeholders})",
                        (db["database"], *REQUIRED_TABLES),
                    )
                    existing = {row["table_name"] for row in cursor.fetchall()}
                    missing_tables = [table for table in REQUIRED_TABLES if table not in existing]
                    schema_detected = not missing_tables
                    if "users" in existing:
                        cursor.execute(
                            "SELECT id, username, display_name, email FROM users WHERE is_admin = 1 ORDER BY id ASC LIMIT 1"
                        )
                        existing_admin = cursor.fetchone()
            finally:
                db_conn.close()
        return {
            "success": True,
            "connected": True,
            "message": "Connection successful",
            "database_exists": database_exists,
            "points_schema_detected": schema_detected,
            "missing_tables": missing_tables,
            "existing_admin": existing_admin,
        }
    finally:
        conn.close()


@router.get("/status")
def status():
    return install_status()


@router.post("/test-connection")
def test_connection(data: dict):
    try:
        db = InstallDatabaseIn.model_validate(data.get("database", data)).model_dump()
        return _probe_database(db)
    except Exception as exc:
        return {"success": False, "connected": False, "error": str(exc)}


@router.post("/setup")
def setup(data: InstallIn):
    if is_installed():
        raise HTTPException(status_code=409, detail="Application is already installed")

    db = data.database.model_dump()
    try:
        try:
            conn = pymysql.connect(**_base_mysql_config(db), autocommit=True)
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS {_quote_identifier(db['database'])} "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            conn.close()
        except Exception:
            # Some hosted MySQL users cannot create databases; allow setup if the chosen DB already exists.
            conn = pymysql.connect(**_base_mysql_config(db), database=db["database"])
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not connect to MySQL or create/select database: {exc}")

    save_install_config(db)
    engine = configure_engine(force=True)
    try:
        Base.metadata.create_all(bind=engine)
        ensure_team_schema(engine)
        with engine.begin() as connection:
            connection.execute(text("SELECT 1"))
        session = SessionLocal()
        try:
            if data.reuse_existing_database:
                admin = session.query(User).filter(User.is_admin == True).order_by(User.id.asc()).first()  # noqa: E712
                if not admin:
                    raise HTTPException(status_code=400, detail="Existing database has no admin user to reuse")
            else:
                assert data.admin is not None
                admin = session.query(User).filter(
                    (User.username == data.admin.username) | (User.email == data.admin.email)
                ).first()
                if admin:
                    admin.username = data.admin.username
                    admin.display_name = data.admin.display_name
                    admin.email = data.admin.email
                    admin.password_hash = hash_password(data.admin.password)
                    admin.is_admin = True
                    admin.is_active = True
                else:
                    admin = User(
                        username=data.admin.username,
                        display_name=data.admin.display_name,
                        email=data.admin.email,
                        password_hash=hash_password(data.admin.password),
                        is_admin=True,
                        is_active=True,
                    )
                    session.add(admin)
                session.commit()
            ensure_initial_team_data(session)
            sync_active_users_to_members(session)
            session.commit()
            auto_generate_quarter(session)
        finally:
            session.close()
    except HTTPException:
        raise
    except (IntegrityError, Exception) as exc:
        raise HTTPException(status_code=500, detail=f"Database initialisation failed: {exc}")

    return {"ok": True, "status": install_status()}
