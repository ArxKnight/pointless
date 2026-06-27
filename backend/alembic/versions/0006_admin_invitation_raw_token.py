"""store recoverable pending admin invite URLs

Revision ID: 0006_admin_invitation_raw_token
Revises: 0005_audit_logs
Create Date: 2026-06-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_admin_invitation_raw_token"
down_revision = "0005_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_invitations", sa.Column("raw_token", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_invitations", "raw_token")
