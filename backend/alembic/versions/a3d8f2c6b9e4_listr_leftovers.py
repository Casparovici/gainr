"""listr: leftovers, and a weekplanner day that can eat one

Revision ID: a3d8f2c6b9e4
Revises: f1c7a9d3e5b2
Create Date: 2026-10-11 12:00:00.000000

grecipe_leftovers plus grecipe_meal_plan.leftover_id / leftover_consumed. See
docs/adr/0036-listr-leftovers.md. Guarded with an inspector because app.main runs
Base.metadata.create_all on startup, so the table can already exist on a database booted against
this code; create_all never adds a column to an existing table, so the columns are checked apart.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a3d8f2c6b9e4'
down_revision: str | None = 'f1c7a9d3e5b2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table('grecipe_leftovers'):
        op.create_table(
            'grecipe_leftovers',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('recipe_id', sa.Integer(), sa.ForeignKey('grecipe_recipes.id', ondelete='SET NULL'), nullable=True),
            sa.Column('meals', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('servings_per_meal', sa.Integer(), nullable=True),
            sa.Column('location', sa.String(16), nullable=False, server_default='freezer'),
            sa.Column('stored_on', sa.Date(), nullable=False),
            sa.Column('use_by', sa.Date(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    columns = {c['name'] for c in inspector.get_columns('grecipe_meal_plan')}
    with op.batch_alter_table('grecipe_meal_plan') as batch:
        if 'leftover_id' not in columns:
            batch.add_column(sa.Column('leftover_id', sa.Integer(), nullable=True))
            batch.create_foreign_key(
                'fk_grecipe_meal_plan_leftover_id', 'grecipe_leftovers', ['leftover_id'], ['id'], ondelete='SET NULL'
            )
        if 'leftover_consumed' not in columns:
            batch.add_column(sa.Column('leftover_consumed', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('grecipe_meal_plan')}
    with op.batch_alter_table('grecipe_meal_plan') as batch:
        if 'leftover_consumed' in columns:
            batch.drop_column('leftover_consumed')
        if 'leftover_id' in columns:
            batch.drop_constraint('fk_grecipe_meal_plan_leftover_id', type_='foreignkey')
            batch.drop_column('leftover_id')
    if inspector.has_table('grecipe_leftovers'):
        op.drop_table('grecipe_leftovers')
