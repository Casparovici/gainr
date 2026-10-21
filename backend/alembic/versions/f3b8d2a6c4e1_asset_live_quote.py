"""assets: the hourly live quote

Revision ID: f3b8d2a6c4e1
Revises: e5a2c9f7b3d1
Create Date: 2026-10-19 12:00:00.000000

Three nullable columns on `assets` for the latest traded price, refreshed at most once an hour
(docs/adr/0047-hourly-live-quotes.md). Guarded, because app.main's create_all may have added
them already; nothing to backfill, a missing quote just means values stay on daily closes.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f3b8d2a6c4e1'
down_revision: str | None = 'e5a2c9f7b3d1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns('assets')}

    if 'quote_price' not in columns:
        op.add_column('assets', sa.Column('quote_price', sa.Numeric(precision=20, scale=8), nullable=True))
    if 'quoted_at' not in columns:
        op.add_column('assets', sa.Column('quoted_at', sa.DateTime(), nullable=True))
    if 'quote_checked_at' not in columns:
        op.add_column('assets', sa.Column('quote_checked_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns('assets')}

    if 'quote_checked_at' in columns:
        op.drop_column('assets', 'quote_checked_at')
    if 'quoted_at' in columns:
        op.drop_column('assets', 'quoted_at')
    if 'quote_price' in columns:
        op.drop_column('assets', 'quote_price')
