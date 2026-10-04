"""add asset logo cache

Revision ID: b8c1d4e90f27
Revises: a63f442401c5
Create Date: 2026-09-11 00:00:00.000000

Guarded with an inspector because app.main calls Base.metadata.create_all on startup for
local first-run convenience: on a database that has already been booted against this code,
the table is there before the migration runs, and re-creating it would be an error rather
than a no-op.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'b8c1d4e90f27'
down_revision: str | None = 'a63f442401c5'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()

    if 'logo_checked_at' not in {c['name'] for c in inspector.get_columns('assets')}:
        op.add_column('assets', sa.Column('logo_checked_at', sa.Date(), nullable=True))

    if 'asset_logos' not in inspector.get_table_names():
        op.create_table(
            'asset_logos',
            sa.Column('asset_id', sa.Integer(), nullable=False),
            sa.Column('content_type', sa.String(length=64), nullable=False),
            sa.Column('image', sa.LargeBinary(), nullable=False),
            sa.Column('source_url', sa.String(length=500), nullable=False),
            sa.Column('fetched_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
            sa.PrimaryKeyConstraint('asset_id'),
        )


def downgrade() -> None:
    inspector = _inspector()

    if 'asset_logos' in inspector.get_table_names():
        op.drop_table('asset_logos')
    if 'logo_checked_at' in {c['name'] for c in inspector.get_columns('assets')}:
        op.drop_column('assets', 'logo_checked_at')
