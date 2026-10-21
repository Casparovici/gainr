"""trainr: workouts remember where an import got them from (source_ref)

Revision ID: c4f8e2a7b1d6
Revises: b7e3c9a1d5f2
Create Date: 2026-10-12 16:00:00.000000

A nullable, unique trainr_workouts.source_ref ("strava:<activity id>") so the Strava import is
idempotent. See the addendum in docs/adr/0037-trainr-module.md. Guarded because create_all never
adds a column to an existing table, so a database booted against this code may or may not have it.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c4f8e2a7b1d6'
down_revision: str | None = 'b7e3c9a1d5f2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('trainr_workouts')}
    if 'source_ref' not in columns:
        with op.batch_alter_table('trainr_workouts') as batch:
            batch.add_column(sa.Column('source_ref', sa.String(64), nullable=True))
            batch.create_unique_constraint('uq_trainr_workouts_source_ref', ['source_ref'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('trainr_workouts')}
    if 'source_ref' in columns:
        with op.batch_alter_table('trainr_workouts') as batch:
            batch.drop_constraint('uq_trainr_workouts_source_ref', type_='unique')
            batch.drop_column('source_ref')
