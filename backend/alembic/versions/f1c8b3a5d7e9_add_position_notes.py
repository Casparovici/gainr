"""add position_notes

Revision ID: f1c8b3a5d7e9
Revises: a9d3f7e1c2b4
Create Date: 2026-09-12 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the table exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'f1c8b3a5d7e9'
down_revision: str | None = 'a9d3f7e1c2b4'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()

    if 'position_notes' not in tables:
        op.create_table(
            'position_notes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('asset_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_position_notes_asset_id', 'position_notes', ['asset_id'])


def downgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if 'position_notes' in tables:
        op.drop_table('position_notes')
