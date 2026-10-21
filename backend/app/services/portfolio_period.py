"""How a gainr portfolio did over one period: its value at both ends, the money that moved in and
out, and per holding the price change and what it contributed (docs/adr/0045). Pure, no
database: prices and FX rates come in as lookups, so this is the arithmetic only.

Values are end-of-day: a day's transactions count towards that day's value, the same rule as the
performance chart (performance_service). The period runs from the close of `start` to the close
of `end`, so a transaction on `start` is already in the start value and one on `end` is in the
period.

A holding's contribution is what it earned in euros over the period: its value at the end, minus
its value at the start, minus what was spent buying it, plus what selling it brought in, plus the
dividends it paid. Those contributions, plus interest, minus broker fees, add up exactly to the
portfolio's change (end value - start value - net deposits), which is what the tests hold it to.
A contribution in percentage points is that euro amount as a share of the start value, so the
points add up to the period's simple return on the money that was there at the start.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models.transaction import Transaction, TransactionType

TT = TransactionType
ZERO = Decimal(0)
HUNDRED = Decimal(100)

# (asset_id, day) -> the close in the asset's own currency on or before that day, or None.
PriceLookup = Callable[[int, date], Decimal | None]
# (asset_id, day) -> the rate from the asset's currency into euros on or before that day.
FxLookup = Callable[[int, date], Decimal]


def pct(part: Decimal, whole: Decimal) -> Decimal | None:
    return part / whole * HUNDRED if whole > ZERO else None


@dataclass(frozen=True)
class HoldingPeriod:
    asset_id: int
    quantity_start: Decimal
    quantity_end: Decimal
    price_start: Decimal | None  # own currency
    price_end: Decimal | None
    value_start_eur: Decimal
    value_end_eur: Decimal
    bought_eur: Decimal
    sold_eur: Decimal
    dividends_eur: Decimal
    # No close on or before `end`: the end value rests on the last transaction price instead.
    price_end_stale: bool = False

    @property
    def contribution_eur(self) -> Decimal:
        return self.value_end_eur - self.value_start_eur - self.bought_eur + self.sold_eur + self.dividends_eur

    @property
    def price_change_pct(self) -> Decimal | None:
        """The price move in the asset's own currency, so it matches what the market quotes."""
        if self.price_start is None or self.price_end is None or self.price_start <= ZERO:
            return None
        return (self.price_end / self.price_start - 1) * HUNDRED


@dataclass(frozen=True)
class PortfolioPeriod:
    start: date
    end: date
    value_start_eur: Decimal
    value_end_eur: Decimal
    deposits_eur: Decimal
    withdrawals_eur: Decimal
    interest_eur: Decimal
    fees_eur: Decimal
    buys: int
    sells: int
    holdings: list[HoldingPeriod]

    @property
    def change_eur(self) -> Decimal:
        """What the portfolio earned: the value change minus the money paid in, plus what was
        taken out."""
        return self.value_end_eur - self.value_start_eur - self.deposits_eur + self.withdrawals_eur

    @property
    def dividends_eur(self) -> Decimal:
        return sum((h.dividends_eur for h in self.holdings), ZERO)

    def contribution_pp(self, holding: HoldingPeriod) -> Decimal | None:
        return pct(holding.contribution_eur, self.value_start_eur)

    def weight_end_pct(self, holding: HoldingPeriod) -> Decimal | None:
        return pct(holding.value_end_eur, self.value_end_eur)


class _Ledger:
    """Quantities, cash and the last transaction price per asset, replayed up to a day."""

    def __init__(self, transactions: list[Transaction]):
        self._transactions = sorted(transactions, key=lambda t: (t.date, t.id or 0))

    def state_at(self, day: date) -> tuple[dict[int, Decimal], Decimal, dict[int, Decimal]]:
        quantities: dict[int, Decimal] = {}
        last_price: dict[int, Decimal] = {}
        cash = ZERO
        for txn in self._transactions:
            if txn.date > day:
                break
            qty = txn.quantity or ZERO
            if txn.type in (TT.BUY, TT.SELL, TT.STAKING) and txn.asset_id is not None:
                sign = -1 if txn.type == TT.SELL else 1
                quantities[txn.asset_id] = quantities.get(txn.asset_id, ZERO) + sign * qty
                if txn.type != TT.STAKING and txn.price is not None:
                    last_price[txn.asset_id] = txn.price
            if txn.type == TT.BUY:
                cash -= txn.total_eur
            elif txn.type in (TT.SELL, TT.DEPOSIT, TT.INTEREST, TT.DIVIDEND):
                cash += txn.total_eur
            elif txn.type in (TT.WITHDRAW, TT.BROKER_FEE):
                cash -= txn.total_eur
        return quantities, cash, last_price


def _value(
    asset_id: int, quantity: Decimal, day: date, last_price: dict[int, Decimal], price_on: PriceLookup, fx_on: FxLookup,
) -> tuple[Decimal | None, Decimal, bool]:
    """(close in own currency, value in euros, stale) for a holding at the end of `day`. Without a
    close, the last transaction price stands in, as on the performance chart, and the price is
    stale; without either, the value is 0."""
    price = price_on(asset_id, day)
    stale = price is None
    if price is None:
        price = last_price.get(asset_id)
    if price is None or quantity == ZERO:
        return price, ZERO, stale and quantity != ZERO
    return price, price * fx_on(asset_id, day) * quantity, stale


def portfolio_period(
    transactions: Iterable[Transaction], start: date, end: date, price_on: PriceLookup, fx_on: FxLookup,
) -> PortfolioPeriod:
    """The portfolio's figures from the close of `start` to the close of `end`. A holding is
    included when it was held at either end or traded in between, so one sold out during the
    period still shows what it contributed."""
    transactions = list(transactions)
    ledger = _Ledger(transactions)
    qty_start, cash_start, last_start = ledger.state_at(start)
    qty_end, cash_end, last_end = ledger.state_at(end)
    in_period = [t for t in transactions if start < t.date <= end]

    def total(kind: TransactionType, asset_id: int | None = None) -> Decimal:
        return sum(
            (t.total_eur for t in in_period if t.type == kind and (asset_id is None or t.asset_id == asset_id)), ZERO,
        )

    asset_ids = sorted(
        {a for a, q in qty_start.items() if q != ZERO}
        | {a for a, q in qty_end.items() if q != ZERO}
        | {t.asset_id for t in in_period if t.asset_id is not None and t.type in (TT.BUY, TT.SELL, TT.STAKING, TT.DIVIDEND)}
    )
    holdings = []
    for asset_id in asset_ids:
        q0, q1 = qty_start.get(asset_id, ZERO), qty_end.get(asset_id, ZERO)
        price_start, value_start, _ = _value(asset_id, q0, start, last_start, price_on, fx_on)
        price_end, value_end, stale = _value(asset_id, q1, end, last_end, price_on, fx_on)
        holdings.append(HoldingPeriod(
            asset_id=asset_id, quantity_start=q0, quantity_end=q1, price_start=price_start, price_end=price_end,
            value_start_eur=value_start, value_end_eur=value_end,
            bought_eur=total(TT.BUY, asset_id), sold_eur=total(TT.SELL, asset_id),
            dividends_eur=total(TT.DIVIDEND, asset_id), price_end_stale=stale,
        ))

    return PortfolioPeriod(
        start=start,
        end=end,
        value_start_eur=cash_start + sum((h.value_start_eur for h in holdings), ZERO),
        value_end_eur=cash_end + sum((h.value_end_eur for h in holdings), ZERO),
        deposits_eur=total(TT.DEPOSIT),
        withdrawals_eur=total(TT.WITHDRAW),
        interest_eur=total(TT.INTEREST),
        fees_eur=total(TT.BROKER_FEE),
        buys=sum(1 for t in in_period if t.type == TT.BUY),
        sells=sum(1 for t in in_period if t.type == TT.SELL),
        holdings=holdings,
    )
