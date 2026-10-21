"""taskr: tasks the user adds in taskr itself

Revision ID: a3c7e1f9b5d2
Revises: f2b8d4a6c1e7
Create Date: 2026-10-18 15:00:00.000000

A new table, `taskr_tasks`: the one kind of agenda item taskr owns rather than reads from another
module (the addendum on docs/adr/0038-taskr-agenda.md). Guarded, because app.main's create_all may
have built it already.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a3c7e1f9b5d2'
down_revision: str | None = 'f2b8d4a6c1e7'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table('taskr_tasks'):
        op.create_table(
            'taskr_tasks',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('due_date', sa.Date(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_taskr_tasks_due_date', 'taskr_tasks', ['due_date'])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('taskr_tasks'):
        op.drop_table('taskr_tasks')
