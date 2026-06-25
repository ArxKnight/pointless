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
                "status": "status VARCHAR(20) DEFAULT 'draft'",
                "created_at": "created_at DATETIME NULL",
                "published_at": "published_at DATETIME NULL",
                "allocation_min": "allocation_min INTEGER DEFAULT 5",
                "allocation_max": "allocation_max INTEGER DEFAULT 25",
                "preferred_min_recipients": "preferred_min_recipients INTEGER DEFAULT 2",
                "preferred_max_recipients": "preferred_max_recipients INTEGER DEFAULT 5",
            }
            for name, ddl in additions.items():
                if name not in columns:
                    _add_column(conn, "quarters", ddl)
            if "status" not in columns:
                conn.execute(text("UPDATE quarters SET status = CASE WHEN is_completed = 1 THEN 'completed' WHEN is_active = 1 THEN 'published' ELSE 'draft' END WHERE status IS NULL"))
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
