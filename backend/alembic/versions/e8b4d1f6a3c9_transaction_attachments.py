"""gainr: files attached to a transaction

Revision ID: e8b4d1f6a3c9
Revises: d3f7a2b9c6e1
Create Date: 2026-10-05 18:00:00.000000

transaction_attachments: one row per file (an invoice, a contract note), the bytes stored in the
row so the daily backup covers them. See docs/adr/0035-transaction-attachments.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e8b4d1f6a3c9'
down_revision: str | None = 'd3f7a2b9c6e1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table('transaction_attachments'):
        op.create_table(
            'transaction_attachments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('transaction_id', sa.Integer(), sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('filename', sa.String(255), nullable=False),
            sa.Column('content_type', sa.String(50), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('content', sa.LargeBinary(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_transaction_attachments_transaction_id', 'transaction_attachments', ['transaction_id'])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('transaction_attachments'):
        op.drop_index('ix_transaction_attachments_transaction_id', table_name='transaction_attachments')
        op.drop_table('transaction_attachments')
