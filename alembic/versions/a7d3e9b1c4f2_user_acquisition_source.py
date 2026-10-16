"""users.acquisition_source / start_payload: where each user came from

Existing users stay NULL ("joined before tracking"), except those who already have an inviter:
they are marked as 'referral'.

Revision ID: a7d3e9b1c4f2
Revises: f2c9d4a7b1e5
Create Date: 2026-10-16 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a7d3e9b1c4f2'
down_revision = 'f2c9d4a7b1e5'
branch_labels = None
depends_on = None

INDEX = 'ix_users_acquisition_source'


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c['name'] for c in insp.get_columns('users')}
    if 'acquisition_source' not in cols:
        op.add_column('users', sa.Column('acquisition_source', sa.String(length=64), nullable=True))
    if 'start_payload' not in cols:
        op.add_column('users', sa.Column('start_payload', sa.String(length=128), nullable=True))
    if INDEX not in {i['name'] for i in insp.get_indexes('users')}:
        op.create_index(INDEX, 'users', ['acquisition_source'])
    op.execute("UPDATE users SET acquisition_source = 'referral' WHERE referred_by IS NOT NULL AND acquisition_source IS NULL")


def downgrade():
    insp = sa.inspect(op.get_bind())
    if INDEX in {i['name'] for i in insp.get_indexes('users')}:
        op.drop_index(INDEX, table_name='users')
    cols = {c['name'] for c in insp.get_columns('users')}
    if 'start_payload' in cols:
        op.drop_column('users', 'start_payload')
    if 'acquisition_source' in cols:
        op.drop_column('users', 'acquisition_source')
