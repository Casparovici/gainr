"""gripr: banks that send amounts only, and amount rules

Revision ID: e8b4c2f6a9d1
Revises: d7a3b9e1c4f6
Create Date: 2026-10-02 18:00:00.000000

Trade Republic, through Enable Banking, sends only date, amount and direction for each entry. A
connection can now say so (bank_connections.amount_only, set for Trade Republic), and a
counterparty rule can match on an exact amount around a day of the month (amount, day_of_month)
-- how a monthly savings-plan purchase is recognised when there's no description to look at. See
the addendum on docs/adr/0029-ing-transactions-into-gripr.md.

Guarded with an inspector for the same reason every migration since the logo one is -- and since
app.main's create_all may already have added the columns on a server that started first.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e8b4c2f6a9d1'
down_revision: str | None = 'd7a3b9e1c4f6'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

RULE_COLUMNS = (('amount', sa.Numeric(14, 2)), ('day_of_month', sa.Integer()))


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'amount_only' not in [c['name'] for c in inspector.get_columns('bank_connections')]:
        op.add_column('bank_connections', sa.Column('amount_only', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE bank_connections SET amount_only = 1 WHERE source_prefix = 'tr'")
    columns = [c['name'] for c in inspector.get_columns('bank_counterparty_rules')]
    for name, type_ in RULE_COLUMNS:
        if name not in columns:
            op.add_column('bank_counterparty_rules', sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    op.execute("DELETE FROM bank_counterparty_rules WHERE iban IS NULL AND text_contains IS NULL")
    columns = [c['name'] for c in inspector.get_columns('bank_counterparty_rules')]
    with op.batch_alter_table('bank_counterparty_rules') as batch_op:
        for name, _ in RULE_COLUMNS:
            if name in columns:
                batch_op.drop_column(name)
    if 'amount_only' in [c['name'] for c in inspector.get_columns('bank_connections')]:
        with op.batch_alter_table('bank_connections') as batch_op:
            batch_op.drop_column('amount_only')
