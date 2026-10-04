"""add transactions.to_broker, for the new Transfer transaction type

Revision ID: b8f3e1c6a4d2
Revises: e2c9a4f6b8d3
Create Date: 2026-09-22 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the column exists before the migration runs. No CHECK constraint to update for the new
TransactionType.TRANSFER enum member -- `type` is a plain VARCHAR on SQLite (SQLAlchemy's Enum
type doesn't add a CHECK constraint here), so a new member needs no migration of its own.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b8f3e1c6a4d2'
down_revision: str | None = 'e2c9a4f6b8d3'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('transactions')]
    if 'to_broker' not in columns:
        op.add_column('transactions', sa.Column('to_broker', sa.String(length=64), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('transactions')]
    if 'to_broker' in columns:
        with op.batch_alter_table('transactions') as batch_op:
            batch_op.drop_column('to_broker')
