"""add grecipe tables (categories, items, lists, list items, recipes, recipe ingredients)

Revision ID: a3c7e5f9b2d4
Revises: f2a7d4c9e1b6
Create Date: 2026-09-14 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the tables exist before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a3c7e5f9b2d4'
down_revision: str | None = 'f2a7d4c9e1b6'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table('grecipe_categories'):
        op.create_table(
            'grecipe_categories',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False, unique=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('color', sa.String(7), nullable=True),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if not inspector.has_table('grecipe_items'):
        op.create_table(
            'grecipe_items',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False, unique=True),
            sa.Column('category_id', sa.Integer(), nullable=False),
            sa.Column('default_unit', sa.String(32), nullable=False),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if not inspector.has_table('grecipe_lists'):
        op.create_table(
            'grecipe_lists',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )

    if not inspector.has_table('grecipe_list_items'):
        op.create_table(
            'grecipe_list_items',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('list_id', sa.Integer(), nullable=False),
            sa.Column('grocery_item_id', sa.Integer(), nullable=False),
            sa.Column('quantity', sa.Numeric(10, 3), nullable=False, server_default='1'),
            sa.Column('unit', sa.String(32), nullable=False),
            sa.Column('is_checked', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        )
        op.create_index('ix_grecipe_list_items_list_id', 'grecipe_list_items', ['list_id'])

    if not inspector.has_table('grecipe_recipes'):
        op.create_table(
            'grecipe_recipes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('servings', sa.Integer(), nullable=True),
            sa.Column('instructions', sa.Text(), nullable=False, server_default=''),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )

    if not inspector.has_table('grecipe_recipe_ingredients'):
        op.create_table(
            'grecipe_recipe_ingredients',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('recipe_id', sa.Integer(), nullable=False),
            sa.Column('grocery_item_id', sa.Integer(), nullable=False),
            sa.Column('quantity', sa.Numeric(10, 3), nullable=False, server_default='1'),
            sa.Column('unit', sa.String(32), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        )
        op.create_index(
            'ix_grecipe_recipe_ingredients_recipe_id', 'grecipe_recipe_ingredients', ['recipe_id']
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in [
        'grecipe_recipe_ingredients',
        'grecipe_recipes',
        'grecipe_list_items',
        'grecipe_lists',
        'grecipe_items',
        'grecipe_categories',
    ]:
        if inspector.has_table(table):
            op.drop_table(table)
