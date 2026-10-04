"""add picnic_session table and grecipe_items.picnic_product_id/name

Revision ID: e73ac4a45514
Revises: c4d8e2a7f5b1
Create Date: 2026-09-14 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the table/columns exist before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e73ac4a45514'
down_revision: str | None = 'c4d8e2a7f5b1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table('picnic_session'):
        op.create_table(
            'picnic_session',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('auth_key', sa.String(200), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )

    columns = [c['name'] for c in inspector.get_columns('grecipe_items')]
    if 'picnic_product_id' not in columns:
        op.add_column('grecipe_items', sa.Column('picnic_product_id', sa.String(32), nullable=True))
    if 'picnic_product_name' not in columns:
        op.add_column('grecipe_items', sa.Column('picnic_product_name', sa.String(200), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('picnic_session'):
        op.drop_table('picnic_session')
    columns = [c['name'] for c in inspector.get_columns('grecipe_items')]
    with op.batch_alter_table('grecipe_items') as batch_op:
        if 'picnic_product_id' in columns:
            batch_op.drop_column('picnic_product_id')
        if 'picnic_product_name' in columns:
            batch_op.drop_column('picnic_product_name')
