"""add grecipe recipe categories and meal plan (weekplanner)

Revision ID: b8f1c3d6e9a2
Revises: a3c7e5f9b2d4
Create Date: 2026-09-13 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the tables exist before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b8f1c3d6e9a2'
down_revision: str | None = 'a3c7e5f9b2d4'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table('grecipe_recipe_categories'):
        op.create_table(
            'grecipe_recipe_categories',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False, unique=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('color', sa.String(7), nullable=True),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if not inspector.has_table('grecipe_recipe_category_links'):
        op.create_table(
            'grecipe_recipe_category_links',
            sa.Column('recipe_id', sa.Integer(), sa.ForeignKey('grecipe_recipes.id'), primary_key=True),
            sa.Column(
                'category_id', sa.Integer(), sa.ForeignKey('grecipe_recipe_categories.id'), primary_key=True
            ),
        )

    if not inspector.has_table('grecipe_meal_plan'):
        op.create_table(
            'grecipe_meal_plan',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('date', sa.Date(), nullable=False, unique=True),
            sa.Column('recipe_id', sa.Integer(), sa.ForeignKey('grecipe_recipes.id'), nullable=True),
            sa.Column('is_cooked', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_grecipe_meal_plan_date', 'grecipe_meal_plan', ['date'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ['grecipe_meal_plan', 'grecipe_recipe_category_links', 'grecipe_recipe_categories']:
        if inspector.has_table(table):
            op.drop_table(table)
