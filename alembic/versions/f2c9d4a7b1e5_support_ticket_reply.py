"""store the admin's reply on support tickets

Revision ID: f2c9d4a7b1e5
Revises: e8b2c4f6a1d3
Create Date: 2026-10-15 19:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f2c9d4a7b1e5'
down_revision = 'e8b2c4f6a1d3'
branch_labels = None
depends_on = None


def _cols():
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns('support_tickets')}


def upgrade():
    existing = _cols()
    if 'admin_reply' not in existing:
        op.add_column('support_tickets', sa.Column('admin_reply', sa.Text(), nullable=True))
    if 'replied_at' not in existing:
        op.add_column('support_tickets', sa.Column('replied_at', sa.DateTime(), nullable=True))


def downgrade():
    existing = _cols()
    for name in ('replied_at', 'admin_reply'):
        if name in existing:
            op.drop_column('support_tickets', name)
