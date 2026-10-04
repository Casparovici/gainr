"""add pefi_savings_goals

Revision ID: c1d5f8a2e6b4
Revises: b8f3e1c6a4d2
Create Date: 2026-09-24 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the table exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c1d5f8a2e6b4'
down_revision: str | None = 'b8f3e1c6a4d2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if 'pefi_savings_goals' not in tables:
        # A plain integer column for account_id, not a DB-level FK constraint -- same rationale
        # as pefi_categories.linked_loan_account_id: this app doesn't rely on DB-enforced FK
        # integrity, and it keeps this table creatable in one op.create_table call.
        op.create_table(
            'pefi_savings_goals',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('account_id', sa.Integer(), nullable=False),
            sa.Column('month', sa.Date(), nullable=False),
            sa.Column('amount', sa.Numeric(14, 2), nullable=False),
            sa.UniqueConstraint('account_id', 'month', name='uq_gripr_savings_goal_account_month'),
        )
        op.create_index('ix_pefi_savings_goals_account_id', 'pefi_savings_goals', ['account_id'])
        op.create_index('ix_pefi_savings_goals_month', 'pefi_savings_goals', ['month'])


def downgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if 'pefi_savings_goals' in tables:
        op.drop_table('pefi_savings_goals')
