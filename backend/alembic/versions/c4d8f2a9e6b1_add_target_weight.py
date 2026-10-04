"""add target weight (assets.target_weight_pct, portfolio_settings table)

Revision ID: c4d8f2a9e6b1
Revises: a7c2e9f4b6d1
Create Date: 2026-09-13 00:00:00.000000

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code
the column/table exists before the migration runs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c4d8f2a9e6b1'
down_revision: str | None = 'a7c2e9f4b6d1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    columns = [c['name'] for c in inspector.get_columns('assets')]
    if 'target_weight_pct' not in columns:
        op.add_column('assets', sa.Column('target_weight_pct', sa.Numeric(5, 2), nullable=True))

    if not inspector.has_table('portfolio_settings'):
        op.create_table(
            'portfolio_settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('cash_target_weight_pct', sa.Numeric(5, 2), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if inspector.has_table('portfolio_settings'):
        op.drop_table('portfolio_settings')

    columns = [c['name'] for c in inspector.get_columns('assets')]
    if 'target_weight_pct' in columns:
        with op.batch_alter_table('assets') as batch_op:
            batch_op.drop_column('target_weight_pct')
