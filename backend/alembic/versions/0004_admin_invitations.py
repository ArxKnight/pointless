"""admin invitations and fixed allocation defaults

Revision ID: 0004_admin_invitations
Revises: 0003_participants
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_admin_invitations'
down_revision = '0003_participants'
branch_labels = None
depends_on = None


def _has_column(bind, table, column):
    insp = sa.inspect(bind)
    return table in insp.get_table_names() and column in {c['name'] for c in insp.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, 'users', 'is_super_admin'):
        op.add_column('users', sa.Column('is_super_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
        op.create_index('ix_users_is_super_admin', 'users', ['is_super_admin'])
        bind.execute(sa.text("UPDATE users SET is_super_admin = 1 WHERE is_admin = 1 AND id = (SELECT MIN(id) FROM users WHERE is_admin = 1)"))
    if not _has_column(bind, 'users', 'last_login_at'):
        op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    if not _has_column(bind, 'quarters', 'published_by_admin_id'):
        op.add_column('quarters', sa.Column('published_by_admin_id', sa.Integer(), nullable=True))
        op.create_index('ix_quarters_published_by_admin_id', 'quarters', ['published_by_admin_id'])
        if bind.dialect.name != 'sqlite':
            try:
                op.create_foreign_key('fk_quarters_published_by_admin_id_users', 'quarters', 'users', ['published_by_admin_id'], ['id'], ondelete='SET NULL')
            except Exception:
                pass
    insp = sa.inspect(bind)
    if 'admin_invitations' not in insp.get_table_names():
        op.create_table(
            'admin_invitations',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('token_hash', sa.String(128), nullable=False),
            sa.Column('invitee_name', sa.String(160), nullable=False),
            sa.Column('invitee_email', sa.String(255), nullable=True),
            sa.Column('created_by_admin_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('used_by_admin_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_admin_invitations_token_hash', 'admin_invitations', ['token_hash'], unique=True)
        op.create_index('ix_admin_invitations_created_by_admin_id', 'admin_invitations', ['created_by_admin_id'])
        op.create_index('ix_admin_invitations_used_by_admin_id', 'admin_invitations', ['used_by_admin_id'])


def downgrade():
    op.drop_table('admin_invitations')
    try:
        op.drop_index('ix_quarters_published_by_admin_id', table_name='quarters')
        op.drop_column('quarters', 'published_by_admin_id')
        op.drop_column('users', 'last_login_at')
        op.drop_index('ix_users_is_super_admin', table_name='users')
        op.drop_column('users', 'is_super_admin')
    except Exception:
        pass
