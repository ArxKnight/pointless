"""participant workflow and public giving trees

Revision ID: 0003_participants
Revises: 0002_teams
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '0003_participants'
down_revision = '0002_teams'
branch_labels = None
depends_on = None


def _has_column(bind, table, column):
    insp = sa.inspect(bind)
    return column in {c['name'] for c in insp.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    op.create_table(
        'participants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('display_name', sa.String(160), nullable=False),
        sa.Column('slug', sa.String(180), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('legacy_member_id', sa.Integer(), sa.ForeignKey('department_members.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('legacy_member_id', name='uq_participants_legacy_member_id'),
    )
    op.create_index('ix_participants_display_name', 'participants', ['display_name'])
    op.create_index('ix_participants_slug', 'participants', ['slug'], unique=True)
    op.create_index('ix_participants_is_active', 'participants', ['is_active'])

    op.create_table('participant_slug_redirects', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('participant_id', sa.Integer(), sa.ForeignKey('participants.id', ondelete='CASCADE'), nullable=False), sa.Column('old_slug', sa.String(180), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_participant_slug_redirects_participant_id', 'participant_slug_redirects', ['participant_id'])
    op.create_index('ix_participant_slug_redirects_old_slug', 'participant_slug_redirects', ['old_slug'], unique=True)

    op.create_table('compatibility_rules', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('from_participant_id', sa.Integer(), sa.ForeignKey('participants.id', ondelete='CASCADE'), nullable=False), sa.Column('to_participant_id', sa.Integer(), sa.ForeignKey('participants.id', ondelete='CASCADE'), nullable=False), sa.Column('is_allowed', sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint('from_participant_id', 'to_participant_id', name='uq_compatibility_pair'))
    op.create_index('ix_compatibility_rules_from_participant_id', 'compatibility_rules', ['from_participant_id'])
    op.create_index('ix_compatibility_rules_to_participant_id', 'compatibility_rules', ['to_participant_id'])

    op.create_table('compatibility_groups', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('name', sa.String(160), nullable=False), sa.Column('notes', sa.Text(), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_compatibility_groups_name', 'compatibility_groups', ['name'], unique=True)
    op.create_table('compatibility_group_members', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('group_id', sa.Integer(), sa.ForeignKey('compatibility_groups.id', ondelete='CASCADE'), nullable=False), sa.Column('participant_id', sa.Integer(), sa.ForeignKey('participants.id', ondelete='CASCADE'), nullable=False), sa.UniqueConstraint('group_id', 'participant_id', name='uq_compat_group_member'))
    op.create_index('ix_compatibility_group_members_group_id', 'compatibility_group_members', ['group_id'])
    op.create_index('ix_compatibility_group_members_participant_id', 'compatibility_group_members', ['participant_id'])

    op.create_table('quarter_participants', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('quarter_id', sa.Integer(), sa.ForeignKey('quarters.id', ondelete='CASCADE'), nullable=False), sa.Column('participant_id', sa.Integer(), sa.ForeignKey('participants.id', ondelete='CASCADE'), nullable=False), sa.UniqueConstraint('quarter_id', 'participant_id', name='uq_quarter_participant'))
    op.create_index('ix_quarter_participants_quarter_id', 'quarter_participants', ['quarter_id'])
    op.create_index('ix_quarter_participants_participant_id', 'quarter_participants', ['participant_id'])

    for name, ddl in {
        'status': sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        'created_at': sa.Column('created_at', sa.DateTime(), nullable=True),
        'published_at': sa.Column('published_at', sa.DateTime(), nullable=True),
        'allocation_min': sa.Column('allocation_min', sa.Integer(), nullable=False, server_default='5'),
        'allocation_max': sa.Column('allocation_max', sa.Integer(), nullable=False, server_default='25'),
        'preferred_min_recipients': sa.Column('preferred_min_recipients', sa.Integer(), nullable=False, server_default='2'),
        'preferred_max_recipients': sa.Column('preferred_max_recipients', sa.Integer(), nullable=False, server_default='5'),
    }.items():
        if not _has_column(bind, 'quarters', name):
            op.add_column('quarters', ddl)
    op.execute("UPDATE quarters SET status = CASE WHEN is_completed = 1 THEN 'completed' WHEN is_active = 1 THEN 'published' ELSE 'draft' END WHERE status IS NULL OR status = 'draft'")
    op.create_index('ix_quarters_status', 'quarters', ['status'])

    if not _has_column(bind, 'giving_plans', 'from_participant_id'):
        col = sa.Column('from_participant_id', sa.Integer(), nullable=True) if bind.dialect.name == 'sqlite' else sa.Column('from_participant_id', sa.Integer(), sa.ForeignKey('participants.id'), nullable=True)
        op.add_column('giving_plans', col)
        op.create_index('ix_giving_plans_from_participant_id', 'giving_plans', ['from_participant_id'])
    if not _has_column(bind, 'giving_plans', 'to_participant_id'):
        col = sa.Column('to_participant_id', sa.Integer(), nullable=True) if bind.dialect.name == 'sqlite' else sa.Column('to_participant_id', sa.Integer(), sa.ForeignKey('participants.id'), nullable=True)
        op.add_column('giving_plans', col)
        op.create_index('ix_giving_plans_to_participant_id', 'giving_plans', ['to_participant_id'])

    # Backfill participant rows from legacy department members. Slug uniqueness is
    # handled simply and safely here; the application service handles future edits.
    members = bind.execute(text('SELECT id, display_name, active, created_at FROM department_members ORDER BY id')).mappings().all()
    used = set()
    for member in members:
        base = ''.join(ch.lower() if ch.isalnum() else '-' for ch in member['display_name']).strip('-') or 'participant'
        while '--' in base:
            base = base.replace('--', '-')
        slug = base
        i = 2
        while slug in used:
            slug = f'{base}-{i}'
            i += 1
        used.add(slug)
        bind.execute(text('INSERT INTO participants (display_name, slug, is_active, legacy_member_id, created_at, updated_at) VALUES (:name, :slug, :active, :mid, :created, :created)'), {'name': member['display_name'], 'slug': slug, 'active': member['active'], 'mid': member['id'], 'created': member['created_at']})
    bind.execute(text('UPDATE giving_plans SET from_participant_id = (SELECT id FROM participants WHERE legacy_member_id = giving_plans.from_member_id) WHERE from_participant_id IS NULL'))
    bind.execute(text('UPDATE giving_plans SET to_participant_id = (SELECT id FROM participants WHERE legacy_member_id = giving_plans.to_member_id) WHERE to_participant_id IS NULL'))
    qp_pairs = set()
    for row in bind.execute(text('SELECT DISTINCT quarter_id, from_participant_id AS participant_id FROM giving_plans WHERE from_participant_id IS NOT NULL')).mappings():
        qp_pairs.add((row['quarter_id'], row['participant_id']))
    for row in bind.execute(text('SELECT DISTINCT quarter_id, to_participant_id AS participant_id FROM giving_plans WHERE to_participant_id IS NOT NULL')).mappings():
        qp_pairs.add((row['quarter_id'], row['participant_id']))
    for quarter_id, participant_id in qp_pairs:
        bind.execute(text('INSERT INTO quarter_participants (quarter_id, participant_id) VALUES (:quarter_id, :participant_id)'), {'quarter_id': quarter_id, 'participant_id': participant_id})


def downgrade():
    op.drop_table('quarter_participants')
    op.drop_table('compatibility_group_members')
    op.drop_table('compatibility_groups')
    op.drop_table('compatibility_rules')
    op.drop_table('participant_slug_redirects')
    op.drop_table('participants')
