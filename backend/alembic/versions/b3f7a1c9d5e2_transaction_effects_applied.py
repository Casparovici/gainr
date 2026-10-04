"""gripr: record whether a transaction's side effects were applied

Revision ID: b3f7a1c9d5e2
Revises: a9d5e3b7c2f8
Create Date: 2026-10-02 23:00:00.000000

pefi_transactions.effects_applied: a recurring occurrence pre-booked ahead of its date gets its
loan-balance / portfolio-mirror effects only once it's due, but editing or deleting it reversed
them regardless -- deleting the pre-booked 25 Oct Studieschuld occurrence on 26 Sep 2026 added
€154.99 back onto the loan that was never taken off for it, undoing the real 25 Sep repayment.
Now edits and deletes reverse only what was applied.

Backfill: every existing row counts as applied (as the old code assumed), except a recurring
occurrence its rule hasn't reached yet (next_due_date on or before the occurrence) -- exactly the
pre-booked rows whose effects are still deferred. See docs/adr/0020.
"""
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op

revision: str = 'b3f7a1c9d5e2'
down_revision: str | None = 'a9d5e3b7c2f8'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'effects_applied' not in [c['name'] for c in inspector.get_columns('pefi_transactions')]:
        op.add_column('pefi_transactions', sa.Column('effects_applied', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE pefi_transactions SET effects_applied = 1")
    next_due = dict(bind.execute(sa.text("SELECT id, next_due_date FROM pefi_recurring_transactions")).all())
    pending = []
    for txn_id, source_ref in bind.execute(sa.text("SELECT id, source_ref FROM pefi_transactions WHERE source_ref LIKE 'pefi_recurring:%'")).all():
        try:
            _, rule_id, occurrence = source_ref.split(":")
            rule_next = next_due.get(int(rule_id))
            if rule_next is not None and date.fromisoformat(str(rule_next)[:10]) <= date.fromisoformat(occurrence):
                pending.append(txn_id)
        except ValueError:
            continue
    for txn_id in pending:
        bind.execute(sa.text("UPDATE pefi_transactions SET effects_applied = 0 WHERE id = :id"), {"id": txn_id})


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'effects_applied' in [c['name'] for c in inspector.get_columns('pefi_transactions')]:
        with op.batch_alter_table('pefi_transactions') as batch_op:
            batch_op.drop_column('effects_applied')
