"""picnic: delivery processing settings/records, and prices on mapped products

Revision ID: a3c9e5f1b7d2
Revises: e2a6c8f4b9d7
Create Date: 2026-10-02 00:00:00.000000

Two single-purpose tables for processing completed Picnic deliveries into gripr and Voorraad
(picnic_sync_settings, a single row; picnic_synced_deliveries, one row per processed delivery),
and three nullable columns on grecipe_items for the mapped Picnic product's price. See
docs/adr/0027-picnic-deliveries-into-gripr-and-voorraad.md.

Guarded with an inspector for the same reason every migration since the logo one is.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a3c9e5f1b7d2'
down_revision: str | None = 'e2a6c8f4b9d7'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

ITEM_COLUMNS = (
    ('picnic_price', sa.Numeric(10, 2)),
    ('picnic_unit_quantity', sa.String(60)),
    ('picnic_price_at', sa.DateTime()),
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('picnic_sync_settings'):
        op.create_table(
            'picnic_sync_settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('gripr_account_id', sa.Integer(), sa.ForeignKey('pefi_accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('gripr_category_id', sa.Integer(), sa.ForeignKey('pefi_categories.id', ondelete='SET NULL'), nullable=True),
            sa.Column('since', sa.Date(), nullable=True),
            sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        )
    if not inspector.has_table('picnic_synced_deliveries'):
        op.create_table(
            'picnic_synced_deliveries',
            sa.Column('delivery_id', sa.String(32), primary_key=True),
            sa.Column('delivered_on', sa.Date(), nullable=False),
            sa.Column('synced_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('orders_booked', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('orders_matched', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('items_restocked', sa.Integer(), nullable=False, server_default='0'),
        )
    columns = [c['name'] for c in inspector.get_columns('grecipe_items')]
    for name, type_ in ITEM_COLUMNS:
        if name not in columns:
            op.add_column('grecipe_items', sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('grecipe_items')]
    with op.batch_alter_table('grecipe_items') as batch_op:
        for name, _ in ITEM_COLUMNS:
            if name in columns:
                batch_op.drop_column(name)
    for table in ('picnic_synced_deliveries', 'picnic_sync_settings'):
        if inspector.has_table(table):
            op.drop_table(table)
