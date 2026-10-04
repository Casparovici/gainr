"""gardnr: a care schedule can have a start date

Revision ID: c8e2a6f4d1b9
Revises: b3f7a1c9d5e2
Create Date: 2026-10-02 23:30:00.000000

garden_care_schedules.start_date: the first occurrence, so "fertilize every 2 weeks, starting
next Monday" can be entered instead of the first due date always being one interval after the
schedule was created. Nullable with no backfill: existing schedules keep the creation-date
fallback, so none of their due dates move. See docs/adr/0012.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c8e2a6f4d1b9'
down_revision: str | None = 'b3f7a1c9d5e2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'start_date' not in [c['name'] for c in inspector.get_columns('garden_care_schedules')]:
        op.add_column('garden_care_schedules', sa.Column('start_date', sa.Date(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'start_date' in [c['name'] for c in inspector.get_columns('garden_care_schedules')]:
        with op.batch_alter_table('garden_care_schedules') as batch_op:
            batch_op.drop_column('start_date')
