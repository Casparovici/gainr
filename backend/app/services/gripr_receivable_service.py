"""Money the reader is owed for expenses they fronted (a restaurant bill paid for the table): what
each expense expects back, what its linked refunds have brought so far, and what's still to come.
See docs/adr/0032-gripr-expected-back.md.

An amount is open while its refunds don't cover what was expected. Writing it off lowers the
expectation to what has come back, so the rest simply counts as the reader's own spending.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.gripr_transaction import GriprTransaction
from app.repositories import gripr_transaction_repo

# A repayment may be a cent or so off what's outstanding (rounding a split three ways).
MATCH_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class Receivable:
    expense: GriprTransaction
    received: Decimal

    @property
    def expected(self) -> Decimal:
        return self.expense.expected_back or Decimal(0)

    @property
    def outstanding(self) -> Decimal:
        return max(self.expected - self.received, Decimal(0))


def outstanding_for(expense: GriprTransaction, received: Decimal) -> Decimal:
    if expense.expected_back is None:
        return Decimal(0)
    return max(expense.expected_back - received, Decimal(0))


def list_open(db: Session) -> list[Receivable]:
    """Every expense with money still to come back, oldest first."""
    expenses = gripr_transaction_repo.list_expecting_back(db)
    received = gripr_transaction_repo.refunded_totals(db, [e.id for e in expenses])
    receivables = [Receivable(e, received.get(e.id, Decimal(0))) for e in expenses]
    return [r for r in receivables if r.outstanding > 0]


def write_off(db: Session, expense: GriprTransaction) -> None:
    """Stops expecting the rest: the expectation drops to what has come back, so what never came
    counts as the reader's own spending from here on."""
    received = gripr_transaction_repo.refunded_totals(db, [expense.id]).get(expense.id, Decimal(0))
    if received > 0:
        expense.expected_back = received
    else:
        expense.expected_back = None
        expense.expected_from = None
    db.flush()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[0-9a-z]+", text.casefold()) if len(t) >= 3}


def match_incoming(db: Session, text: str, amount: Decimal) -> GriprTransaction | None:
    """The one open expense an incoming payment repays, judged by name: a word of who it's
    expected from appears in the payment's counterparty or description, and the payment fits
    what's still outstanding. None when no expense or more than one fits -- the reader picks."""
    words = _tokens(text)
    fits = [
        r.expense for r in list_open(db)
        if r.expense.expected_from
        and _tokens(r.expense.expected_from) & words
        and amount <= r.outstanding + MATCH_TOLERANCE
    ]
    return fits[0] if len(fits) == 1 else None
