"""add asset fundamentals snapshot cache

Revision ID: c7a5e83b1d94
Revises: b8c1d4e90f27
Create Date: 2026-09-11 00:00:00.000000

Guarded with an inspector for the same reason the logo migration is: app.main calls
Base.metadata.create_all on startup, so on a database already booted against this code the
table exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'c7a5e83b1d94'
down_revision: str | None = 'b8c1d4e90f27'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    if 'asset_snapshots' not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            'asset_snapshots',
            sa.Column('asset_id', sa.Integer(), nullable=False),
            sa.Column('kind', sa.String(length=32), nullable=False),
            sa.Column('payload', sa.Text(), nullable=False),
            sa.Column('fetched_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
            sa.PrimaryKeyConstraint('asset_id', 'kind'),
        )


def downgrade() -> None:
    if 'asset_snapshots' in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table('asset_snapshots')
