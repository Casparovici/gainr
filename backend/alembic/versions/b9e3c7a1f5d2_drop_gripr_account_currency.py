"""gripr: drop the account currency

Revision ID: b9e3c7a1f5d2
Revises: a6d2f8c4e1b3
Create Date: 2026-10-04 09:00:00.000000

pefi_accounts.currency was never read: every balance was summed into net worth as euros whatever
it said. gripr is euro-only; see docs/adr/0033-gripr-euro-only.md. Downgrade restores the column
as "EUR" for every account, which is what it held.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b9e3c7a1f5d2'
down_revision: str | None = 'a6d2f8c4e1b3'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _columns() -> list[str]:
    return [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_accounts')]


def upgrade() -> None:
    if 'currency' in _columns():
        with op.batch_alter_table('pefi_accounts') as batch_op:
            batch_op.drop_column('currency')


def downgrade() -> None:
    if 'currency' not in _columns():
        op.add_column('pefi_accounts', sa.Column('currency', sa.String(8), nullable=False, server_default='EUR'))
