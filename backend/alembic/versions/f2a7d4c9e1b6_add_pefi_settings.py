"""add pefi_settings table (period_start_day)

Revision ID: f2a7d4c9e1b6
Revises: e8f4a6c2b9d3
Create Date: 2026-09-13 00:00:00.000003

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the table exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f2a7d4c9e1b6'
down_revision: str | None = 'e8f4a6c2b9d3'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table('pefi_settings'):
        op.create_table(
            'pefi_settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('period_start_day', sa.Integer(), nullable=False, server_default='1'),
        )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('pefi_settings'):
        op.drop_table('pefi_settings')
