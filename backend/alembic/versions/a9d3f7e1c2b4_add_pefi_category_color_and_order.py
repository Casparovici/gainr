"""add color and sort_order to pefi_categories

Revision ID: a9d3f7e1c2b4
Revises: f4a1c8e2d6b7
Create Date: 2026-09-12 12:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the columns exist before the migration runs.

Backfills sort_order in the same order the app already displays categories (kind, parent group,
then name), so applying this migration doesn't reshuffle anything — reordering only happens once
someone actually drags a tile. color is left null for every row: null means "derive it from the
palette," which is exactly what every category showed before this column existed.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'a9d3f7e1c2b4'
down_revision: str | None = 'f4a1c8e2d6b7'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_categories')]

    if 'color' not in columns:
        op.add_column('pefi_categories', sa.Column('color', sa.String(length=7), nullable=True))
    if 'sort_order' not in columns:
        op.add_column('pefi_categories', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))

    conn = op.get_bind()
    groups: dict[tuple[str, int | None], list[int]] = {}
    for category_id, kind, parent_id in conn.execute(
        sa.text('SELECT id, kind, parent_id FROM pefi_categories ORDER BY kind, parent_id, name')
    ):
        groups.setdefault((kind, parent_id), []).append(category_id)
    for ids in groups.values():
        for position, category_id in enumerate(ids):
            conn.execute(
                sa.text('UPDATE pefi_categories SET sort_order = :pos WHERE id = :id'),
                {'pos': position, 'id': category_id},
            )


def downgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_categories')]
    with op.batch_alter_table('pefi_categories') as batch_op:
        if 'sort_order' in columns:
            batch_op.drop_column('sort_order')
        if 'color' in columns:
            batch_op.drop_column('color')
