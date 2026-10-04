"""grecipe_items.picnic_image_id: the linked Picnic product's picture

Revision ID: b8d4f2a6c1e3
Revises: a3c9e5f1b7d2
Create Date: 2026-10-02 00:00:01.000000

Picnic's image id for the linked product, saved when it's picked and refreshed with its price;
the picture itself is public at Picnic's static image URL. Nullable: unlinked items have none.

Guarded with an inspector for the same reason every migration since the logo one is.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b8d4f2a6c1e3'
down_revision: str | None = 'a3c9e5f1b7d2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('grecipe_items')]
    if 'picnic_image_id' not in columns:
        op.add_column('grecipe_items', sa.Column('picnic_image_id', sa.String(80), nullable=True))


def downgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('grecipe_items')]
    if 'picnic_image_id' in columns:
        with op.batch_alter_table('grecipe_items') as batch_op:
            batch_op.drop_column('picnic_image_id')
