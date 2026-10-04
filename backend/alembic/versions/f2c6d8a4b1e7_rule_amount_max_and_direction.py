"""gripr: amount rules with a ceiling and a direction

Revision ID: f2c6d8a4b1e7
Revises: e8b4c2f6a9d1
Create Date: 2026-10-02 20:00:00.000000

A counterparty rule can match "at most this amount" (bank_counterparty_rules.amount_max -- Trade
Republic's saveback varies month to month but never exceeds €15) and only money going one way
(direction: "out" or "in"), so the saveback reward coming in on the 1st isn't read as the
purchase going out on the 2nd. See the addendum on docs/adr/0029-ing-transactions-into-gripr.md.

Guarded with an inspector, as app.main's create_all may already have added the columns.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f2c6d8a4b1e7'
down_revision: str | None = 'e8b4c2f6a9d1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

COLUMNS = (('amount_max', sa.Numeric(14, 2)), ('direction', sa.String(3)))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = [c['name'] for c in inspector.get_columns('bank_counterparty_rules')]
    for name, type_ in COLUMNS:
        if name not in existing:
            op.add_column('bank_counterparty_rules', sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    op.execute("DELETE FROM bank_counterparty_rules WHERE iban IS NULL AND text_contains IS NULL AND amount IS NULL")
    existing = [c['name'] for c in inspector.get_columns('bank_counterparty_rules')]
    with op.batch_alter_table('bank_counterparty_rules') as batch_op:
        for name, _ in COLUMNS:
            if name in existing:
                batch_op.drop_column(name)
