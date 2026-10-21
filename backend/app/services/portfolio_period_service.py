"""gainr's figures for a period, from the database: the ledger replayed by portfolio_period, the
time-weighted return from the performance series, and the benchmarks over the same days
(docs/adr/0045). Whoever reports on a period (briefr's performance reports) asks here rather than
recomputing any of it."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.repositories import asset_repo, portfolio_asset_target_repo, transaction_repo
from app.services.benchmark_service import BENCHMARKS, benchmark_service
from app.services.performance_service import SeriesPoint, performance_service
from app.services.portfolio_period import PortfolioPeriod, portfolio_period
from app.services.price_service import price_service

ZERO = Decimal(0)
# Closes are looked up "on or before" a day; this far back is enough to cover a long weekend or
# a holiday at either end of a period.
LOOKBACK = timedelta(days=10)


@dataclass(frozen=True)
class PeriodReport:
    """Everything worth saying about one portfolio over one period."""

    period: PortfolioPeriod
    assets: dict[int, Asset]
    targets: dict[int, Decimal]  # asset_id -> target weight %, where one is set
    twr_pct: Decimal | None  # time-weighted: deposits and withdrawals don't count as return
    best_day: tuple[date, Decimal] | None  # (day, time-weighted return %), when the period spans days
    worst_day: tuple[date, Decimal] | None


def _index_on(series: list[SeriesPoint], day: date) -> SeriesPoint | None:
    on_or_before = [p for p in series if p.date <= day]
    return on_or_before[-1] if on_or_before else None


def _daily_returns(series: list[SeriesPoint], start: date, end: date) -> list[tuple[date, Decimal]]:
    window = [p for p in series if start <= p.date <= end]
    return [
        (b.date, (b.return_index / a.return_index - 1) * 100)
        for a, b in zip(window, window[1:])
        if a.return_index > ZERO and b.return_index != a.return_index
    ]


def period_report(db: Session, portfolio_id: int, start: date, end: date) -> PeriodReport:
    transactions = transaction_repo.list_all_transactions(db, portfolio_id)
    asset_ids = {t.asset_id for t in transactions if t.asset_id is not None}
    assets = asset_repo.get_assets_by_ids(db, list(asset_ids))
    for asset in assets.values():
        price_service.ensure_history(db, asset, start - LOOKBACK, end)
    for currency in {a.native_currency for a in assets.values()}:
        price_service.ensure_fx_history(db, currency, start - LOOKBACK, end)

    def price_on(asset_id: int, day: date) -> Decimal | None:
        return price_service.get_price_on(db, assets[asset_id], day) if asset_id in assets else None

    def fx_on(asset_id: int, day: date) -> Decimal:
        currency = assets[asset_id].native_currency if asset_id in assets else "EUR"
        return price_service.get_fx_rate(db, currency, day)

    period = portfolio_period(transactions, start, end, price_on, fx_on)

    series = performance_service.get_full_series(db, portfolio_id)
    first, last = _index_on(series, start), _index_on(series, end)
    twr = (last.return_index / first.return_index - 1) * 100 if first and last and first.return_index > ZERO else None
    daily = _daily_returns(series, start, end) if (end - start).days > 3 else []

    return PeriodReport(
        period=period,
        assets=assets,
        targets=portfolio_asset_target_repo.targets_by_asset_id(db, portfolio_id),
        twr_pct=twr,
        best_day=max(daily, key=lambda d: d[1]) if daily else None,
        worst_day=min(daily, key=lambda d: d[1]) if daily else None,
    )


def benchmark_returns(db: Session, start: date, end: date) -> dict[str, Decimal]:
    """Each benchmark's own-currency return from the close of `start` to the close of `end`; a
    benchmark without closes at both ends is left out."""
    returns = {}
    for key, benchmark in BENCHMARKS.items():
        closes = benchmark_service.get_series(db, key, start - LOOKBACK, end)
        before_start = [c for d, c in closes if d <= start]
        before_end = [c for d, c in closes if d <= end]
        if before_start and before_end and before_start[-1] > ZERO:
            returns[benchmark.label] = (before_end[-1] / before_start[-1] - 1) * 100
    return returns
