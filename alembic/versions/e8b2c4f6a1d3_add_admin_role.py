"""add users.admin_role (superadmin / moderator / finance)

NULL means "superadmin" so existing admins keep full access.

Revision ID: e8b2c4f6a1d3
Revises: c3f1a9d2b7e4
Create Date: 2026-10-15 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'e8b2c4f6a1d3'
down_revision = 'c3f1a9d2b7e4'
branch_labels = None
depends_on = None


def upgrade():
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}
    if 'admin_role' not in cols:
        op.add_column('users', sa.Column('admin_role', sa.String(length=20), nullable=True))


def downgrade():
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}
    if 'admin_role' in cols:
        op.drop_column('users', 'admin_role')
