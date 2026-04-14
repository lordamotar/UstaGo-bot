"""add admin_logs table

Revision ID: 4d2e1a3b5c7d
Revises: 0c6d3d3b47ee
Create Date: 2026-04-14 16:17:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d2e1a3b5c7d'
down_revision = '0c6d3d3b47ee'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'admin_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('admin_logs')
