"""add pefi portfolio account link

Revision ID: a3d9f7b21c48
Revises: 040be43d92e5
Create Date: 2026-09-16 21:05:00.000000

Guarded with an inspector, same as every migration since the logo one: app.main calls
Base.metadata.create_all on startup, so on a database already booted against this code the
column exists before the migration ever runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a3d9f7b21c48'
down_revision: str | None = '040be43d92e5'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns('pefi_settings')}

    if 'portfolio_account_id' not in columns:
        # No named FK constraint: SQLite can't add one to an existing table without a full
        # rebuild, and the column is only ever written with an id the app just read back.
        op.add_column('pefi_settings', sa.Column('portfolio_account_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns('pefi_settings')}

    if 'portfolio_account_id' in columns:
        op.drop_column('pefi_settings', 'portfolio_account_id')
