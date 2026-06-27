"""audit logs

Revision ID: 0005_audit_logs
Revises: 0004_admin_invitations
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_audit_logs'
down_revision = '0004_admin_invitations'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'audit_logs' in insp.get_table_names():
        return
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_type', sa.String(80), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('actor_username', sa.String(80), nullable=True),
        sa.Column('target_type', sa.String(80), nullable=True),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('target_name', sa.String(255), nullable=True),
        sa.Column('message', sa.String(500), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(80), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_audit_logs_event_type', 'audit_logs', ['event_type'])
    op.create_index('ix_audit_logs_actor_user_id', 'audit_logs', ['actor_user_id'])
    op.create_index('ix_audit_logs_target_type', 'audit_logs', ['target_type'])
    op.create_index('ix_audit_logs_target_id', 'audit_logs', ['target_id'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade():
    op.drop_table('audit_logs')
