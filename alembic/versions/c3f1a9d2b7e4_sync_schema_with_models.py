"""sync schema with models

The earlier migrations never created some tables/columns that the models use
(support_tickets, support_chats, topup_requests, users.banned_until, ...), and the
Postgres enum ``transactiontype`` lacked REFUND (used by the code) and TOPUP.
A fresh ``alembic upgrade head`` therefore produced a broken database.

Everything here is idempotent, so it is safe both on a fresh database and on one
that was originally built with ``Base.metadata.create_all``.

Revision ID: c3f1a9d2b7e4
Revises: 4d2e1a3b5c7d
Create Date: 2026-10-15 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3f1a9d2b7e4'
down_revision = '4d2e1a3b5c7d'
branch_labels = None
depends_on = None


def _add_missing_columns(table, *columns):
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table, column)


def upgrade():
    bind = op.get_bind()

    # 1. Enum values. ALTER TYPE ... ADD VALUE must run outside the migration transaction.
    has_enum = bind.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'transactiontype'")).first()
    if has_enum:
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'REFUND'")
            op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'TOPUP'")

    tables = set(sa.inspect(op.get_bind()).get_table_names())

    # 2. Missing columns on existing tables (server defaults make this safe for populated tables)
    _add_missing_columns(
        'users',
        sa.Column('notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('visible_for_new_orders', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('agreed_to_terms', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('banned_until', sa.DateTime(), nullable=True),
        sa.Column('dnd_start', sa.String(length=5), nullable=True),
        sa.Column('dnd_end', sa.String(length=5), nullable=True),
    )
    _add_missing_columns(
        'categories',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    _add_missing_columns(
        'master_profiles',
        sa.Column('is_accredited', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )

    # users.do_not_disturb is a leftover of an early schema: the models no longer have it, but it is
    # NOT NULL without a default, so EVERY ORM insert into users failed on a migrated database.
    # Keep the data, just make the column harmless.
    if 'do_not_disturb' in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}:
        op.execute("ALTER TABLE users ALTER COLUMN do_not_disturb SET DEFAULT FALSE")
        op.execute("ALTER TABLE users ALTER COLUMN do_not_disturb DROP NOT NULL")

    # 3. Missing tables
    if 'support_tickets' not in tables:
        op.create_table(
            'support_tickets',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('is_replied', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
        )
    if 'support_chats' not in tables:
        op.create_table(
            'support_chats',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_tid', sa.BigInteger(), nullable=False),
            sa.Column('admin_tid', sa.BigInteger(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
        )
    if 'topup_requests' not in tables:
        op.create_table(
            'topup_requests',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('amount', sa.Integer(), nullable=False),
            sa.Column('method', sa.String(length=50), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
            sa.Column('receipt_data', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
        )
    if 'system_settings' not in tables:
        op.create_table(
            'system_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('crypto_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('crypto_address', sa.String(length=255), nullable=True),
            sa.Column('bank_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('bank_details', sa.Text(), nullable=True),
            sa.Column('free_orders_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.PrimaryKeyConstraint('id'),
        )

    # 4. Indexes for the hottest queries
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_status_category ON orders (status, category_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bids_order_id ON bids (order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_transactions_user_id ON transactions (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_topup_requests_status ON topup_requests (status)")


def downgrade():
    # Only the indexes are removed. Tables, columns and enum values are kept on purpose:
    # dropping them would destroy data, and PostgreSQL cannot remove enum values anyway.
    op.execute("DROP INDEX IF EXISTS ix_topup_requests_status")
    op.execute("DROP INDEX IF EXISTS ix_transactions_user_id")
    op.execute("DROP INDEX IF EXISTS ix_bids_order_id")
    op.execute("DROP INDEX IF EXISTS ix_orders_status_category")
