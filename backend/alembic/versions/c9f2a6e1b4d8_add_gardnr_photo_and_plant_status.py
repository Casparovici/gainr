"""add garden_care_logs.photo/photo_content_type and garden_plants.status

Revision ID: c9f2a6e1b4d8
Revises: b6e1d4f9a2c7
Create Date: 2026-09-19 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the columns exist before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c9f2a6e1b4d8'
down_revision: str | None = 'b6e1d4f9a2c7'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    log_columns = [c['name'] for c in inspector.get_columns('garden_care_logs')]
    if 'photo' not in log_columns:
        op.add_column('garden_care_logs', sa.Column('photo', sa.LargeBinary(), nullable=True))
    if 'photo_content_type' not in log_columns:
        op.add_column('garden_care_logs', sa.Column('photo_content_type', sa.String(50), nullable=True))

    plant_columns = [c['name'] for c in inspector.get_columns('garden_plants')]
    if 'status' not in plant_columns:
        # SQLAlchemy's Enum type persists the Python member NAME by default (not .value) --
        # matching every other enum column already added this way (marker_shape, icon).
        op.add_column(
            'garden_plants',
            sa.Column(
                'status',
                sa.Enum('THRIVING', 'STRUGGLING', 'DEAD', name='gardenplantstatus'),
                nullable=False,
                server_default='THRIVING',
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    plant_columns = [c['name'] for c in inspector.get_columns('garden_plants')]
    if 'status' in plant_columns:
        with op.batch_alter_table('garden_plants') as batch_op:
            batch_op.drop_column('status')

    log_columns = [c['name'] for c in inspector.get_columns('garden_care_logs')]
    with op.batch_alter_table('garden_care_logs') as batch_op:
        if 'photo_content_type' in log_columns:
            batch_op.drop_column('photo_content_type')
        if 'photo' in log_columns:
            batch_op.drop_column('photo')
