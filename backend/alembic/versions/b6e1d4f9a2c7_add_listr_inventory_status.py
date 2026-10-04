"""add grecipe_items.inventory_status

Revision ID: b6e1d4f9a2c7
Revises: a3d9f7b21c48
Create Date: 2026-09-19 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the column exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b6e1d4f9a2c7'
down_revision: str | None = 'a3d9f7b21c48'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('grecipe_items')]
    if 'inventory_status' not in columns:
        op.add_column('grecipe_items', sa.Column('inventory_status', sa.String(16), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('grecipe_items')]
    if 'inventory_status' in columns:
        with op.batch_alter_table('grecipe_items') as batch_op:
            batch_op.drop_column('inventory_status')
