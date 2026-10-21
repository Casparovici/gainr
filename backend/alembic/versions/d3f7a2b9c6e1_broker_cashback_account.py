"""gainr/gripr: Trading 212's cashback can go to its own gripr account

Revision ID: d3f7a2b9c6e1
Revises: c5d8e1f3a7b4
Create Date: 2026-10-05 12:00:00.000000

broker_connections.cashback_account_id: the gripr account the weekly cashback is booked into as
income (the interest stays cash in gainr). Null keeps the old behaviour, one weekly deposit.
See docs/adr/0031-trading212-sync.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd3f7a2b9c6e1'
down_revision: str | None = 'c5d8e1f3a7b4'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _columns() -> list[str]:
    return [c['name'] for c in sa.inspect(op.get_bind()).get_columns('broker_connections')]


def upgrade() -> None:
    if 'cashback_account_id' not in _columns():
        with op.batch_alter_table('broker_connections') as batch_op:
            batch_op.add_column(sa.Column('cashback_account_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_broker_cashback_account', 'pefi_accounts', ['cashback_account_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    if 'cashback_account_id' in _columns():
        with op.batch_alter_table('broker_connections') as batch_op:
            batch_op.drop_constraint('fk_broker_cashback_account', type_='foreignkey')
            batch_op.drop_column('cashback_account_id')
