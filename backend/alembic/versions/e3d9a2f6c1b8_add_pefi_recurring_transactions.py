"""add pefi_recurring_transactions

Revision ID: e3d9a2f6c1b8
Revises: b2e6f9a1c3d5
Create Date: 2026-09-12 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the table exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'e3d9a2f6c1b8'
down_revision: str | None = 'b2e6f9a1c3d5'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()

    if 'pefi_recurring_transactions' not in tables:
        op.create_table(
            'pefi_recurring_transactions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column(
                'type',
                sa.Enum('EXPENSE', 'INCOME', 'TRANSFER', name='pefitransactiontype'),
                nullable=False,
            ),
            sa.Column('amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('account_id', sa.Integer(), nullable=False),
            sa.Column('counter_account_id', sa.Integer(), nullable=True),
            sa.Column('category_id', sa.Integer(), nullable=True),
            sa.Column('notes', sa.String(length=500), nullable=True),
            sa.Column(
                'frequency',
                sa.Enum('WEEKLY', 'MONTHLY', 'YEARLY', name='pefirecurrencefrequency'),
                nullable=False,
            ),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('end_date', sa.Date(), nullable=True),
            sa.Column('next_due_date', sa.Date(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['account_id'], ['pefi_accounts.id']),
            sa.ForeignKeyConstraint(['counter_account_id'], ['pefi_accounts.id']),
            sa.ForeignKeyConstraint(['category_id'], ['pefi_categories.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_pefi_recurring_transactions_account_id', 'pefi_recurring_transactions', ['account_id']
        )
        op.create_index(
            'ix_pefi_recurring_transactions_next_due_date', 'pefi_recurring_transactions', ['next_due_date']
        )


def downgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if 'pefi_recurring_transactions' in tables:
        op.drop_table('pefi_recurring_transactions')
