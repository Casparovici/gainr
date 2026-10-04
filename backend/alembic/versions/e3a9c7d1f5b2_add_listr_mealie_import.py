"""add listr Mealie import: recipe source columns and the food->product mapping table

Revision ID: e3a9c7d1f5b2
Revises: a5b64c0f3d52
Create Date: 2026-09-29 00:00:00.000000

`grecipe_recipes.mealie_id`/`mealie_updated_at` mark a recipe as imported from Mealie (so a
re-import updates it instead of duplicating it) and `grecipe_mealie_foods` remembers which
catalog product each Mealie food means. See docs/adr/0022.

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the table/columns exist before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e3a9c7d1f5b2'
down_revision: str | None = 'a5b64c0f3d52'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    recipe_columns = [c['name'] for c in inspector.get_columns('grecipe_recipes')]
    if 'mealie_id' not in recipe_columns:
        op.add_column('grecipe_recipes', sa.Column('mealie_id', sa.String(64), nullable=True))
        op.create_index('ix_grecipe_recipes_mealie_id', 'grecipe_recipes', ['mealie_id'], unique=True)
    if 'mealie_updated_at' not in recipe_columns:
        op.add_column('grecipe_recipes', sa.Column('mealie_updated_at', sa.String(64), nullable=True))

    if 'grecipe_mealie_foods' not in inspector.get_table_names():
        op.create_table(
            'grecipe_mealie_foods',
            sa.Column('mealie_food_id', sa.String(64), primary_key=True),
            sa.Column('mealie_food_name', sa.String(200), nullable=False),
            sa.Column('grocery_item_id', sa.Integer(), sa.ForeignKey('grecipe_items.id'), nullable=False),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if 'grecipe_mealie_foods' in inspector.get_table_names():
        op.drop_table('grecipe_mealie_foods')

    recipe_columns = [c['name'] for c in inspector.get_columns('grecipe_recipes')]
    indexes = [i['name'] for i in inspector.get_indexes('grecipe_recipes')]
    with op.batch_alter_table('grecipe_recipes') as batch_op:
        if 'ix_grecipe_recipes_mealie_id' in indexes:
            batch_op.drop_index('ix_grecipe_recipes_mealie_id')
        if 'mealie_updated_at' in recipe_columns:
            batch_op.drop_column('mealie_updated_at')
        if 'mealie_id' in recipe_columns:
            batch_op.drop_column('mealie_id')
