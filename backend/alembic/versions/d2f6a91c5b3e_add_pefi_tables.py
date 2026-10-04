"""add pefi (personal finance) tables

Revision ID: d2f6a91c5b3e
Revises: c7a5e83b1d94
Create Date: 2026-09-11 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the tables exist before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'd2f6a91c5b3e'
down_revision: str | None = 'c7a5e83b1d94'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()

    if 'pefi_accounts' not in tables:
        op.create_table(
            'pefi_accounts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column(
                'type',
                sa.Enum('CHECKING', 'SAVINGS', 'INVESTMENT', 'CREDIT', 'LOAN', 'ASSET', name='pefiaccounttype'),
                nullable=False,
            ),
            sa.Column(
                'balance_mode',
                sa.Enum('TRANSACTIONAL', 'MANUAL', name='pefibalancemode'),
                nullable=False,
            ),
            sa.Column('opening_balance', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('manual_balance', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('currency', sa.String(length=8), nullable=False, server_default='EUR'),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
        )
        op.create_index('ix_pefi_accounts_name', 'pefi_accounts', ['name'])

    if 'pefi_categories' not in tables:
        op.create_table(
            'pefi_categories',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('kind', sa.Enum('EXPENSE', 'INCOME', name='peficategorykind'), nullable=False),
            sa.Column('parent_id', sa.Integer(), nullable=True),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.ForeignKeyConstraint(['parent_id'], ['pefi_categories.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'pefi_transactions' not in tables:
        op.create_table(
            'pefi_transactions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
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
            sa.Column('source_ref', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['account_id'], ['pefi_accounts.id']),
            sa.ForeignKeyConstraint(['counter_account_id'], ['pefi_accounts.id']),
            sa.ForeignKeyConstraint(['category_id'], ['pefi_categories.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('source_ref'),
        )
        op.create_index('ix_pefi_transactions_date', 'pefi_transactions', ['date'])
        op.create_index('ix_pefi_transactions_account_id', 'pefi_transactions', ['account_id'])
        op.create_index('ix_pefi_transactions_counter_account_id', 'pefi_transactions', ['counter_account_id'])
        op.create_index('ix_pefi_transactions_category_id', 'pefi_transactions', ['category_id'])

    if 'pefi_budgets' not in tables:
        op.create_table(
            'pefi_budgets',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('category_id', sa.Integer(), nullable=False),
            sa.Column('month', sa.Date(), nullable=False),
            sa.Column('amount', sa.Numeric(14, 2), nullable=False),
            sa.ForeignKeyConstraint(['category_id'], ['pefi_categories.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('category_id', 'month', name='uq_pefi_budget_category_month'),
        )
        op.create_index('ix_pefi_budgets_category_id', 'pefi_budgets', ['category_id'])
        op.create_index('ix_pefi_budgets_month', 'pefi_budgets', ['month'])


def downgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    for table in ('pefi_budgets', 'pefi_transactions', 'pefi_categories', 'pefi_accounts'):
        if table in tables:
            op.drop_table(table)
