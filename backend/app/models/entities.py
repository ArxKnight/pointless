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
    """Administrator login account.

    Distribution participants are stored separately in Participant and do not
    require usernames, passwords, emails or roles.
    """

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    team: Mapped["Team | None"] = relationship("Team", back_populates="members", foreign_keys=[team_id])


class DepartmentMember(Base):
    """Legacy distribution member table retained for safe migration/history."""

    __tablename__ = "department_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160), index=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    legacy_member_id: Mapped[int | None] = mapped_column(ForeignKey("department_members.id"), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ParticipantSlugRedirect(Base):
    __tablename__ = "participant_slug_redirects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    old_slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompatibilityRule(Base):
    __tablename__ = "compatibility_rules"
    __table_args__ = (UniqueConstraint("from_participant_id", "to_participant_id", name="uq_compatibility_pair"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    to_participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompatibilityGroup(Base):
    __tablename__ = "compatibility_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompatibilityGroupMember(Base):
    __tablename__ = "compatibility_group_members"
    __table_args__ = (UniqueConstraint("group_id", "participant_id", name="uq_compat_group_member"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("compatibility_groups.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)


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
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    allocation_min: Mapped[int] = mapped_column(Integer, default=10)
    allocation_max: Mapped[int] = mapped_column(Integer, default=50)
    preferred_min_recipients: Mapped[int] = mapped_column(Integer, default=2)
    preferred_max_recipients: Mapped[int] = mapped_column(Integer, default=3)


class QuarterParticipant(Base):
    __tablename__ = "quarter_participants"
    __table_args__ = (UniqueConstraint("quarter_id", "participant_id", name="uq_quarter_participant"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quarter_id: Mapped[int] = mapped_column(ForeignKey("quarters.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    participant = relationship("Participant")


class GivingPlan(Base):
    __tablename__ = "giving_plans"
    __table_args__ = (UniqueConstraint("quarter_id", "from_participant_id", "to_participant_id", name="uq_giving_plan_quarter_participant_pair"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quarter_id: Mapped[int] = mapped_column(ForeignKey("quarters.id"), index=True)
    from_member_id: Mapped[int | None] = mapped_column(ForeignKey("department_members.id"), nullable=True, index=True)
    to_member_id: Mapped[int | None] = mapped_column(ForeignKey("department_members.id"), nullable=True, index=True)
    from_participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"), nullable=True, index=True)
    to_participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"), nullable=True, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    quarter = relationship("Quarter")
    from_member = relationship("DepartmentMember", foreign_keys=[from_member_id])
    to_member = relationship("DepartmentMember", foreign_keys=[to_member_id])
    from_participant = relationship("Participant", foreign_keys=[from_participant_id])
    to_participant = relationship("Participant", foreign_keys=[to_participant_id])


class AdminInvitation(Base):
    __tablename__ = "admin_invitations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    invitee_name: Mapped[str] = mapped_column(String(160))
    invitee_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)




class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requested_ip: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user = relationship("User")

class PointsLedger(Base):
    __tablename__ = "points_ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quarter_id: Mapped[int] = mapped_column(ForeignKey("quarters.id"), index=True)
    from_member_id: Mapped[int | None] = mapped_column(ForeignKey("department_members.id"), nullable=True, index=True)
    to_member_id: Mapped[int | None] = mapped_column(ForeignKey("department_members.id"), nullable=True, index=True)
    from_participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"), nullable=True, index=True)
    to_participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"), nullable=True, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    marked_sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    marked_sent_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
