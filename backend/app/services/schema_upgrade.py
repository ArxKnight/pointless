from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


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
                    # Some MySQL variants/permissions reject late FK creation; the API still validates IDs.
                    pass
            elif dialect == "sqlite":
                conn.execute(text("ALTER TABLE users ADD COLUMN team_id INTEGER NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_team_id ON users (team_id)"))
            else:
                conn.execute(text("ALTER TABLE users ADD COLUMN team_id INTEGER NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_team_id ON users (team_id)"))
