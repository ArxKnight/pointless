from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class DepartmentMember(Base):
    __tablename__ = "department_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Quarter(Base):
    __tablename__ = "quarters"
    __table_args__ = (UniqueConstraint("year", "quarter", name="uq_year_quarter"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    quarter: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(20))
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

class GivingPlan(Base):
    __tablename__ = "giving_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quarter_id: Mapped[int] = mapped_column(ForeignKey("quarters.id"), index=True)
    from_member_id: Mapped[int] = mapped_column(ForeignKey("department_members.id"), index=True)
    to_member_id: Mapped[int] = mapped_column(ForeignKey("department_members.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    quarter = relationship("Quarter")
    from_member = relationship("DepartmentMember", foreign_keys=[from_member_id])
    to_member = relationship("DepartmentMember", foreign_keys=[to_member_id])

class PointsLedger(Base):
    __tablename__ = "points_ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quarter_id: Mapped[int] = mapped_column(ForeignKey("quarters.id"), index=True)
    from_member_id: Mapped[int] = mapped_column(ForeignKey("department_members.id"), index=True)
    to_member_id: Mapped[int] = mapped_column(ForeignKey("department_members.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    marked_sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    marked_sent_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
