"""add gripr refunds: pefi_transactions.refund_of_id

Revision ID: b8d3e6f1a2c4
Revises: e3a9c7d1f5b2
Create Date: 2026-09-30 00:00:00.000000

A REFUND transaction (money coming back for an expense) can point at the expense it undoes, so
it inherits that expense's category and counts in that expense's period. The new enum value
itself needs no DDL on SQLite: the type column is a plain VARCHAR(8) holding the member name,
and "REFUND" fits. See docs/adr/0023.

Guarded with an inspector for the same reason every migration since the logo one is.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b8d3e6f1a2c4'
down_revision: str | None = 'e3a9c7d1f5b2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # On Postgres the type column is a native enum; SQLite has nothing to alter.
        op.execute("ALTER TYPE pefitransactiontype ADD VALUE IF NOT EXISTS 'REFUND'")

    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('pefi_transactions')]
    if 'refund_of_id' not in columns:
        with op.batch_alter_table('pefi_transactions') as batch_op:
            batch_op.add_column(sa.Column('refund_of_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_pefi_transactions_refund_of_id', 'pefi_transactions', ['refund_of_id'], ['id']
            )
    indexes = [i['name'] for i in sa.inspect(bind).get_indexes('pefi_transactions')]
    if 'ix_pefi_transactions_refund_of_id' not in indexes:
        op.create_index('ix_pefi_transactions_refund_of_id', 'pefi_transactions', ['refund_of_id'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('pefi_transactions')]
    indexes = [i['name'] for i in inspector.get_indexes('pefi_transactions')]
    with op.batch_alter_table('pefi_transactions') as batch_op:
        if 'ix_pefi_transactions_refund_of_id' in indexes:
            batch_op.drop_index('ix_pefi_transactions_refund_of_id')
        if 'refund_of_id' in columns:
            batch_op.drop_column('refund_of_id')
