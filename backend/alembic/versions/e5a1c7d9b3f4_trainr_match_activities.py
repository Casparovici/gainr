"""trainr: football and padel record calories and heart rate

Revision ID: e5a1c7d9b3f4
Revises: d9e3f1a6c2b8
Create Date: 2026-10-16 12:00:00.000000

Three nullable integer columns on trainr_workouts. The two new activity types need no DDL: the
enum is stored as plain text without a CHECK constraint. See the addendum in
docs/adr/0037-trainr-module.md. Guarded because create_all never adds a column to an existing
table, so a database booted against this code may or may not have them.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e5a1c7d9b3f4'
down_revision: str | None = 'd9e3f1a6c2b8'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

COLUMNS = ('calories_kcal', 'avg_heart_rate_bpm', 'max_heart_rate_bpm')


def upgrade() -> None:
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('trainr_workouts')}
    missing = [name for name in COLUMNS if name not in existing]
    if missing:
        with op.batch_alter_table('trainr_workouts') as batch:
            for name in missing:
                batch.add_column(sa.Column(name, sa.Integer(), nullable=True))


def downgrade() -> None:
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('trainr_workouts')}
    present = [name for name in COLUMNS if name in existing]
    if present:
        with op.batch_alter_table('trainr_workouts') as batch:
            for name in present:
                batch.drop_column(name)
