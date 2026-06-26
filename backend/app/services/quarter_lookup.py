from sqlalchemy.orm import Query, Session

from app.models import Quarter


def current_published_quarter_query(db: Session) -> Query:
    """Return a dialect-portable query for the current published quarter.

    Avoid ``NULLS LAST`` because MySQL/MariaDB reject that PostgreSQL-style
    ordering syntax. Published rows should have ``published_at`` populated; the
    id fallback keeps legacy rows deterministic.
    """
    return (
        db.query(Quarter)
        .filter(Quarter.status == "published")
        .order_by(Quarter.published_at.desc(), Quarter.id.desc())
    )


def current_published_quarter(db: Session) -> Quarter | None:
    return current_published_quarter_query(db).first()
