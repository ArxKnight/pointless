from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TeamGroup(Base):
    __tablename__ = "team_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="group", foreign_keys="Team.group_id")


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    colour: Mapped[str] = mapped_column(String(20), default="#6366f1")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("team_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    group: Mapped["TeamGroup | None"] = relationship("TeamGroup", back_populates="teams", foreign_keys=[group_id])
    members: Mapped[list["User"]] = relationship("User", back_populates="team", foreign_keys="User.team_id")


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
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    team: Mapped["Team | None"] = relationship("Team", back_populates="members", foreign_keys=[team_id])


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
