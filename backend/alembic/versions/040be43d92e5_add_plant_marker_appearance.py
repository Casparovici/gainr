"""add plant marker appearance

Revision ID: 040be43d92e5
Revises: 68222d8b6433
Create Date: 2026-09-15 23:14:05.135803

Guarded with an inspector, same as every migration since the logo one: app.main calls
Base.metadata.create_all on startup, so on a database already booted against this code the
columns exist before the migration ever runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '040be43d92e5'
down_revision: str | None = '68222d8b6433'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns('garden_plants')}

    if 'marker_shape' not in columns:
        op.add_column(
            'garden_plants',
            sa.Column(
                'marker_shape', sa.Enum('RECT', 'CIRCLE', name='gardenzoneshape'), nullable=False, server_default='CIRCLE'
            ),
        )
    if 'marker_width' not in columns:
        op.add_column('garden_plants', sa.Column('marker_width', sa.Numeric(precision=5, scale=2), nullable=False, server_default='6.00'))
    if 'marker_height' not in columns:
        op.add_column('garden_plants', sa.Column('marker_height', sa.Numeric(precision=5, scale=2), nullable=False, server_default='6.00'))
    if 'icon' not in columns:
        op.add_column(
            'garden_plants',
            sa.Column(
                'icon',
                sa.Enum('SPROUT', 'TREE_DECIDUOUS', 'TREE_PINE', 'TREES', 'LEAF', 'LEAFY_GREEN', 'FLOWER', 'FLOWER2', name='gardenplanticon'),
                nullable=True,
            ),
        )


def downgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns('garden_plants')}

    if 'icon' in columns:
        op.drop_column('garden_plants', 'icon')
    if 'marker_height' in columns:
        op.drop_column('garden_plants', 'marker_height')
    if 'marker_width' in columns:
        op.drop_column('garden_plants', 'marker_width')
    if 'marker_shape' in columns:
        op.drop_column('garden_plants', 'marker_shape')
