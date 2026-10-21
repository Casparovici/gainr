"""listr: supermarkets and the order their aisles come in

Revision ID: b8e2c5a1d7f3
Revises: a7d4f1c9e3b2
Create Date: 2026-10-20 21:00:00.000000

Two tables -- `grecipe_stores` and `grecipe_store_categories` (a store's categories in walking
order) -- and a nullable `grecipe_lists.store_id`, the supermarket a list follows. Nothing to
backfill: a list with no store keeps following the global category order. Guarded with an
inspector because app.main's create_all may already have built the new tables. See
docs/adr/0052-listr-store-order.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b8e2c5a1d7f3'
down_revision: str | None = 'a7d4f1c9e3b2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table('grecipe_stores'):
        op.create_table(
            'grecipe_stores',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False, unique=True),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('is_archived', sa.Boolean(), nullable=False),
        )
    if not inspector.has_table('grecipe_store_categories'):
        op.create_table(
            'grecipe_store_categories',
            sa.Column('store_id', sa.Integer(), sa.ForeignKey('grecipe_stores.id'), primary_key=True),
            sa.Column('category_id', sa.Integer(), sa.ForeignKey('grecipe_categories.id'), primary_key=True),
            sa.Column('position', sa.Integer(), nullable=False),
        )

    columns = {c['name'] for c in inspector.get_columns('grecipe_lists')}
    if 'store_id' not in columns:
        with op.batch_alter_table('grecipe_lists') as batch:
            batch.add_column(sa.Column('store_id', sa.Integer(), nullable=True))
            batch.create_foreign_key(
                'fk_grecipe_lists_store_id', 'grecipe_stores', ['store_id'], ['id'], ondelete='SET NULL'
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('grecipe_lists')}
    if 'store_id' in columns:
        with op.batch_alter_table('grecipe_lists') as batch:
            batch.drop_constraint('fk_grecipe_lists_store_id', type_='foreignkey')
            batch.drop_column('store_id')
    for table in ('grecipe_store_categories', 'grecipe_stores'):
        if inspector.has_table(table):
            op.drop_table(table)
