"""add gardy tables

Revision ID: 68222d8b6433
Revises: e73ac4a45514
Create Date: 2026-09-15 22:34:59.132130

Guarded with an inspector, same as every migration since the logo one: app.main calls
Base.metadata.create_all on startup, so on a database already booted against this code the
tables exist before the migration ever runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '68222d8b6433'
down_revision: str | None = 'e73ac4a45514'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()

    if 'garden_areas' not in tables:
        op.create_table(
            'garden_areas',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'garden_plants' not in tables:
        op.create_table(
            'garden_plants',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('area_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('species', sa.String(length=200), nullable=True),
            sa.Column('type', sa.Enum('PLANT', 'TREE', 'SHRUB', 'OTHER', name='gardenplanttype'), nullable=False),
            sa.Column('planted_date', sa.Date(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('x', sa.Numeric(precision=5, scale=2), nullable=True),
            sa.Column('y', sa.Numeric(precision=5, scale=2), nullable=True),
            sa.Column('is_archived', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.ForeignKeyConstraint(['area_id'], ['garden_areas.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_garden_plants_area_id'), 'garden_plants', ['area_id'], unique=False)

    if 'garden_zones' not in tables:
        op.create_table(
            'garden_zones',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('area_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('shape', sa.Enum('RECT', 'CIRCLE', name='gardenzoneshape'), nullable=False),
            sa.Column('x', sa.Numeric(precision=5, scale=2), nullable=False),
            sa.Column('y', sa.Numeric(precision=5, scale=2), nullable=False),
            sa.Column('width', sa.Numeric(precision=5, scale=2), nullable=False),
            sa.Column('height', sa.Numeric(precision=5, scale=2), nullable=False),
            sa.Column('color', sa.String(length=7), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['area_id'], ['garden_areas.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_garden_zones_area_id'), 'garden_zones', ['area_id'], unique=False)

    if 'garden_care_logs' not in tables:
        op.create_table(
            'garden_care_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('plant_id', sa.Integer(), nullable=False),
            sa.Column(
                'action_type',
                sa.Enum('WATER', 'PRUNE', 'TRIM', 'FERTILIZE', 'HARVEST', 'PEST_CONTROL', 'OTHER', name='gardenactiontype'),
                nullable=False,
            ),
            sa.Column('custom_label', sa.String(length=120), nullable=True),
            sa.Column('performed_on', sa.Date(), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.ForeignKeyConstraint(['plant_id'], ['garden_plants.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_garden_care_logs_plant_id'), 'garden_care_logs', ['plant_id'], unique=False)

    if 'garden_care_schedules' not in tables:
        op.create_table(
            'garden_care_schedules',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('plant_id', sa.Integer(), nullable=False),
            sa.Column(
                'action_type',
                sa.Enum('WATER', 'PRUNE', 'TRIM', 'FERTILIZE', 'HARVEST', 'PEST_CONTROL', 'OTHER', name='gardenactiontype'),
                nullable=False,
            ),
            sa.Column('custom_label', sa.String(length=120), nullable=True),
            sa.Column('interval_value', sa.Integer(), nullable=False),
            sa.Column('frequency', sa.Enum('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY', name='gardenschedulefrequency'), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('notes', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.ForeignKeyConstraint(['plant_id'], ['garden_plants.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_garden_care_schedules_plant_id'), 'garden_care_schedules', ['plant_id'], unique=False)


def downgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()

    if 'garden_care_schedules' in tables:
        op.drop_index(op.f('ix_garden_care_schedules_plant_id'), table_name='garden_care_schedules')
        op.drop_table('garden_care_schedules')
    if 'garden_care_logs' in tables:
        op.drop_index(op.f('ix_garden_care_logs_plant_id'), table_name='garden_care_logs')
        op.drop_table('garden_care_logs')
    if 'garden_zones' in tables:
        op.drop_index(op.f('ix_garden_zones_area_id'), table_name='garden_zones')
        op.drop_table('garden_zones')
    if 'garden_plants' in tables:
        op.drop_index(op.f('ix_garden_plants_area_id'), table_name='garden_plants')
        op.drop_table('garden_plants')
    if 'garden_areas' in tables:
        op.drop_table('garden_areas')
