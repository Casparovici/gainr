"""journal notes can be linked to several positions

Revision ID: c4e9a7b2d1f3
Revises: b8d3e6f1a2c4
Create Date: 2026-09-30 00:00:00.000000

Replaces `position_notes.asset_id` (one position per note) with a `position_note_assets`
association table, backfilled with every existing note's single position, so nothing loses its
link. See docs/adr/0024-journal-notes-on-multiple-positions.md.

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so the (empty) association table can already exist
before this runs. The backfill therefore keys off the old column still being there, not off the
table being missing, and ignores rows already present.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c4e9a7b2d1f3'
down_revision: str | None = 'b8d3e6f1a2c4'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'position_note_assets' not in inspector.get_table_names():
        op.create_table(
            'position_note_assets',
            sa.Column('note_id', sa.Integer(), sa.ForeignKey('position_notes.id'), primary_key=True),
            sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id'), primary_key=True),
        )
        op.create_index('ix_position_note_assets_asset_id', 'position_note_assets', ['asset_id'])
        inspector = sa.inspect(bind)

    note_columns = [c['name'] for c in inspector.get_columns('position_notes')]
    if 'asset_id' in note_columns:
        op.execute(
            "INSERT INTO position_note_assets (note_id, asset_id) "
            "SELECT n.id, n.asset_id FROM position_notes n "
            "WHERE n.asset_id IS NOT NULL AND NOT EXISTS ("
            "  SELECT 1 FROM position_note_assets l WHERE l.note_id = n.id AND l.asset_id = n.asset_id)"
        )
        indexes = [i['name'] for i in inspector.get_indexes('position_notes')]
        with op.batch_alter_table('position_notes') as batch_op:
            if 'ix_position_notes_asset_id' in indexes:
                batch_op.drop_index('ix_position_notes_asset_id')
            batch_op.drop_column('asset_id')


def downgrade() -> None:
    # Lossy by nature: a note linked to several positions keeps only its lowest asset id.
    inspector = sa.inspect(op.get_bind())
    note_columns = [c['name'] for c in inspector.get_columns('position_notes')]
    if 'asset_id' not in note_columns:
        with op.batch_alter_table('position_notes') as batch_op:
            batch_op.add_column(sa.Column('asset_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_position_notes_asset_id', 'assets', ['asset_id'], ['id'])
            batch_op.create_index('ix_position_notes_asset_id', ['asset_id'])
    if 'position_note_assets' in inspector.get_table_names():
        op.execute(
            "UPDATE position_notes SET asset_id = "
            "(SELECT MIN(asset_id) FROM position_note_assets l WHERE l.note_id = position_notes.id)"
        )
        op.drop_table('position_note_assets')
