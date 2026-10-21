"""gripr: a recurring transfer can be the depreciation of an asset

Revision ID: c5d8e1f3a7b4
Revises: b9e3c7a1f5d2
Create Date: 2026-10-05 10:00:00.000000

pefi_depreciations: how much of a recurring transfer (or of a booked transfer, as a snapshot of
what was applied) lowers a manually valued asset's value. No backfill: nothing depreciates until a
rule says so. See docs/adr/0034-gripr-depreciation.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c5d8e1f3a7b4'
down_revision: str | None = 'b9e3c7a1f5d2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('pefi_depreciations'):
        return
    op.create_table(
        'pefi_depreciations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recurring_id', sa.Integer(), sa.ForeignKey('pefi_recurring_transactions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('transaction_id', sa.Integer(), sa.ForeignKey('pefi_transactions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('pefi_accounts.id'), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
    )
    op.create_index('ix_pefi_depreciations_recurring_id', 'pefi_depreciations', ['recurring_id'])
    op.create_index('ix_pefi_depreciations_transaction_id', 'pefi_depreciations', ['transaction_id'])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('pefi_depreciations'):
        op.drop_table('pefi_depreciations')
