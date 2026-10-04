"""gripr: an expense can expect money back

Revision ID: a6d2f8c4e1b3
Revises: f4a9c3e7b2d8
Create Date: 2026-10-03 10:00:00.000000

pefi_transactions.expected_back / expected_from: what part of an expense was fronted for
others and who owes it. Nullable, no backfill: existing expenses expect nothing back. See
docs/adr/0032-gripr-expected-back.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a6d2f8c4e1b3'
down_revision: str | None = 'f4a9c3e7b2d8'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_transactions')]
    if 'expected_back' not in columns:
        op.add_column('pefi_transactions', sa.Column('expected_back', sa.Numeric(14, 2), nullable=True))
    if 'expected_from' not in columns:
        op.add_column('pefi_transactions', sa.Column('expected_from', sa.String(80), nullable=True))


def downgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_transactions')]
    with op.batch_alter_table('pefi_transactions') as batch_op:
        if 'expected_from' in columns:
            batch_op.drop_column('expected_from')
        if 'expected_back' in columns:
            batch_op.drop_column('expected_back')
