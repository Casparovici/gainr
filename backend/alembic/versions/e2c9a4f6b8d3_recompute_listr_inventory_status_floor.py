"""recompute grecipe_items.inventory_status against the new floor (0, not 1)

Revision ID: e2c9a4f6b8d3
Revises: f7c2e4a8d6b1
Create Date: 2026-09-22 00:00:00.000000

No schema change -- inventory_status's compute rule changed (see docs/adr/0015-listr-inventory.md's
fourth addendum): the floor that forced "out" at count<=1 regardless of minimum is now count==0
only, so a minimum=1 item at count=1 is in_stock rather than permanently out. Every already-tracked
row (inventory_status is not null) gets recomputed once here against the new rule, same as
e5f8b3d1a9c7 did when the minimum column itself first landed.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e2c9a4f6b8d3'
down_revision: str | None = 'f7c2e4a8d6b1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _compute_status(count: int, minimum: int) -> str:
    if count == 0:
        return 'out'
    if count < minimum:
        return 'low'
    return 'in_stock'


def upgrade() -> None:
    conn = op.get_bind()
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
    """Not reversible -- the old floor's information (which rows were forced to `out` at
    count<=1 purely by the floor, versus genuinely below minimum) isn't retained anywhere."""
    pass
