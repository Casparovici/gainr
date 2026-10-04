"""add position_events: user-entered company milestones for the Calendar tab

Revision ID: d7f2b9c4e6a1
Revises: c4e9a7b2d1f3
Create Date: 2026-09-30 00:00:00.000000

Investor days, AGMs and the like, which no free data source provides -- earnings and dividend
dates come from Yahoo and are only cached, not stored here. See docs/adr/0025.

Guarded with an inspector for the same reason every migration since the logo one is.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd7f2b9c4e6a1'
down_revision: str | None = 'c4e9a7b2d1f3'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    if 'position_events' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'position_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column(
            'kind',
            sa.Enum('INVESTOR_DAY', 'CAPITAL_MARKETS_DAY', 'AGM', 'PRODUCT_EVENT', 'OTHER', name='positioneventkind'),
            nullable=False,
        ),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_position_events_asset_id', 'position_events', ['asset_id'])
    op.create_index('ix_position_events_date', 'position_events', ['date'])


def downgrade() -> None:
    if 'position_events' in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table('position_events')
