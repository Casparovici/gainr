"""gripr: virtual pots inside another account

Revision ID: a9d5e3b7c2f8
Revises: f2c6d8a4b1e7
Create Date: 2026-10-02 22:00:00.000000

pefi_accounts.held_in_account_id: set when an account is a virtual pot (Onderhoud Auto,
Reservering Vakantie) whose money really sits in another account (Trade Republic). The bank sync
counts pot spending as the parent's bank entries and never matches a bank entry against a move
between the parent and its pots. See the addendum on docs/adr/0029-ing-transactions-into-gripr.md.

Guarded with an inspector, as app.main's create_all may already have added the column.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a9d5e3b7c2f8'
down_revision: str | None = 'f2c6d8a4b1e7'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'held_in_account_id' not in [c['name'] for c in inspector.get_columns('pefi_accounts')]:
        with op.batch_alter_table('pefi_accounts') as batch_op:
            batch_op.add_column(sa.Column('held_in_account_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_pefi_accounts_held_in', 'pefi_accounts', ['held_in_account_id'], ['id'], ondelete='SET NULL'
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'held_in_account_id' in [c['name'] for c in inspector.get_columns('pefi_accounts')]:
        with op.batch_alter_table('pefi_accounts') as batch_op:
            batch_op.drop_constraint('fk_pefi_accounts_held_in', type_='foreignkey')
            batch_op.drop_column('held_in_account_id')
