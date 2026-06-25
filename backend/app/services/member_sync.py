from sqlalchemy.orm import Session

from app.models import DepartmentMember, User


def sync_active_users_to_members(db: Session) -> int:
    """Ensure every active user also exists as an active department member.

    Department members are the participant pool used by quarter generation and
    giving trees. User accounts are login identities. This sync keeps the
    participant pool in line with accounts found in the database, including
    users restored from an existing DB during installer reuse.
    """
    created = 0
    active_users = db.query(User).filter(User.is_active == True).order_by(User.id).all()  # noqa: E712
    for user in active_users:
        member = db.query(DepartmentMember).filter(DepartmentMember.email == user.email).first()
        if member:
            member.display_name = user.display_name
            member.active = True
            continue
        db.add(
            DepartmentMember(
                display_name=user.display_name,
                email=user.email,
                added_by=user.id,
                active=True,
            )
        )
        created += 1
    db.flush()
    return created
