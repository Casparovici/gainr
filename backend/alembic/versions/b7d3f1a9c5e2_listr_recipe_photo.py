"""listr: a recipe can carry a photo

Revision ID: b7d3f1a9c5e2
Revises: a3c7e1f9b5d2
Create Date: 2026-10-18 15:00:00.000000

`photo` and `photo_content_type` on grecipe_recipes, stored inline like gardnr's care-log photos
(docs/adr/0043-listr-recipe-photos.md). Guarded with an inspector because app.main calls
Base.metadata.create_all on startup, which never adds a column to an existing table but does
create it on a fresh one.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b7d3f1a9c5e2'
down_revision: str | None = 'a3c7e1f9b5d2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('grecipe_recipes')]
    if 'photo' not in columns:
        op.add_column('grecipe_recipes', sa.Column('photo', sa.LargeBinary(), nullable=True))
    if 'photo_content_type' not in columns:
        op.add_column('grecipe_recipes', sa.Column('photo_content_type', sa.String(50), nullable=True))


def downgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('grecipe_recipes')]
    with op.batch_alter_table('grecipe_recipes') as batch_op:
        if 'photo_content_type' in columns:
            batch_op.drop_column('photo_content_type')
        if 'photo' in columns:
            batch_op.drop_column('photo')
