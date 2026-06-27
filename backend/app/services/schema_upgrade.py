from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _add_column(conn, table: str, definition: str):
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {definition}"))


def _create_index(conn, table: str, name: str, columns: str, dialect: str):
    if dialect == "mysql":
        try:
            conn.execute(text(f"CREATE INDEX {name} ON {table} ({columns})"))
        except Exception:
            pass
    else:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"))


def ensure_team_schema(engine: Engine) -> None:
    """Apply tiny safe upgrades for installs that use create_all instead of Alembic."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "team_id" not in user_columns:
        dialect = engine.dialect.name
        with engine.begin() as conn:
            if dialect == "mysql":
                conn.execute(text("ALTER TABLE users ADD COLUMN team_id INTEGER NULL"))
                conn.execute(text("CREATE INDEX ix_users_team_id ON users (team_id)"))
                try:
                    conn.execute(text("ALTER TABLE users ADD CONSTRAINT fk_users_team_id_teams FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL"))
                except Exception:
                    pass
            elif dialect == "sqlite":
                conn.execute(text("ALTER TABLE users ADD COLUMN team_id INTEGER NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_team_id ON users (team_id)"))
            else:
                conn.execute(text("ALTER TABLE users ADD COLUMN team_id INTEGER NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_team_id ON users (team_id)"))


def ensure_participant_schema(engine: Engine) -> None:
    """Safe additive schema upgrades for the participant-based workflow.

    Base.metadata.create_all creates new tables, while this function adds missing
    columns to existing quarter/allocation tables. It never drops old member/team
    data, so production history remains recoverable.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if "quarters" in tables:
            columns = {c["name"] for c in inspector.get_columns("quarters")}
            additions = {
                "status": "status VARCHAR(20) DEFAULT 'published'",
                "created_at": "created_at DATETIME NULL",
                "published_at": "published_at DATETIME NULL",
                "allocation_min": "allocation_min INTEGER DEFAULT 10",
                "allocation_max": "allocation_max INTEGER DEFAULT 50",
                "preferred_min_recipients": "preferred_min_recipients INTEGER DEFAULT 2",
                "preferred_max_recipients": "preferred_max_recipients INTEGER DEFAULT 3",
                "published_by_admin_id": "published_by_admin_id INTEGER NULL",
            }
            for name, ddl in additions.items():
                if name not in columns:
                    _add_column(conn, "quarters", ddl)
            if "status" not in columns:
                conn.execute(text("UPDATE quarters SET status = CASE WHEN is_completed = 1 THEN 'completed' ELSE 'published' END WHERE status IS NULL OR status = 'draft'"))
            _create_index(conn, "quarters", "ix_quarters_status", "status", dialect)
        if "giving_plans" in tables:
            columns = {c["name"] for c in inspector.get_columns("giving_plans")}
            if "from_participant_id" not in columns:
                _add_column(conn, "giving_plans", "from_participant_id INTEGER NULL")
                _create_index(conn, "giving_plans", "ix_giving_plans_from_participant_id", "from_participant_id", dialect)
            if "to_participant_id" not in columns:
                _add_column(conn, "giving_plans", "to_participant_id INTEGER NULL")
                _create_index(conn, "giving_plans", "ix_giving_plans_to_participant_id", "to_participant_id", dialect)
        if "points_ledger" in tables:
            columns = {c["name"] for c in inspector.get_columns("points_ledger")}
            if "from_participant_id" not in columns:
                _add_column(conn, "points_ledger", "from_participant_id INTEGER NULL")
                _create_index(conn, "points_ledger", "ix_points_ledger_from_participant_id", "from_participant_id", dialect)
            if "to_participant_id" not in columns:
                _add_column(conn, "points_ledger", "to_participant_id INTEGER NULL")
                _create_index(conn, "points_ledger", "ix_points_ledger_to_participant_id", "to_participant_id", dialect)


def ensure_admin_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    dialect = engine.dialect.name
    if "users" in tables:
        columns = {c["name"] for c in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "is_super_admin" not in columns:
                _add_column(conn, "users", "is_super_admin BOOLEAN DEFAULT 0")
                _create_index(conn, "users", "ix_users_is_super_admin", "is_super_admin", dialect)
            conn.execute(text("UPDATE users SET is_super_admin = 1 WHERE is_admin = 1 AND id = (SELECT first_admin.id FROM (SELECT MIN(id) AS id FROM users WHERE is_admin = 1) AS first_admin) AND NOT EXISTS (SELECT existing_admin.id FROM (SELECT id FROM users WHERE is_super_admin = 1 AND is_active = 1 LIMIT 1) AS existing_admin)"))
            if "last_login_at" not in columns:
                _add_column(conn, "users", "last_login_at DATETIME NULL")
    if "admin_invitations" not in tables:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE admin_invitations (id INTEGER PRIMARY KEY AUTO_INCREMENT, token_hash VARCHAR(128) NOT NULL UNIQUE, invitee_name VARCHAR(160) NOT NULL, invitee_email VARCHAR(255) NULL, created_by_admin_id INTEGER NULL, created_at DATETIME NOT NULL, expires_at DATETIME NOT NULL, used_at DATETIME NULL, used_by_admin_id INTEGER NULL, revoked_at DATETIME NULL)" if dialect == "mysql" else "CREATE TABLE IF NOT EXISTS admin_invitations (id INTEGER PRIMARY KEY, token_hash VARCHAR(128) NOT NULL UNIQUE, invitee_name VARCHAR(160) NOT NULL, invitee_email VARCHAR(255) NULL, created_by_admin_id INTEGER NULL, created_at DATETIME NOT NULL, expires_at DATETIME NOT NULL, used_at DATETIME NULL, used_by_admin_id INTEGER NULL, revoked_at DATETIME NULL)"))
            _create_index(conn, "admin_invitations", "ix_admin_invitations_token_hash", "token_hash", dialect)
            _create_index(conn, "admin_invitations", "ix_admin_invitations_created_by_admin_id", "created_by_admin_id", dialect)


def ensure_password_reset_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    dialect = engine.dialect.name
    if "password_reset_tokens" not in tables:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE password_reset_tokens (id INTEGER PRIMARY KEY AUTO_INCREMENT, token_hash VARCHAR(128) NOT NULL UNIQUE, user_id INTEGER NOT NULL, created_at DATETIME NOT NULL, expires_at DATETIME NOT NULL, used_at DATETIME NULL, requested_ip VARCHAR(80) NULL, INDEX ix_password_reset_tokens_token_hash (token_hash), INDEX ix_password_reset_tokens_user_id (user_id), INDEX ix_password_reset_tokens_expires_at (expires_at))" if dialect == "mysql" else "CREATE TABLE IF NOT EXISTS password_reset_tokens (id INTEGER PRIMARY KEY, token_hash VARCHAR(128) NOT NULL UNIQUE, user_id INTEGER NOT NULL, created_at DATETIME NOT NULL, expires_at DATETIME NOT NULL, used_at DATETIME NULL, requested_ip VARCHAR(80) NULL)"))
            if dialect != "mysql":
                _create_index(conn, "password_reset_tokens", "ix_password_reset_tokens_token_hash", "token_hash", dialect)
                _create_index(conn, "password_reset_tokens", "ix_password_reset_tokens_user_id", "user_id", dialect)
                _create_index(conn, "password_reset_tokens", "ix_password_reset_tokens_expires_at", "expires_at", dialect)


def ensure_audit_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "audit_logs" in tables:
        return
    dialect = engine.dialect.name
    pk = "INTEGER PRIMARY KEY AUTO_INCREMENT" if dialect == "mysql" else "INTEGER PRIMARY KEY"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE audit_logs (id {pk}, event_type VARCHAR(80) NOT NULL, actor_user_id INTEGER NULL, actor_username VARCHAR(80) NULL, target_type VARCHAR(80) NULL, target_id INTEGER NULL, target_name VARCHAR(255) NULL, message VARCHAR(500) NOT NULL, metadata_json TEXT NULL, ip_address VARCHAR(80) NULL, created_at DATETIME NOT NULL)"))
        _create_index(conn, "audit_logs", "ix_audit_logs_event_type", "event_type", dialect)
        _create_index(conn, "audit_logs", "ix_audit_logs_actor_user_id", "actor_user_id", dialect)
        _create_index(conn, "audit_logs", "ix_audit_logs_target_type", "target_type", dialect)
        _create_index(conn, "audit_logs", "ix_audit_logs_target_id", "target_id", dialect)
        _create_index(conn, "audit_logs", "ix_audit_logs_created_at", "created_at", dialect)
