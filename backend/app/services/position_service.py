"""Computes current and closed positions from the transaction ledger.

Positions are never stored — they're derived here from `transactions` every time, using a
running weighted-average cost basis per asset. This guarantees the numbers shown on the Home
page can never drift out of sync with the ledger on the Transactions page.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType
from app.repositories import transaction_repo
from app.schemas.portfolio import PositionOut
from app.services.price_service import price_service

ZERO = Decimal(0)
CASH_ASSET_ID = 0  # sentinel — real asset ids start at 1
UNASSIGNED_BROKER = "Unassigned"  # bucket for transactions with no broker recorded
# Below this, a "remaining" quantity is treated as fully closed rather than an open position.
# Needs to be well above realistic floating/rounding dust (e.g. a manually-entered sell that
# doesn't cancel a higher-precision buy to the last digit) but well below the smallest
# genuinely-held real quantity in this portfolio (~0.06 for BTC) — see the BIT:EQQQ case for
# why 1e-7 was too tight: a 6dp-rounded manual sell left a 1.2e-7 residual that kept showing
# as an active position with a displayed quantity of "0".
QTY_EPSILON = Decimal("0.00001")


@dataclass
class _AssetLedger:
    quantity: Decimal = ZERO
    cost_basis_eur: Decimal = ZERO
    realized_pnl_eur: Decimal = ZERO
    total_bought_eur: Decimal = ZERO
    total_sold_eur: Decimal = ZERO
    first_buy_date: date | None = None
    last_sell_date: date | None = None
    last_txn_price_native: Decimal | None = None


@dataclass
class Position:
    asset_id: int
    ticker: str
    name: str
    asset_class: str
    native_currency: str
    quantity: Decimal
    cost_basis_eur: Decimal
    last_txn_price_native: Decimal | None
    # Gains already banked on this asset through earlier partial sells. Non-zero on plenty of
    # still-open positions, which is why it's carried here and not only on ClosedPosition.
    realized_pnl_eur: Decimal = ZERO


@dataclass
class Valuation:
    market_value_eur: Decimal | None
    price_native: Decimal | None
    price_date: date | None  # trading day the price belongs to; None when falling back
    price_stale: bool


@dataclass
class ClosedPosition:
    asset_id: int
    ticker: str
    name: str
    asset_class: str
    total_bought_eur: Decimal
    total_sold_eur: Decimal
    realized_pnl_eur: Decimal
    first_buy_date: date | None
    last_sell_date: date | None


def _build_ledgers(transactions: list[Transaction]) -> dict[int, _AssetLedger]:
    ledgers: dict[int, _AssetLedger] = {}
    for txn in sorted(transactions, key=lambda t: (t.date, t.id)):
        if txn.asset_id is None or txn.type == TransactionType.DIVIDEND:
            continue
        ledger = ledgers.setdefault(txn.asset_id, _AssetLedger())
        qty = txn.quantity or ZERO

        if txn.type == TransactionType.BUY:
            ledger.quantity += qty
            ledger.cost_basis_eur += txn.total_eur
            ledger.total_bought_eur += txn.total_eur
            ledger.first_buy_date = ledger.first_buy_date or txn.date
            if txn.price is not None:
                ledger.last_txn_price_native = txn.price
        elif txn.type == TransactionType.SELL:
            avg_cost = ledger.cost_basis_eur / ledger.quantity if ledger.quantity > QTY_EPSILON else ZERO
            sold_qty = min(qty, ledger.quantity) if ledger.quantity > ZERO else ZERO
            cost_removed = avg_cost * sold_qty
            proceeds = txn.total_eur
            ledger.realized_pnl_eur += proceeds - cost_removed
            ledger.cost_basis_eur -= cost_removed
            ledger.quantity -= sold_qty
            ledger.total_sold_eur += proceeds
            ledger.last_sell_date = txn.date
            if txn.price is not None:
                ledger.last_txn_price_native = txn.price
        elif txn.type == TransactionType.STAKING:
            # Reward shares/coins carry zero cost basis.
            ledger.quantity += qty

        if ledger.quantity < QTY_EPSILON:
            ledger.quantity = ZERO
            ledger.cost_basis_eur = ZERO

    return ledgers


class PositionService:
    def get_positions(self, db: Session, portfolio_id: int) -> tuple[list[Position], list[ClosedPosition]]:
        transactions = transaction_repo.list_all_transactions(db, portfolio_id)
        return self.get_positions_from(transactions)

    def get_positions_from(self, transactions: list[Transaction]) -> tuple[list[Position], list[ClosedPosition]]:
        """Same as `get_positions`, but from an already-fetched ledger — lets a caller that
        also needs the raw transaction list (e.g. for cash/invested totals) fetch it once."""
        ledgers = _build_ledgers(transactions)

        active: list[Position] = []
        closed: list[ClosedPosition] = []

        assets_by_id = {t.asset_id: t.asset for t in transactions if t.asset_id is not None and t.asset}

        for asset_id, ledger in ledgers.items():
            asset = assets_by_id.get(asset_id)
            if asset is None:
                continue
            if ledger.quantity > QTY_EPSILON:
                active.append(
                    Position(
                        asset_id=asset_id,
                        ticker=asset.ticker,
                        name=asset.name,
                        asset_class=asset.asset_class,
                        native_currency=asset.native_currency,
                        quantity=ledger.quantity,
                        cost_basis_eur=ledger.cost_basis_eur,
                        last_txn_price_native=ledger.last_txn_price_native,
                        realized_pnl_eur=ledger.realized_pnl_eur,
                    )
                )
            elif ledger.total_bought_eur > ZERO or ledger.total_sold_eur > ZERO:
                closed.append(
                    ClosedPosition(
                        asset_id=asset_id,
                        ticker=asset.ticker,
                        name=asset.name,
                        asset_class=asset.asset_class,
                        total_bought_eur=ledger.total_bought_eur,
                        total_sold_eur=ledger.total_sold_eur,
                        realized_pnl_eur=ledger.realized_pnl_eur,
                        first_buy_date=ledger.first_buy_date,
                        last_sell_date=ledger.last_sell_date,
                    )
                )

        closed.sort(key=lambda c: c.last_sell_date or date.min, reverse=True)
        return active, closed

    def valuation(self, db: Session, position: Position) -> "Valuation":
        """Current value of `position`, plus the per-unit price it was derived from."""
        return self.valuations(db, [position])[position.asset_id]

    def valuations(self, db: Session, positions: list[Position]) -> dict[int, "Valuation"]:
        """Batched `valuation()` for a whole positions list — one query for every asset row
        instead of one per position, and one FX lookup per distinct currency instead of one
        per position (most positions in this portfolio share a handful of currencies)."""
        from app.repositories import asset_repo

        assets_by_id = asset_repo.get_assets_by_ids(db, [p.asset_id for p in positions])
        fx_rate_by_currency: dict[str, Decimal] = {}
        results: dict[int, Valuation] = {}

        for position in positions:
            asset = assets_by_id.get(position.asset_id)
            if asset is None:
                results[position.asset_id] = Valuation(None, None, None, True)
                continue

            price_native = price_service.get_daily_price(db, asset)
            price_date = price_service.price_as_of(db, asset)
            stale = False
            if price_native is None:
                # No provider data (unmapped/delisted symbol) — fall back to what it last
                # traded at in the ledger so the position still carries a plausible value.
                price_native = position.last_txn_price_native
                price_date = None
                stale = True
            if price_native is None:
                results[position.asset_id] = Valuation(None, None, None, True)
                continue

            if asset.native_currency not in fx_rate_by_currency:
                fx_rate_by_currency[asset.native_currency] = price_service.get_fx_rate(db, asset.native_currency)
            fx_rate = fx_rate_by_currency[asset.native_currency]

            results[position.asset_id] = Valuation(price_native * fx_rate * position.quantity, price_native, price_date, stale)

        return results

    def list_position_rows(self, db: Session, portfolio_id: int) -> list["PositionOut"]:
        """Every active holding valued and weighted, plus the synthetic cash row, sorted
        largest-first. Cash participates in the weighting because a target allocation is only
        meaningful against the whole portfolio — so it's built here rather than bolted on by a
        caller, which would leave every other row's weight_pct computed against a total that
        doesn't include it."""
        from app.repositories import asset_repo, portfolio_asset_target_repo, portfolio_settings_repo

        active, _closed = self.get_positions(db, portfolio_id)
        cash_eur = cash_balance_eur(transaction_repo.list_all_transactions(db, portfolio_id))
        dlt_judgments = asset_repo.dlt_judgments_by_asset_id(db)
        target_weights = portfolio_asset_target_repo.targets_by_asset_id(db, portfolio_id)
        valuations = self.valuations(db, active)

        total_value = cash_eur + sum((valuations[p.asset_id].market_value_eur or ZERO) for p in active)

        rows = []
        for position in active:
            valuation = valuations[position.asset_id]
            market_value = valuation.market_value_eur
            avg_cost = position.cost_basis_eur / position.quantity if position.quantity > ZERO else ZERO
            unrealized_pnl = (market_value - position.cost_basis_eur) if market_value is not None else None
            unrealized_pct = (
                (unrealized_pnl / position.cost_basis_eur * 100)
                if unrealized_pnl is not None and position.cost_basis_eur > ZERO
                else None
            )
            weight = (market_value / total_value * 100) if market_value is not None and total_value > ZERO else None
            target_weight = target_weights.get(position.asset_id)
            diff_pct, diff_eur = _target_weight_diff(weight, target_weight, market_value, total_value)

            rows.append(
                PositionOut(
                    asset_id=position.asset_id,
                    ticker=position.ticker,
                    name=position.name,
                    asset_class=position.asset_class,
                    quantity=position.quantity,
                    avg_cost_eur=avg_cost,
                    cost_basis_eur=position.cost_basis_eur,
                    current_price_native=valuation.price_native,
                    price_date=valuation.price_date,
                    native_currency=position.native_currency,
                    market_value_eur=market_value,
                    unrealized_pnl_eur=unrealized_pnl,
                    unrealized_pnl_pct=unrealized_pct,
                    realized_pnl_eur=position.realized_pnl_eur,
                    weight_pct=weight,
                    price_stale=valuation.price_stale,
                    dlt_judgment=dlt_judgments.get(position.asset_id),
                    target_weight_pct=target_weight,
                    target_weight_diff_pct=diff_pct,
                    target_weight_diff_eur=diff_eur,
                )
            )

        cash_weight = (cash_eur / total_value * 100) if total_value > ZERO else None
        cash_target_weight = portfolio_settings_repo.get_cash_target_weight_pct(db, portfolio_id)
        cash_diff_pct, cash_diff_eur = _target_weight_diff(cash_weight, cash_target_weight, cash_eur, total_value)

        rows.append(
            PositionOut(
                asset_id=CASH_ASSET_ID,
                ticker="CASH",
                name="Cash",
                asset_class="cash",
                quantity=cash_eur,
                avg_cost_eur=Decimal(1),
                cost_basis_eur=cash_eur,
                current_price_native=None,
                price_date=None,
                native_currency="EUR",
                market_value_eur=cash_eur,
                unrealized_pnl_eur=ZERO,
                unrealized_pnl_pct=ZERO,
                realized_pnl_eur=ZERO,
                weight_pct=cash_weight,
                price_stale=False,
                # Cash isn't a security DLT would ever rate -- null, not a fake "neutral".
                dlt_judgment=None,
                target_weight_pct=cash_target_weight,
                target_weight_diff_pct=cash_diff_pct,
                target_weight_diff_eur=cash_diff_eur,
            )
        )

        rows.sort(key=lambda p: p.market_value_eur or ZERO, reverse=True)
        return rows


def portfolio_value_eur(db: Session, portfolio_id: int) -> Decimal:
    """Cash plus every holding's market value — the same figure Home shows as the portfolio's
    total. Deliberately leaner than `summary_service.get_summary`, which also computes YTD
    performance: callers here (the gripr balance bridge) want the one number, not the page."""
    transactions = transaction_repo.list_all_transactions(db, portfolio_id)
    active, _closed = position_service.get_positions_from(transactions)
    valuations = position_service.valuations(db, active)
    holdings = sum((valuations[p.asset_id].market_value_eur or ZERO) for p in active)
    return cash_balance_eur(transactions) + holdings


def _target_weight_diff(
    weight: Decimal | None, target: Decimal | None, value: Decimal | None, total_value: Decimal
) -> tuple[Decimal | None, Decimal | None]:
    """(weight_pct - target_weight_pct, and the euro amount that represents) — None on either
    output whenever there's nothing to compare against: no target set, no valued weight, or
    the portfolio itself isn't valued yet."""
    if target is None or weight is None or value is None or total_value <= ZERO:
        return None, None
    diff_pct = weight - target
    diff_eur = value - (target / 100 * total_value)
    return diff_pct, diff_eur


def cash_balance_eur(transactions: list[Transaction]) -> Decimal:
    balance = ZERO
    for txn in transactions:
        if txn.type in (TransactionType.DEPOSIT, TransactionType.INTEREST, TransactionType.DIVIDEND, TransactionType.SELL):
            balance += txn.total_eur
        elif txn.type in (TransactionType.WITHDRAW, TransactionType.BUY, TransactionType.BROKER_FEE):
            balance -= txn.total_eur
        # STAKING is a non-cash quantity increase; TRANSFER moves cash between two brokers'
        # own buckets (see cash_balance_by_broker_eur) but nets to zero on the total -- neither
        # has a total-balance impact.
    return balance


def cash_balance_by_broker_eur(transactions: list[Transaction]) -> dict[str, Decimal]:
    """The same ledger `cash_balance_eur` sums, split by which broker actually holds it. A
    Transfer is the one type that touches two buckets at once -- money leaving `broker` and
    landing in `to_broker` -- which is exactly why it doesn't appear in `cash_balance_eur`'s own
    branches: summed across every broker it's already zero, so it would be double-counted work
    for no change to the total. Brokers with no recorded balance movement at all don't appear in
    the result (a broker only ever bought/sold assets, say) -- callers that want a broker listed
    unconditionally should union this against `transaction_repo.list_distinct_brokers`."""
    balances: dict[str, Decimal] = {}

    def add(broker: str | None, amount: Decimal) -> None:
        key = broker or UNASSIGNED_BROKER
        balances[key] = balances.get(key, ZERO) + amount

    for txn in transactions:
        if txn.type in (TransactionType.DEPOSIT, TransactionType.INTEREST, TransactionType.DIVIDEND, TransactionType.SELL):
            add(txn.broker, txn.total_eur)
        elif txn.type in (TransactionType.WITHDRAW, TransactionType.BUY, TransactionType.BROKER_FEE):
            add(txn.broker, -txn.total_eur)
        elif txn.type == TransactionType.TRANSFER:
            add(txn.broker, -txn.total_eur)
            add(txn.to_broker, txn.total_eur)
    return balances


def net_invested_eur(transactions: list[Transaction]) -> Decimal:
    total = ZERO
    for txn in transactions:
        if txn.type == TransactionType.DEPOSIT:
            total += txn.total_eur
        elif txn.type == TransactionType.WITHDRAW:
            total -= txn.total_eur
    return total


position_service = PositionService()
