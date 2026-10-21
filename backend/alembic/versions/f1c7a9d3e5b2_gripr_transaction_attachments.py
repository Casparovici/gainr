"""gripr: files attached to a transaction

Revision ID: f1c7a9d3e5b2
Revises: e8b4d1f6a3c9
Create Date: 2026-10-05 20:00:00.000000

pefi_transaction_attachments: one row per file (an invoice, a receipt), the bytes stored in the
row so the backup covers them -- gainr's table's twin. See docs/adr/0035-transaction-attachments.md.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f1c7a9d3e5b2'
down_revision: str | None = 'e8b4d1f6a3c9'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table('pefi_transaction_attachments'):
        op.create_table(
            'pefi_transaction_attachments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('transaction_id', sa.Integer(), sa.ForeignKey('pefi_transactions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('filename', sa.String(255), nullable=False),
            sa.Column('content_type', sa.String(50), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('content', sa.LargeBinary(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_pefi_transaction_attachments_transaction_id', 'pefi_transaction_attachments', ['transaction_id'])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('pefi_transaction_attachments'):
        op.drop_index('ix_pefi_transaction_attachments_transaction_id', table_name='pefi_transaction_attachments')
        op.drop_table('pefi_transaction_attachments')
