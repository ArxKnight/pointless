from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import DepartmentMember, User
from app.services.auth_service import hash_password
from app.services.member_sync import sync_active_users_to_members


def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def make_user(username, email, display_name, active=True):
    return User(
        username=username,
        email=email,
        display_name=display_name,
        password_hash=hash_password("password123"),
        is_admin=False,
        is_active=active,
    )


def test_sync_active_users_to_members_creates_missing_active_department_members():
    db = session()
    db.add(make_user("alex", "alex@example.com", "Alex"))
    db.add(make_user("sam", "sam@example.com", "Sam"))
    db.add(make_user("inactive", "inactive@example.com", "Inactive", active=False))
    db.commit()

    created = sync_active_users_to_members(db)

    members = db.query(DepartmentMember).order_by(DepartmentMember.email).all()
    assert created == 2
    assert [(m.display_name, m.email, m.active) for m in members] == [
        ("Alex", "alex@example.com", True),
        ("Sam", "sam@example.com", True),
    ]


def test_sync_active_users_to_members_reactivates_existing_user_member_without_duplicates():
    db = session()
    db.add(make_user("alex", "alex@example.com", "Alex New"))
    db.add(DepartmentMember(display_name="Alex Old", email="alex@example.com", active=False))
    db.commit()

    created = sync_active_users_to_members(db)
    sync_active_users_to_members(db)

    members = db.query(DepartmentMember).all()
    assert created == 0
    assert len(members) == 1
    assert members[0].display_name == "Alex New"
    assert members[0].active is True
