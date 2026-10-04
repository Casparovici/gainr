"""add interval to pefi_recurring_transactions

Revision ID: d5e9c3a7f1b2
Revises: c4d8f2a9e6b1
Create Date: 2026-09-13 00:00:00.000001

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the column exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd5e9c3a7f1b2'
down_revision: str | None = 'c4d8f2a9e6b1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_recurring_transactions')]
    if 'interval' not in columns:
        op.add_column(
            'pefi_recurring_transactions',
            sa.Column('interval', sa.Integer(), nullable=False, server_default='1'),
        )


def downgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_recurring_transactions')]
    if 'interval' in columns:
        with op.batch_alter_table('pefi_recurring_transactions') as batch_op:
            batch_op.drop_column('interval')
