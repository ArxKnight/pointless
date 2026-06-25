"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa
revision='0001_initial'; down_revision=None; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('users', sa.Column('id',sa.Integer(),primary_key=True), sa.Column('username',sa.String(80),nullable=False), sa.Column('display_name',sa.String(160),nullable=False), sa.Column('email',sa.String(255),nullable=False), sa.Column('password_hash',sa.String(255),nullable=False), sa.Column('is_admin',sa.Boolean(),nullable=False), sa.Column('created_at',sa.DateTime(),nullable=False), sa.Column('is_active',sa.Boolean(),nullable=False))
    op.create_index('ix_users_username','users',['username'],unique=True); op.create_index('ix_users_email','users',['email'],unique=True)
    op.create_table('department_members', sa.Column('id',sa.Integer(),primary_key=True), sa.Column('display_name',sa.String(160),nullable=False), sa.Column('email',sa.String(255),nullable=False), sa.Column('added_by',sa.Integer(),sa.ForeignKey('users.id')), sa.Column('active',sa.Boolean(),nullable=False), sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_department_members_display_name','department_members',['display_name']); op.create_index('ix_department_members_email','department_members',['email'],unique=True)
    op.create_table('quarters', sa.Column('id',sa.Integer(),primary_key=True), sa.Column('year',sa.Integer(),nullable=False), sa.Column('quarter',sa.Integer(),nullable=False), sa.Column('label',sa.String(20),nullable=False), sa.Column('generated_at',sa.DateTime(),nullable=False), sa.Column('is_active',sa.Boolean(),nullable=False), sa.Column('is_completed',sa.Boolean(),nullable=False), sa.UniqueConstraint('year','quarter',name='uq_year_quarter'))
    op.create_index('ix_quarters_year','quarters',['year'])
    op.create_table('giving_plans', sa.Column('id',sa.Integer(),primary_key=True), sa.Column('quarter_id',sa.Integer(),sa.ForeignKey('quarters.id'),nullable=False), sa.Column('from_member_id',sa.Integer(),sa.ForeignKey('department_members.id'),nullable=False), sa.Column('to_member_id',sa.Integer(),sa.ForeignKey('department_members.id'),nullable=False), sa.Column('amount',sa.Integer(),nullable=False), sa.Column('acknowledged',sa.Boolean(),nullable=False))
    op.create_index('ix_giving_plans_quarter_id','giving_plans',['quarter_id']); op.create_index('ix_giving_plans_from_member_id','giving_plans',['from_member_id']); op.create_index('ix_giving_plans_to_member_id','giving_plans',['to_member_id'])
    op.create_table('points_ledger', sa.Column('id',sa.Integer(),primary_key=True), sa.Column('quarter_id',sa.Integer(),sa.ForeignKey('quarters.id'),nullable=False), sa.Column('from_member_id',sa.Integer(),sa.ForeignKey('department_members.id'),nullable=False), sa.Column('to_member_id',sa.Integer(),sa.ForeignKey('department_members.id'),nullable=False), sa.Column('amount',sa.Integer(),nullable=False), sa.Column('marked_sent_at',sa.DateTime(),nullable=False), sa.Column('marked_sent_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False))
    op.create_index('ix_points_ledger_quarter_id','points_ledger',['quarter_id']); op.create_index('ix_points_ledger_from_member_id','points_ledger',['from_member_id']); op.create_index('ix_points_ledger_to_member_id','points_ledger',['to_member_id'])

def downgrade():
    op.drop_table('points_ledger'); op.drop_table('giving_plans'); op.drop_table('quarters'); op.drop_table('department_members'); op.drop_table('users')
