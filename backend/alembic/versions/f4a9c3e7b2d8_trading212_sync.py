"""Trading 212: card spending into gripr, fills/dividends/interest into gainr

Revision ID: f4a9c3e7b2d8
Revises: c8e2a6f4d1b9
Create Date: 2026-10-02 22:00:00.000000

- bank_connections.provider: how a bank is read ("enablebanking", or "trading212" for Trading
  212's own API), plus a Trading 212 row (off) with its one account ("T212"), unmapped.
- bank_synced_transactions.merchant: the merchant of a card payment, so the next payment there
  can take the category the reader gave the last one.
- assets.isin: how a broker's records find their asset.
- broker_connections / broker_synced_items: gainr's side, one broker row (Trading212, off) and the
  record of every fill, dividend and weekly interest deposit handled.

See docs/adr/0031-trading212-sync.md. Guarded with an inspector: app.main runs create_all at
startup, so a server that started on the new models first already has the new tables (empty).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f4a9c3e7b2d8'
down_revision: str | None = 'c8e2a6f4d1b9'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _columns(inspector, table: str) -> list[str]:
    return [c['name'] for c in inspector.get_columns(table)]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if 'provider' not in _columns(inspector, 'bank_connections'):
        op.add_column(
            'bank_connections',
            sa.Column('provider', sa.String(16), nullable=False, server_default='enablebanking'),
        )
    op.execute(
        "INSERT INTO bank_connections (aspsp_name, aspsp_country, source_prefix, provider, enabled, amount_only) "
        "SELECT 'Trading 212', 'NL', 't212', 'trading212', 0, 0 "
        "WHERE NOT EXISTS (SELECT 1 FROM bank_connections WHERE source_prefix = 't212')"
    )
    op.execute(
        "INSERT OR IGNORE INTO bank_sync_accounts (iban, connection_id, product, holder_name) "
        "SELECT 'T212', id, 'Invest account', '' FROM bank_connections WHERE source_prefix = 't212'"
    )

    if 'merchant' not in _columns(inspector, 'bank_synced_transactions'):
        with op.batch_alter_table('bank_synced_transactions') as batch_op:
            batch_op.add_column(sa.Column('merchant', sa.String(120), nullable=True))
            batch_op.create_index('ix_bank_synced_transactions_merchant', ['merchant'])

    if 'isin' not in _columns(inspector, 'assets'):
        with op.batch_alter_table('assets') as batch_op:
            batch_op.add_column(sa.Column('isin', sa.String(12), nullable=True))
            batch_op.create_index('ix_assets_isin', ['isin'])

    if not inspector.has_table('broker_connections'):
        op.create_table(
            'broker_connections',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('broker', sa.String(64), nullable=False, unique=True),
            sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id', ondelete='SET NULL'), nullable=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('since', sa.Date(), nullable=True),
            sa.Column('last_synced_at', sa.DateTime(), nullable=True),
            sa.Column('last_error', sa.String(300), nullable=True),
            sa.Column('unmapped', sa.Text(), nullable=True),
        )
    op.execute("INSERT OR IGNORE INTO broker_connections (broker, enabled) VALUES ('Trading212', 0)")

    if not inspector.has_table('broker_synced_items'):
        op.create_table(
            'broker_synced_items',
            sa.Column('reference', sa.String(80), primary_key=True),
            sa.Column('outcome', sa.String(16), nullable=False),
            sa.Column('transaction_id', sa.Integer(), sa.ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True),
            sa.Column('synced_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_broker_synced_items_transaction_id', 'broker_synced_items', ['transaction_id'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('broker_synced_items'):
        op.drop_table('broker_synced_items')
    if inspector.has_table('broker_connections'):
        op.drop_table('broker_connections')
    if 'isin' in _columns(inspector, 'assets'):
        with op.batch_alter_table('assets') as batch_op:
            batch_op.drop_index('ix_assets_isin')
            batch_op.drop_column('isin')
    if 'merchant' in _columns(inspector, 'bank_synced_transactions'):
        with op.batch_alter_table('bank_synced_transactions') as batch_op:
            batch_op.drop_index('ix_bank_synced_transactions_merchant')
            batch_op.drop_column('merchant')
    op.execute("DELETE FROM bank_synced_transactions WHERE reference LIKE 't212:%'")
    op.execute("DELETE FROM bank_sync_accounts WHERE connection_id IN (SELECT id FROM bank_connections WHERE source_prefix = 't212')")
    op.execute("DELETE FROM bank_connections WHERE source_prefix = 't212'")
    if 'provider' in _columns(inspector, 'bank_connections'):
        with op.batch_alter_table('bank_connections') as batch_op:
            batch_op.drop_column('provider')
