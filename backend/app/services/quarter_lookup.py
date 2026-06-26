from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.models import Quarter


def current_calendar_quarter(now: datetime | None = None) -> tuple[int, int]:
    now = now or datetime.utcnow()
    return now.year, ((now.month - 1) // 3) + 1


def current_published_quarter_query(db: Session) -> Query:
    """Return a dialect-portable query for the currently live published quarter.

    A quarter can be generated and published ahead of time, but participant
    public trees should only show it when its calendar quarter is live. Avoid
    ``NULLS LAST`` because MySQL/MariaDB reject that PostgreSQL-style ordering.
    """
    year, quarter = current_calendar_quarter()
    return (
        db.query(Quarter)
        .filter(
            Quarter.year == year,
            Quarter.quarter == quarter,
            or_(Quarter.status == "published", (Quarter.is_active == True) & (Quarter.published_at.isnot(None))),  # noqa: E712
            Quarter.is_completed == False,  # noqa: E712
        )
        .order_by(Quarter.is_active.desc(), Quarter.published_at.desc(), Quarter.id.desc())
    )


def current_published_quarter(db: Session) -> Quarter | None:
    return current_published_quarter_query(db).first()
