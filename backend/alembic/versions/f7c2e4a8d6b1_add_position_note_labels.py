"""add position_note_labels and position_note_label_links

Revision ID: f7c2e4a8d6b1
Revises: e5f8b3d1a9c7
Create Date: 2026-09-19 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the tables exist before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f7c2e4a8d6b1'
down_revision: str | None = 'e5f8b3d1a9c7'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table('position_note_labels'):
        op.create_table(
            'position_note_labels',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(60), nullable=False, unique=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('color', sa.String(7), nullable=True),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if not inspector.has_table('position_note_label_links'):
        op.create_table(
            'position_note_label_links',
            sa.Column('note_id', sa.Integer(), sa.ForeignKey('position_notes.id'), primary_key=True),
            sa.Column('label_id', sa.Integer(), sa.ForeignKey('position_note_labels.id'), primary_key=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ['position_note_label_links', 'position_note_labels']:
        if inspector.has_table(table):
            op.drop_table(table)
