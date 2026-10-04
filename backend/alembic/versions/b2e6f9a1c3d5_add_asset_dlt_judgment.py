"""add dlt_judgment to assets

Revision ID: b2e6f9a1c3d5
Revises: f1c8b3a5d7e9
Create Date: 2026-09-12 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the column exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'b2e6f9a1c3d5'
down_revision: str | None = 'f1c8b3a5d7e9'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('assets')]

    if 'dlt_judgment' not in columns:
        op.add_column(
            'assets',
            sa.Column(
                'dlt_judgment',
                sa.Enum('ATTRACTIVE', 'NEUTRAL', 'CRITICAL', name='dltjudgment'),
                nullable=True,
            ),
        )


def downgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('assets')]
    if 'dlt_judgment' in columns:
        with op.batch_alter_table('assets') as batch_op:
            batch_op.drop_column('dlt_judgment')
