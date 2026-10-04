"""add pefi_bank_logos table and pefi_accounts.bank_logo_key

Revision ID: c4d8e2a7f5b1
Revises: b8f1c3d6e9a2
Create Date: 2026-09-13 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the table/column exist before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c4d8e2a7f5b1'
down_revision: str | None = 'b8f1c3d6e9a2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table('pefi_bank_logos'):
        op.create_table(
            'pefi_bank_logos',
            sa.Column('key', sa.String(32), primary_key=True),
            sa.Column('content_type', sa.String(64), nullable=False),
            sa.Column('image', sa.LargeBinary(), nullable=False),
            sa.Column('source_url', sa.String(500), nullable=False),
            sa.Column('fetched_at', sa.DateTime(), server_default=sa.func.now()),
        )

    columns = [c['name'] for c in inspector.get_columns('pefi_accounts')]
    if 'bank_logo_key' not in columns:
        op.add_column('pefi_accounts', sa.Column('bank_logo_key', sa.String(32), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('pefi_bank_logos'):
        op.drop_table('pefi_bank_logos')
    columns = [c['name'] for c in inspector.get_columns('pefi_accounts')]
    if 'bank_logo_key' in columns:
        with op.batch_alter_table('pefi_accounts') as batch_op:
            batch_op.drop_column('bank_logo_key')
