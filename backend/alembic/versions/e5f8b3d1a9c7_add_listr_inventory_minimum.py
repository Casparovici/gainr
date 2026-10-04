"""add grecipe_items.inventory_minimum, recompute inventory_status from it

Revision ID: e5f8b3d1a9c7
Revises: d3a7c5e9f1b6
Create Date: 2026-09-19 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the column exists before the migration runs.

inventory_status stops being a value the client sets directly and becomes computed from
inventory_count vs inventory_minimum (see docs/adr/0015-listr-inventory.md's second addendum),
so any row already tracked (inventory_status is not null) gets its status recomputed once here
against the new rule rather than left holding a value nothing will touch again until its count
or minimum next changes.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e5f8b3d1a9c7'
down_revision: str | None = 'd3a7c5e9f1b6'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _compute_status(count: int, minimum: int) -> str:
    if count <= 1:
        return 'out'
    if count < minimum:
        return 'low'
    return 'in_stock'


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('grecipe_items')]
    if 'inventory_minimum' not in columns:
        op.add_column('grecipe_items', sa.Column('inventory_minimum', sa.Integer(), nullable=False, server_default='0'))

    items = sa.table(
        'grecipe_items',
        sa.column('id', sa.Integer),
        sa.column('inventory_status', sa.String),
        sa.column('inventory_count', sa.Integer),
        sa.column('inventory_minimum', sa.Integer),
    )
    tracked = conn.execute(
        sa.select(items.c.id, items.c.inventory_count, items.c.inventory_minimum).where(items.c.inventory_status.is_not(None))
    ).fetchall()
    for row in tracked:
        new_status = _compute_status(row.inventory_count or 0, row.inventory_minimum or 0)
        conn.execute(items.update().where(items.c.id == row.id).values(inventory_status=new_status))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('grecipe_items')]
    if 'inventory_minimum' in columns:
        with op.batch_alter_table('grecipe_items') as batch_op:
            batch_op.drop_column('inventory_minimum')
