"""add teams and team groups

Revision ID: 0002_teams
Revises: 0001_initial
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

revision = '0002_teams'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'team_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_team_groups_name', 'team_groups', ['name'], unique=True)

    op.create_table(
        'teams',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('colour', sa.String(20), nullable=False, server_default='#6366f1'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('team_groups.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_teams_name', 'teams', ['name'], unique=True)
    op.create_index('ix_teams_group_id', 'teams', ['group_id'])

    op.add_column('users', sa.Column('team_id', sa.Integer(), nullable=True))
    if op.get_bind().dialect.name != 'sqlite':
        op.create_foreign_key('fk_users_team_id_teams', 'users', 'teams', ['team_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_users_team_id', 'users', ['team_id'])

    groups = table('team_groups', column('id', sa.Integer), column('name', sa.String), column('description', sa.Text), column('display_order', sa.Integer), column('is_active', sa.Boolean))
    teams = table('teams', column('id', sa.Integer), column('name', sa.String), column('description', sa.Text), column('colour', sa.String), column('display_order', sa.Integer), column('is_active', sa.Boolean), column('group_id', sa.Integer))
    op.bulk_insert(groups, [
        {'id': 1, 'name': 'Shift A + Shift B', 'description': 'Initial sharing group for teams that commonly share points.', 'display_order': 10, 'is_active': True},
        {'id': 2, 'name': 'Shift C + Shift D', 'description': 'Initial sharing group for teams that commonly share points.', 'display_order': 20, 'is_active': True},
        {'id': 3, 'name': 'Others', 'description': 'Independent initial group.', 'display_order': 30, 'is_active': True},
    ])
    op.bulk_insert(teams, [
        {'id': 1, 'name': 'Shift A', 'description': 'Shift A initial team.', 'colour': '#2563eb', 'display_order': 10, 'is_active': True, 'group_id': 1},
        {'id': 2, 'name': 'Shift B', 'description': 'Shift B initial team.', 'colour': '#7c3aed', 'display_order': 20, 'is_active': True, 'group_id': 1},
        {'id': 3, 'name': 'Shift C', 'description': 'Shift C initial team.', 'colour': '#059669', 'display_order': 30, 'is_active': True, 'group_id': 2},
        {'id': 4, 'name': 'Shift D', 'description': 'Shift D initial team.', 'colour': '#ea580c', 'display_order': 40, 'is_active': True, 'group_id': 2},
        {'id': 5, 'name': 'Others', 'description': 'Independent or non-shift users.', 'colour': '#64748b', 'display_order': 50, 'is_active': True, 'group_id': 3},
    ])


def downgrade():
    op.drop_index('ix_users_team_id', table_name='users')
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_constraint('fk_users_team_id_teams', 'users', type_='foreignkey')
    op.drop_column('users', 'team_id')
    op.drop_index('ix_teams_group_id', table_name='teams')
    op.drop_index('ix_teams_name', table_name='teams')
    op.drop_table('teams')
    op.drop_index('ix_team_groups_name', table_name='team_groups')
    op.drop_table('team_groups')
