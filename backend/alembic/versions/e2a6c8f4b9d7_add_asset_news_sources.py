"""add assets.news_sources: extra news feeds per position

Revision ID: e2a6c8f4b9d7
Revises: d7f2b9c4e6a1
Create Date: 2026-09-30 00:00:00.000000

A JSON list of source keys (sector/industry/Yahoo symbol) whose news is shown alongside the
position's own. Nullable: no extra sources is the default. See docs/adr/0026.

Guarded with an inspector for the same reason every migration since the logo one is.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e2a6c8f4b9d7'
down_revision: str | None = 'd7f2b9c4e6a1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('assets')]
    if 'news_sources' not in columns:
        op.add_column('assets', sa.Column('news_sources', sa.Text(), nullable=True))


def downgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('assets')]
    if 'news_sources' in columns:
        with op.batch_alter_table('assets') as batch_op:
            batch_op.drop_column('news_sources')
