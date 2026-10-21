"""Dividend income from the ledger: what was received per month, year and holding, and what the
current holdings can be expected to pay over the next 12 months (docs/adr/0041). Pure arithmetic
on transactions, so it's derived on every request like positions are.

The expectation repeats the last 12 months. Each dividend received in that window is turned into
an amount per share held on the day it was paid, multiplied by the shares held now, and placed a
year later. A holding bought since then has no history yet and expects nothing; one sold expects
nothing; one that cut or raised its dividend is only caught after the next payment. Amounts are
the euros the ledger booked (after withholding tax), at the FX rate of the day they were paid.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.models.transaction import Transaction, TransactionType

ZERO = Decimal(0)
WINDOW = timedelta(days=365)
# Months on the chart: the last 12 (this one included) received, the next 12 expected.
MONTHS_BACK = 12
MONTHS_AHEAD = 12


@dataclass
class HoldingIncome:
    asset_id: int
    received_total_eur: Decimal = ZERO
    received_12m_eur: Decimal = ZERO
    payments_12m: int = 0
    expected_12m_eur: Decimal = ZERO
    last_paid_on: date | None = None


@dataclass
class DividendIncome:
    received_by_month: dict[tuple[int, int], Decimal] = field(default_factory=dict)
    expected_by_month: dict[tuple[int, int], Decimal] = field(default_factory=dict)
    holdings: dict[int, HoldingIncome] = field(default_factory=dict)


def _month(d: date) -> tuple[int, int]:
    return d.year, d.month


def _next_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29 February
        return d + timedelta(days=365)


def add_months(month: tuple[int, int], count: int) -> tuple[int, int]:
    index = month[0] * 12 + (month[1] - 1) + count
    return index // 12, index % 12 + 1


def dividend_income(transactions: list[Transaction], today: date) -> DividendIncome:
    """Everything the Income page shows, from one pass over the ledger in date order. On a day
    with both a dividend and a trade, the dividend is counted first: it was earned on the shares
    held before that day (the ex-date comes before the payment)."""
    result = DividendIncome()
    quantities: dict[int, Decimal] = {}
    # (asset, pay date, amount per share) for the dividends in the last 12 months.
    per_share: list[tuple[int, date, Decimal]] = []

    ordered = sorted(transactions, key=lambda t: (t.date, t.type != TransactionType.DIVIDEND, t.id))
    for txn in ordered:
        if txn.asset_id is None or txn.date > today:
            continue
        if txn.type == TransactionType.DIVIDEND:
            holding = result.holdings.setdefault(txn.asset_id, HoldingIncome(txn.asset_id))
            amount = txn.total_eur
            holding.received_total_eur += amount
            holding.last_paid_on = txn.date
            month = _month(txn.date)
            result.received_by_month[month] = result.received_by_month.get(month, ZERO) + amount
            if txn.date > today - WINDOW:
                holding.received_12m_eur += amount
                holding.payments_12m += 1
                held = quantities.get(txn.asset_id, ZERO)
                if held > ZERO:
                    per_share.append((txn.asset_id, txn.date, amount / held))
        elif txn.type in (TransactionType.BUY, TransactionType.STAKING):
            quantities[txn.asset_id] = quantities.get(txn.asset_id, ZERO) + (txn.quantity or ZERO)
        elif txn.type == TransactionType.SELL:
            quantities[txn.asset_id] = max(quantities.get(txn.asset_id, ZERO) - (txn.quantity or ZERO), ZERO)

    for asset_id, paid_on, amount_per_share in per_share:
        held_now = quantities.get(asset_id, ZERO)
        if held_now <= ZERO:
            continue
        expected = amount_per_share * held_now
        result.holdings[asset_id].expected_12m_eur += expected
        month = _month(_next_year(paid_on))
        result.expected_by_month[month] = result.expected_by_month.get(month, ZERO) + expected

    return result


def percent_of(part: Decimal, whole: Decimal | None) -> Decimal | None:
    if whole is None or whole <= ZERO:
        return None
    return part / whole * 100
