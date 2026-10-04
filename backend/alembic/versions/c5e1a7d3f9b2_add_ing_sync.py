"""gripr: ING transactions via Enable Banking

Revision ID: c5e1a7d3f9b2
Revises: b8d4f2a6c1e3
Create Date: 2026-10-02 12:00:00.000000

Four tables for booking ING transactions into gripr automatically: ing_sync_settings (a single
row: the consent's session, on/off, since-date), ing_sync_accounts (each ING account the consent
covers and the gripr account it lands on), ing_counterparty_rules (counterparties that are the
reader's own accounts elsewhere, booked as transfers) and ing_synced_transactions (one row per
handled bank entry). See docs/adr/0029-ing-transactions-into-gripr.md.

Guarded with an inspector for the same reason every migration since the logo one is.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c5e1a7d3f9b2'
down_revision: str | None = 'b8d4f2a6c1e3'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('ing_sync_settings'):
        op.create_table(
            'ing_sync_settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('since', sa.Date(), nullable=True),
            sa.Column('session_id', sa.String(64), nullable=True),
            sa.Column('valid_until', sa.DateTime(), nullable=True),
            sa.Column('pending_state', sa.String(64), nullable=True),
            sa.Column('last_synced_at', sa.DateTime(), nullable=True),
            sa.Column('last_error', sa.String(300), nullable=True),
        )
    if not inspector.has_table('ing_sync_accounts'):
        op.create_table(
            'ing_sync_accounts',
            sa.Column('iban', sa.String(34), primary_key=True),
            sa.Column('eb_uid', sa.String(64), nullable=True),
            sa.Column('product', sa.String(60), nullable=False, server_default=''),
            sa.Column('holder_name', sa.String(120), nullable=False, server_default=''),
            sa.Column('gripr_account_id', sa.Integer(), sa.ForeignKey('pefi_accounts.id', ondelete='SET NULL'), nullable=True),
        )
    if not inspector.has_table('ing_counterparty_rules'):
        op.create_table(
            'ing_counterparty_rules',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('iban', sa.String(34), nullable=True),
            sa.Column('text_contains', sa.String(80), nullable=True),
            sa.Column('gripr_account_id', sa.Integer(), sa.ForeignKey('pefi_accounts.id', ondelete='CASCADE'), nullable=False),
        )
    if not inspector.has_table('ing_synced_transactions'):
        op.create_table(
            'ing_synced_transactions',
            sa.Column('reference', sa.String(64), primary_key=True),
            sa.Column('iban', sa.String(34), nullable=False),
            sa.Column('transacted_on', sa.Date(), nullable=False),
            sa.Column('synced_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('outcome', sa.String(16), nullable=False),
            sa.Column('gripr_transaction_id', sa.Integer(), sa.ForeignKey('pefi_transactions.id', ondelete='SET NULL'), nullable=True),
            sa.Column('recurring_id', sa.Integer(), sa.ForeignKey('pefi_recurring_transactions.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index('ix_ing_synced_transactions_transacted_on', 'ing_synced_transactions', ['transacted_on'])
        op.create_index('ix_ing_synced_transactions_gripr_transaction_id', 'ing_synced_transactions', ['gripr_transaction_id'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ('ing_synced_transactions', 'ing_counterparty_rules', 'ing_sync_accounts', 'ing_sync_settings'):
        if inspector.has_table(table):
            op.drop_table(table)
