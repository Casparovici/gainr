"""Builds the portfolio's daily value time series by replaying the transaction ledger against
cached historical prices, and slices it into the ranges the Home page chart offers
(1D / 1M / YTD / 1Y / Max).

Returns are time-weighted: each day's return is measured net of that day's deposits and
withdrawals, then chained. Paying money in raises the portfolio's value but is not a return,
and a time-weighted series is the one that can be compared like-for-like against a benchmark
index. `change_eur` stays a plain money figure (end - start - net flows).
"""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType
from app.repositories import asset_repo, transaction_repo
from app.services.money_weighted_return import money_weighted_return
from app.services.price_service import price_service

ZERO = Decimal(0)
VALID_RANGES = ("1D", "1M", "YTD", "1Y", "Max")


@dataclass
class SeriesPoint:
    date: date
    value_eur: Decimal
    # Time-weighted return index (starts at 100 on the inception date). Daily returns are
    # computed net of that day's external deposits/withdrawals and chained, so this measures
    # investment performance only — which is what can honestly be held up against an index.
    # `value_eur` alone can't: it rises when money is paid in, which isn't a return.
    return_index: Decimal = Decimal(100)


@dataclass
class _HeldToday:
    """One holding as the series valued it on its last day, at the daily close and its FX
    rate -- what the live overlay re-prices without replaying the ledger. The asset by id, not
    the row: the cache outlives the request whose session loaded it, and each request reads the
    asset (and its latest quote) through its own session."""

    asset_id: int
    quantity: Decimal
    price_native: Decimal
    fx_rate: Decimal


@dataclass
class _Series:
    points: list[SeriesPoint]
    held_today: list[_HeldToday]
    flow_today: Decimal  # deposits less withdrawals on the last day


class _AsOfSeries:
    def __init__(self):
        self.dates: list[date] = []
        self.values: list[Decimal] = []

    def add(self, d: date, v: Decimal) -> None:
        self.dates.append(d)
        self.values.append(v)

    def finalize(self) -> None:
        paired = sorted(zip(self.dates, self.values))
        self.dates = [p[0] for p in paired]
        self.values = [p[1] for p in paired]

    def as_of(self, day: date) -> Decimal | None:
        idx = bisect_right(self.dates, day) - 1
        if idx < 0:
            return None
        return self.values[idx]


class PerformanceService:
    def __init__(self):
        # Process-lifetime memoization of a pure function of the ledger (transactions +
        # cached prices), not a persisted alternate source of truth — a restart recomputes
        # from scratch, and any transaction write invalidates it. Keyed by portfolio since each
        # one's series is computed from a disjoint slice of the ledger. See docs/adr/0001 and
        # docs/adr/0019.
        self._cache: dict[int, tuple[date, _Series]] = {}

    def invalidate_cache(self, portfolio_id: int | None = None) -> None:
        """Clears one portfolio's cached series, or every portfolio's when none is given (a
        mutation whose portfolio isn't known at the call site, or a broad invalidation)."""
        if portfolio_id is None:
            self._cache.clear()
        else:
            self._cache.pop(portfolio_id, None)

    def get_full_series(self, db: Session, portfolio_id: int) -> list[SeriesPoint]:
        """The daily series on closes only -- every day, today included, valued at the latest
        close. What a report about finished days wants; the Home chart wants `get_live_series`."""
        return self._series(db, portfolio_id).points

    def get_live_series(self, db: Session, portfolio_id: int) -> list[SeriesPoint]:
        """The daily series with today's point re-priced at the hourly live quotes (ADR 0047),
        so the chart, the 1D change and the YTD figure agree with the live total value. Earlier
        days stay on closes. Recomputed per request from the cached series: a few multiplications,
        and never stale by more than the quotes themselves."""
        series = self._series(db, portfolio_id)
        if not series.points or not series.held_today:
            return series.points

        assets_by_id = asset_repo.get_assets_by_ids(db, [held.asset_id for held in series.held_today])
        delta = ZERO
        live_fx: dict[str, Decimal] = {}
        for held in series.held_today:
            asset = assets_by_id.get(held.asset_id)
            if asset is None:
                continue
            live = price_service.get_live_quote(db, asset)
            price_native = live.price if live is not None else held.price_native
            currency = asset.native_currency
            if currency not in live_fx:
                live_fx[currency] = held.fx_rate if currency == "EUR" else price_service.get_fx_rate(db, currency)
            delta += price_native * live_fx[currency] * held.quantity - held.price_native * held.fx_rate * held.quantity
        if delta == ZERO:
            return series.points

        last = series.points[-1]
        value = last.value_eur + delta
        return_index = last.return_index
        if len(series.points) >= 2:
            prev = series.points[-2]
            return_index = prev.return_index
            if prev.value_eur > ZERO:
                daily_return = (value - series.flow_today) / prev.value_eur
                if daily_return > ZERO:
                    return_index *= daily_return
        return [*series.points[:-1], SeriesPoint(date=last.date, value_eur=value, return_index=return_index)]

    def _series(self, db: Session, portfolio_id: int) -> _Series:
        today = date.today()
        cached = self._cache.get(portfolio_id)
        if cached is not None and cached[0] == today:
            return cached[1]
        series = self._compute_full_series(db, portfolio_id)
        self._cache[portfolio_id] = (today, series)
        return series

    def _compute_full_series(self, db: Session, portfolio_id: int) -> _Series:
        transactions = transaction_repo.list_all_transactions(db, portfolio_id)
        if not transactions:
            return _Series([], [], ZERO)

        transactions = sorted(transactions, key=lambda t: (t.date, t.id))
        inception = transactions[0].date
        today = date.today()

        held_asset_ids = {t.asset_id for t in transactions if t.asset_id is not None}
        assets_by_id = {aid: asset_repo.get_asset(db, aid) for aid in held_asset_ids}
        assets_by_id = {k: v for k, v in assets_by_id.items() if v is not None}

        currencies = {a.native_currency for a in assets_by_id.values()}

        for asset in assets_by_id.values():
            first_txn = next((t.date for t in transactions if t.asset_id == asset.id), inception)
            price_service.ensure_history(db, asset, first_txn, today)
        for currency in currencies:
            price_service.ensure_fx_history(db, currency, inception, today)

        price_series: dict[int, _AsOfSeries] = {}
        for asset in assets_by_id.values():
            series = _AsOfSeries()
            for row in price_service_history_rows(db, asset.id, inception, today):
                series.add(row[0], row[1])
            series.finalize()
            price_series[asset.id] = series

        fx_series: dict[str, _AsOfSeries] = {}
        for currency in currencies:
            if currency == "EUR":
                continue
            series = _AsOfSeries()
            fx_asset = asset_repo.get_by_ticker(db, f"FX:{currency}")
            if fx_asset:
                for row in price_service_history_rows(db, fx_asset.id, inception, today):
                    series.add(row[0], row[1])
            series.finalize()
            fx_series[currency] = series

        txns_by_day: dict[date, list[Transaction]] = {}
        for txn in transactions:
            txns_by_day.setdefault(txn.date, []).append(txn)

        quantities: dict[int, Decimal] = {}
        last_price_native: dict[int, Decimal] = {}
        cash_eur = ZERO
        points: list[SeriesPoint] = []

        return_index = Decimal(100)
        prev_value: Decimal | None = None
        held_today: list[_HeldToday] = []
        flow_today = ZERO

        day = inception
        while day <= today:
            external_flow = ZERO  # deposits/withdrawals only — not investment performance
            for txn in txns_by_day.get(day, []):
                if txn.type == TransactionType.DEPOSIT:
                    external_flow += txn.total_eur
                elif txn.type == TransactionType.WITHDRAW:
                    external_flow -= txn.total_eur

            for txn in txns_by_day.get(day, []):
                qty = txn.quantity or ZERO
                if txn.type == TransactionType.BUY:
                    if txn.asset_id is not None:
                        quantities[txn.asset_id] = quantities.get(txn.asset_id, ZERO) + qty
                        if txn.price is not None:
                            last_price_native[txn.asset_id] = txn.price
                    cash_eur -= txn.total_eur
                elif txn.type == TransactionType.SELL:
                    if txn.asset_id is not None:
                        quantities[txn.asset_id] = quantities.get(txn.asset_id, ZERO) - qty
                        if txn.price is not None:
                            last_price_native[txn.asset_id] = txn.price
                    cash_eur += txn.total_eur
                elif txn.type == TransactionType.STAKING:
                    if txn.asset_id is not None:
                        quantities[txn.asset_id] = quantities.get(txn.asset_id, ZERO) + qty
                elif txn.type in (TransactionType.DEPOSIT, TransactionType.INTEREST, TransactionType.DIVIDEND):
                    cash_eur += txn.total_eur
                elif txn.type in (TransactionType.WITHDRAW, TransactionType.BROKER_FEE):
                    cash_eur -= txn.total_eur

            holdings_value = ZERO
            for asset_id, qty in quantities.items():
                if qty == ZERO:
                    continue
                asset = assets_by_id.get(asset_id)
                if asset is None:
                    continue
                price_native = price_series[asset_id].as_of(day)
                if price_native is None:
                    price_native = last_price_native.get(asset_id)
                if price_native is None:
                    continue
                fx_rate = Decimal(1) if asset.native_currency == "EUR" else (
                    fx_series.get(asset.native_currency).as_of(day) if asset.native_currency in fx_series else None
                )
                if fx_rate is None:
                    fx_rate = Decimal(1)
                holdings_value += price_native * fx_rate * qty
                if day == today:
                    held_today.append(_HeldToday(asset_id, qty, price_native, fx_rate))

            value = cash_eur + holdings_value

            # Chain one day of time-weighted return: strip out the money that moved in or
            # out today, then measure what's left against yesterday's value.
            if prev_value is not None and prev_value > ZERO:
                daily_return = (value - external_flow) / prev_value
                if daily_return > ZERO:
                    return_index *= daily_return
            prev_value = value

            points.append(SeriesPoint(date=day, value_eur=value, return_index=return_index))
            flow_today = external_flow
            day += timedelta(days=1)

        return _Series(points, held_today, flow_today)

    def get_range(self, db: Session, portfolio_id: int, range_key: str) -> dict:
        series = self.get_live_series(db, portfolio_id)
        if not series:
            return {
                "range": range_key, "points": [], "start_value_eur": None,
                "end_value_eur": None, "change_eur": None, "change_pct": None,
            }

        today = series[-1].date
        if range_key == "1D":
            slice_points = series[-2:] if len(series) >= 2 else series[-1:]
        elif range_key == "1M":
            slice_points = self._since(series, today - timedelta(days=30))
        elif range_key == "YTD":
            slice_points = self._since(series, date(today.year, 1, 1))
        elif range_key == "1Y":
            slice_points = self._since(series, today - timedelta(days=365))
        else:  # Max
            slice_points = series

        start_value = slice_points[0].value_eur
        end_value = slice_points[-1].value_eur
        start, end = slice_points[0].date, slice_points[-1].date
        flows = self._external_flows(db, portfolio_id, start, end)
        net_flow = sum((amount for _, amount in flows), ZERO)

        change_eur = end_value - start_value - net_flow
        # A day is too short for a rate to mean anything; the chart's 1D change says it all.
        mwr_pct, mwr_yearly_pct = (
            money_weighted_return(start, start_value, flows, end, end_value) if range_key != "1D" else (None, None)
        )

        # Percentages come from the time-weighted index rebased to the start of the range, so
        # the headline figure and the chart's plotted line are the same number, and both are
        # directly comparable to a benchmark's return.
        base_index = slice_points[0].return_index
        change_pct = ((slice_points[-1].return_index / base_index) - 1) * 100 if base_index > ZERO else None

        return {
            "range": range_key,
            "points": [
                {
                    "date": p.date,
                    "value_eur": p.value_eur,
                    "return_pct": ((p.return_index / base_index) - 1) * 100 if base_index > ZERO else None,
                }
                for p in slice_points
            ],
            "start_value_eur": start_value,
            "end_value_eur": end_value,
            "change_eur": change_eur,
            "change_pct": change_pct,
            "mwr_pct": mwr_pct,
            "mwr_yearly_pct": mwr_yearly_pct,
        }

    @staticmethod
    def _since(series: list[SeriesPoint], start: date) -> list[SeriesPoint]:
        filtered = [p for p in series if p.date >= start]
        return filtered if filtered else series[-1:]

    @staticmethod
    def _external_flows(db: Session, portfolio_id: int, start: date, end: date) -> list[tuple[date, Decimal]]:
        """Deposits (positive) and withdrawals (negative) after `start`, up to and including
        `end`: the start value already holds whatever moved on the first day."""
        flows = []
        for txn in transaction_repo.list_all_transactions(db, portfolio_id):
            if start < txn.date <= end:
                if txn.type == TransactionType.DEPOSIT:
                    flows.append((txn.date, txn.total_eur))
                elif txn.type == TransactionType.WITHDRAW:
                    flows.append((txn.date, -txn.total_eur))
        return flows


def price_service_history_rows(db: Session, asset_id: int, start: date, end: date):
    from app.repositories import price_repo

    return [(row.date, Decimal(str(row.close_price))) for row in price_repo.get_history(db, asset_id, start, end)]


performance_service = PerformanceService()
