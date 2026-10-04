"""add sort_order to pefi_accounts

Revision ID: f4a1c8e2d6b7
Revises: d2f6a91c5b3e
Create Date: 2026-09-12 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the column exists before the migration runs.

Backfills existing rows in the same order the app already displays them (type, then name), so
applying this migration doesn't reshuffle anyone's Accounts page — reordering only happens once
someone actually drags a card.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'f4a1c8e2d6b7'
down_revision: str | None = 'd2f6a91c5b3e'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_accounts')]

    if 'sort_order' not in columns:
        op.add_column('pefi_accounts', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))

    conn = op.get_bind()
    accounts_by_type: dict[str, list[int]] = {}
    for account_id, type_ in conn.execute(sa.text('SELECT id, type FROM pefi_accounts ORDER BY type, name')):
        accounts_by_type.setdefault(type_, []).append(account_id)
    for ids in accounts_by_type.values():
        for position, account_id in enumerate(ids):
            conn.execute(
                sa.text('UPDATE pefi_accounts SET sort_order = :pos WHERE id = :id'),
                {'pos': position, 'id': account_id},
            )


def downgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_accounts')]
    if 'sort_order' in columns:
        with op.batch_alter_table('pefi_accounts') as batch_op:
            batch_op.drop_column('sort_order')
