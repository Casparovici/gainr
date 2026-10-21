"""briefr: recipe suggestions on findings, and the page a listr recipe came from

Revision ID: c3f7a9d2e5b4
Revises: b8e2c5a1d7f3
Create Date: 2026-10-21 10:00:00.000000

A nullable `briefr_report_items.recipe` (a suggested recipe as JSON) and a nullable, unique
`grecipe_recipes.source_url`. Nothing to backfill: no finding had a recipe and no recipe had a
source before. Guarded with an inspector because app.main's create_all may already have added
the columns. See docs/adr/0054-briefr-home-chef.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c3f7a9d2e5b4'
down_revision: str | None = 'b8e2c5a1d7f3'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    columns = {c['name'] for c in inspector.get_columns('briefr_report_items')}
    if 'recipe' not in columns:
        op.add_column('briefr_report_items', sa.Column('recipe', sa.Text(), nullable=True))

    columns = {c['name'] for c in inspector.get_columns('grecipe_recipes')}
    if 'source_url' not in columns:
        op.add_column('grecipe_recipes', sa.Column('source_url', sa.String(500), nullable=True))
    indexes = {i['name'] for i in inspector.get_indexes('grecipe_recipes')}
    if 'ix_grecipe_recipes_source_url' not in indexes:
        op.create_index('ix_grecipe_recipes_source_url', 'grecipe_recipes', ['source_url'], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {i['name'] for i in inspector.get_indexes('grecipe_recipes')}
    if 'ix_grecipe_recipes_source_url' in indexes:
        op.drop_index('ix_grecipe_recipes_source_url', table_name='grecipe_recipes')
    columns = {c['name'] for c in inspector.get_columns('grecipe_recipes')}
    if 'source_url' in columns:
        with op.batch_alter_table('grecipe_recipes') as batch:
            batch.drop_column('source_url')
    columns = {c['name'] for c in inspector.get_columns('briefr_report_items')}
    if 'recipe' in columns:
        with op.batch_alter_table('briefr_report_items') as batch:
            batch.drop_column('recipe')
