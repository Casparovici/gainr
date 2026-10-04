"""add linked_loan_account_id to pefi_categories

Revision ID: e8f4a6c2b9d3
Revises: d5e9c3a7f1b2
Create Date: 2026-09-13 00:00:00.000002

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the column exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e8f4a6c2b9d3'
down_revision: str | None = 'd5e9c3a7f1b2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_categories')]
    if 'linked_loan_account_id' not in columns:
        # A plain column, not a DB-level FK constraint: SQLite can't ALTER TABLE ADD COLUMN
        # with a foreign key without a full table rebuild (batch mode), and this app doesn't
        # otherwise rely on DB-enforced FK integrity -- the SQLAlchemy model still declares the
        # relationship for query/join purposes.
        op.add_column('pefi_categories', sa.Column('linked_loan_account_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    columns = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('pefi_categories')]
    if 'linked_loan_account_id' in columns:
        with op.batch_alter_table('pefi_categories') as batch_op:
            batch_op.drop_column('linked_loan_account_id')
