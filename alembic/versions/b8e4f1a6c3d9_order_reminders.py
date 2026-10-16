"""orders.reminder_prompted_at / remind_mode / reminder_sent_at and order_views

Re-notifying masters about orders without bids: the client is asked once, the choice is stored on the order;
order_views remembers which masters opened the order card (to remind only those who did not).

Revision ID: b8e4f1a6c3d9
Revises: a7d3e9b1c4f2
Create Date: 2026-10-16 20:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b8e4f1a6c3d9'
down_revision = 'a7d3e9b1c4f2'
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c['name'] for c in insp.get_columns('orders')}
    if 'reminder_prompted_at' not in cols:
        op.add_column('orders', sa.Column('reminder_prompted_at', sa.DateTime(), nullable=True))
    if 'remind_mode' not in cols:
        op.add_column('orders', sa.Column('remind_mode', sa.String(length=16), nullable=True))
    if 'reminder_sent_at' not in cols:
        op.add_column('orders', sa.Column('reminder_sent_at', sa.DateTime(), nullable=True))
    if 'order_views' not in insp.get_table_names():
        op.create_table(
            'order_views',
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('viewed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    # Orders that already exist must not suddenly ask their clients about reminders.
    op.execute("UPDATE orders SET reminder_prompted_at = NOW() WHERE reminder_prompted_at IS NULL")


def downgrade():
    insp = sa.inspect(op.get_bind())
    if 'order_views' in insp.get_table_names():
        op.drop_table('order_views')
    cols = {c['name'] for c in insp.get_columns('orders')}
    for name in ('reminder_sent_at', 'remind_mode', 'reminder_prompted_at'):
        if name in cols:
            op.drop_column('orders', name)
