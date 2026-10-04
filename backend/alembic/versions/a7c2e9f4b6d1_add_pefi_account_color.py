"""add color to pefi_accounts

Revision ID: a7c2e9f4b6d1
Revises: e3d9a2f6c1b8
Create Date: 2026-09-12 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the column exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'a7c2e9f4b6d1'
down_revision: str | None = 'e3d9a2f6c1b8'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_accounts')]

    if 'color' not in columns:
        op.add_column('pefi_accounts', sa.Column('color', sa.String(length=7), nullable=True))


def downgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_accounts')]
    if 'color' in columns:
        with op.batch_alter_table('pefi_accounts') as batch_op:
            batch_op.drop_column('color')
