"""notr: notes, moving the Journal's notes and labels in

Revision ID: a7d4f1c9e3b2
Revises: f3b8d2a6c4e1
Create Date: 2026-10-20 18:00:00.000000

Creates notr's tables (notes, labels, their links to labels, positions, plants and recipes, and
pictures) and moves gainr's Journal into them: every `position_notes` row keeps its id, text,
dates, labels and position links, then the old tables are dropped. See docs/adr/0050-notr-notes.md.

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so the (empty) new tables can already exist before this
runs. The copy therefore keys off the old tables still being there, and ignores rows already
present. The deploy backs the database up before migrating.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a7d4f1c9e3b2'
down_revision: str | None = 'f3b8d2a6c4e1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _has(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has('notr_labels'):
        op.create_table(
            'notr_labels',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(60), nullable=False, unique=True),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('color', sa.String(7), nullable=True),
            sa.Column('is_archived', sa.Boolean(), nullable=False),
        )
    if not _has('notr_notes'):
        op.create_table(
            'notr_notes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('pinned', sa.Boolean(), nullable=False),
            sa.Column('is_archived', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if not _has('notr_note_label_links'):
        op.create_table(
            'notr_note_label_links',
            sa.Column('note_id', sa.Integer(), sa.ForeignKey('notr_notes.id'), primary_key=True),
            sa.Column('label_id', sa.Integer(), sa.ForeignKey('notr_labels.id'), primary_key=True),
        )
    for table, column, target in (
        ('notr_note_assets', 'asset_id', 'assets.id'),
        ('notr_note_plants', 'plant_id', 'garden_plants.id'),
        ('notr_note_recipes', 'recipe_id', 'grecipe_recipes.id'),
    ):
        if not _has(table):
            op.create_table(
                table,
                sa.Column('note_id', sa.Integer(), sa.ForeignKey('notr_notes.id'), primary_key=True),
                sa.Column(column, sa.Integer(), sa.ForeignKey(target), primary_key=True),
            )
            op.create_index(f'ix_{table}_{column}', table, [column])
    if not _has('notr_note_images'):
        op.create_table(
            'notr_note_images',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('note_id', sa.Integer(), sa.ForeignKey('notr_notes.id'), nullable=True),
            sa.Column('content_type', sa.String(50), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('content', sa.LargeBinary(), nullable=False),
        )
        op.create_index('ix_notr_note_images_note_id', 'notr_note_images', ['note_id'])

    if _has('position_notes'):
        # Portable "insert what isn't there yet" (no SQLite-only INSERT OR IGNORE).
        if _has('position_note_labels'):
            op.execute(
                "INSERT INTO notr_labels (id, name, sort_order, color, is_archived) "
                "SELECT l.id, l.name, l.sort_order, l.color, l.is_archived FROM position_note_labels l "
                "WHERE NOT EXISTS (SELECT 1 FROM notr_labels n WHERE n.id = l.id)"
            )
        op.execute(
            "INSERT INTO notr_notes (id, title, body, pinned, is_archived, created_at, updated_at) "
            "SELECT p.id, p.title, p.body, 0, 0, p.created_at, p.updated_at FROM position_notes p "
            "WHERE NOT EXISTS (SELECT 1 FROM notr_notes n WHERE n.id = p.id)"
        )
        if _has('position_note_assets'):
            op.execute(
                "INSERT INTO notr_note_assets (note_id, asset_id) "
                "SELECT l.note_id, l.asset_id FROM position_note_assets l "
                "WHERE NOT EXISTS (SELECT 1 FROM notr_note_assets n WHERE n.note_id = l.note_id AND n.asset_id = l.asset_id)"
            )
        if _has('position_note_label_links'):
            op.execute(
                "INSERT INTO notr_note_label_links (note_id, label_id) "
                "SELECT l.note_id, l.label_id FROM position_note_label_links l "
                "WHERE NOT EXISTS (SELECT 1 FROM notr_note_label_links n WHERE n.note_id = l.note_id AND n.label_id = l.label_id)"
            )
        for table in ('position_note_label_links', 'position_note_assets', 'position_notes', 'position_note_labels'):
            if _has(table):
                op.drop_table(table)


def downgrade() -> None:
    # Lossy by nature: plain notes and notes about plants or recipes have no home in the old
    # tables, and pictures, pins and archiving have none either. Notes about positions, their
    # labels and their positions go back.
    op.create_table(
        'position_note_labels',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(60), nullable=False, unique=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False),
    )
    op.create_table(
        'position_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'position_note_assets',
        sa.Column('note_id', sa.Integer(), sa.ForeignKey('position_notes.id'), primary_key=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id'), primary_key=True),
    )
    op.create_index('ix_position_note_assets_asset_id', 'position_note_assets', ['asset_id'])
    op.create_table(
        'position_note_label_links',
        sa.Column('note_id', sa.Integer(), sa.ForeignKey('position_notes.id'), primary_key=True),
        sa.Column('label_id', sa.Integer(), sa.ForeignKey('position_note_labels.id'), primary_key=True),
    )
    op.execute("INSERT INTO position_note_labels (id, name, sort_order, color, is_archived) SELECT id, name, sort_order, color, is_archived FROM notr_labels")
    op.execute(
        "INSERT INTO position_notes (id, title, body, created_at, updated_at) "
        "SELECT id, title, body, created_at, updated_at FROM notr_notes "
        "WHERE id IN (SELECT note_id FROM notr_note_assets)"
    )
    op.execute("INSERT INTO position_note_assets (note_id, asset_id) SELECT note_id, asset_id FROM notr_note_assets")
    op.execute(
        "INSERT INTO position_note_label_links (note_id, label_id) "
        "SELECT note_id, label_id FROM notr_note_label_links WHERE note_id IN (SELECT id FROM position_notes)"
    )
    for table in (
        'notr_note_images', 'notr_note_recipes', 'notr_note_plants', 'notr_note_assets',
        'notr_note_label_links', 'notr_notes', 'notr_labels',
    ):
        op.drop_table(table)
