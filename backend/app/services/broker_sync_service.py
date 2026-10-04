"""Trading 212's own records into gainr: every fill and dividend on or after the start date becomes a
transaction in the portfolio the sync books into, once per record, plus one deposit a week for the
interest and spending cashback Trading 212 paid on its cash. See docs/adr/0031-trading212-sync.md.

- A record that's already in gainr -- entered by hand before the sync ran -- is matched instead of
  booked twice: a fill against a Buy/Sell of the same asset with the same quantity within
  FILL_MATCH_DAYS, or several fills of one day against the rows the reader entered for that day
  when the totals agree (one hand-entered row for three partial fills); a dividend against a
  Dividend of the same asset for the same amount within DIVIDEND_MATCH_DAYS.
- An instrument is found by its ISIN on the asset. A record for an ISIN no asset has is held back
  and listed (`BrokerConnection.unmapped`) until the reader links an asset; the next run books it,
  however long ago it was.
- Fills are booked for the cash they actually moved: Trading 212's net value, fees included. A
  fill paid from the USD wallet is converted at that day's EUR rate.
- Interest and cashback arrive daily in amounts of a few cents, and auto-invest spends them on
  small buys. They're booked per completed week (Monday to Sunday) as one Deposit on the Sunday,
  so the cash those buys use is there without a row per day.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.broker_sync import BrokerConnection
from app.models.transaction import Transaction, TransactionType
from app.repositories import broker_sync_repo, transaction_repo
from app.services.performance_service import performance_service
from app.services.price_service import PriceService, price_service
from app.services.trading212_provider import (
    CashEntry,
    Dividend,
    Fill,
    Trading212AuthError,
    Trading212Error,
    Trading212Provider,
    local_date,
    trading212_provider,
)

BROKER = "Trading212"
PREFIX = "t212"
FILL_MATCH_DAYS = 2
DIVIDEND_MATCH_DAYS = 5
DIVIDEND_TOLERANCE = Decimal("0.02")
# Each run re-reads this far back from the last one, so a record Trading 212 lists late is still
# picked up. Already-handled records are skipped by reference.
REFETCH_OVERLAP_DAYS = 7
# The cash-activity rows that make up the weekly deposit.
WEEKLY_ACTIONS = {"interest on cash": "interest", "spending cashback": "cashback"}
PLACES = Decimal("0.00000001")

TT = TransactionType


@dataclass
class BrokerSyncResult:
    booked: int = 0
    matched: int = 0
    deposits: int = 0
    unmapped: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def is_configured(t212: Trading212Provider | None = None) -> bool:
    return (t212 or trading212_provider).configured


def get_connection(db: Session) -> BrokerConnection | None:
    return broker_sync_repo.get_connection(db, BROKER)


def unmapped_instruments(connection: BrokerConnection) -> list[dict]:
    try:
        stored = json.loads(connection.unmapped or "[]")
    except json.JSONDecodeError:
        return []
    return stored if isinstance(stored, list) else []


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _q(value: Decimal) -> Decimal:
    return value.quantize(PLACES)


def iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def _week_bounds(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


# -- the run -------------------------------------------------------------------------------------


@dataclass
class _Run:
    db: Session
    connection: BrokerConnection
    portfolio_id: int
    prices: PriceService
    assets: dict[str, list[Asset]]
    result: BrokerSyncResult
    # isin -> what's known about an instrument no asset has, for the reader to link.
    unmapped: dict[str, dict] = field(default_factory=dict)

    def asset_for(self, instrument, day: date) -> Asset | None:
        candidates = self.assets.get(instrument.isin, [])
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            names = ", ".join(sorted(a.ticker for a in candidates))
            self.result.problems.append(f"{instrument.isin} is on more than one asset ({names}); left for you to sort out")
        entry = self.unmapped.setdefault(
            instrument.isin,
            {"isin": instrument.isin, "ticker": instrument.ticker, "name": instrument.name,
             "currency": instrument.currency, "records": 0, "first_date": day.isoformat()},
        )
        entry["records"] += 1
        entry["first_date"] = min(entry["first_date"], day.isoformat())
        return None


def sync(
    db: Session,
    t212: Trading212Provider | None = None,
    prices: PriceService | None = None,
    as_of: date | None = None,
) -> BrokerSyncResult:
    """Books Trading 212's fills, dividends and weekly interest/cashback since the last run into
    the portfolio the sync is set to. Nothing happens while it's off or not yet pointed at a
    portfolio; a Trading 212 that can't be read is recorded on the connection and retried."""
    t212 = t212 or trading212_provider
    prices = prices or price_service
    as_of = as_of or date.today()
    result = BrokerSyncResult()
    connection = get_connection(db)
    if connection is None or not connection.enabled or connection.since is None or connection.portfolio_id is None:
        return result
    if not t212.configured:
        result.problems.append("Trading 212 isn't configured on this server")
        return result

    date_from = connection.since
    if connection.last_synced_at is not None:
        date_from = max(connection.since, connection.last_synced_at.date() - timedelta(days=REFETCH_OVERLAP_DAYS))
    # Records held back for an instrument nobody had linked yet are read again until they're booked.
    for held in unmapped_instruments(connection):
        try:
            date_from = min(date_from, max(connection.since, date.fromisoformat(held.get("first_date", ""))))
        except (TypeError, ValueError):
            continue
    if date_from > as_of:
        return result

    try:
        fills = t212.fills_since(date_from)
        dividends = t212.dividends_since(date_from)
        weeks = _pending_weeks(db, connection.since, as_of)
        cash = t212.cash_activity(min(start for start, _ in weeks.values())) if weeks else []
    except Trading212AuthError:
        message = "Trading 212 refused the API key. Check it's still valid and allowed from this server's IP address."
        broker_sync_repo.update_connection(db, connection, last_error=message)
        result.problems.append(message)
        return result
    except Trading212Error as exc:
        broker_sync_repo.update_connection(db, connection, last_error="Couldn't reach Trading 212; retrying next run.")
        result.problems.append(str(exc)[:200])
        return result

    isins = {f.instrument.isin for f in fills} | {d.instrument.isin for d in dividends}
    run = _Run(
        db=db, connection=connection, portfolio_id=connection.portfolio_id, prices=prices,
        assets=broker_sync_repo.assets_by_isin(db, isins), result=result,
    )
    _sync_fills(run, [f for f in fills if local_date(f.filled_at) <= as_of])
    _sync_dividends(run, [d for d in dividends if local_date(d.paid_at) <= as_of])
    _sync_weeks(run, weeks, cash)

    result.unmapped = sorted(run.unmapped.values(), key=lambda u: u["first_date"])
    result.problems = list(dict.fromkeys(result.problems))
    broker_sync_repo.update_connection(
        db, connection, last_synced_at=_utcnow(), last_error=None,
        unmapped=json.dumps(result.unmapped) if result.unmapped else None,
    )
    if result.booked or result.deposits:
        performance_service.invalidate_cache(connection.portfolio_id)
    return result


# -- fills ---------------------------------------------------------------------------------------


def _sync_fills(run: _Run, fills: list[Fill]) -> None:
    handled = broker_sync_repo.handled_references(run.db, [f"{PREFIX}:fill:{f.fill_id}" for f in fills])
    groups: dict[tuple[int, str, date], list[Fill]] = defaultdict(list)
    for fill in sorted(fills, key=lambda f: (f.filled_at, f.fill_id)):
        if f"{PREFIX}:fill:{fill.fill_id}" in handled:
            continue
        day = local_date(fill.filled_at)
        asset = run.asset_for(fill.instrument, day)
        if asset is None:
            continue
        if fill.instrument.currency and asset.native_currency.upper() != fill.instrument.currency:
            run.result.problems.append(
                f"{asset.ticker}: Trading 212 prices it in {fill.instrument.currency}, gainr in {asset.native_currency}; not booked"
            )
            continue
        groups[(asset.id, fill.side, day)].append(fill)

    for (asset_id, side, day), group in sorted(groups.items(), key=lambda g: (g[0][2], g[0][0], g[0][1])):
        type_ = TT.BUY if side == "BUY" else TT.SELL
        leftover: list[Fill] = []
        for fill in group:
            rows = broker_sync_repo.find_unclaimed(run.db, run.portfolio_id, BROKER, type_, asset_id, day, FILL_MATCH_DAYS, PREFIX)
            same = next((r for r in rows if broker_sync_repo.quantity_close(r.quantity, fill.quantity)), None)
            if same is not None:
                broker_sync_repo.record(run.db, f"{PREFIX}:fill:{fill.fill_id}", "matched", same.id)
                run.result.matched += 1
            else:
                leftover.append(fill)
        if not leftover:
            continue
        # Several fills of one day the reader entered as fewer rows (one Buy of 45.67 for fills of
        # 27 + 11.28 + 7.39): matched together when the day's totals agree.
        rows = broker_sync_repo.find_unclaimed(run.db, run.portfolio_id, BROKER, type_, asset_id, day, 0, PREFIX)
        if rows and broker_sync_repo.quantity_close(sum((abs(r.quantity or 0) for r in rows), Decimal(0)), sum((f.quantity for f in leftover), Decimal(0))):
            for i, fill in enumerate(leftover):
                broker_sync_repo.record(run.db, f"{PREFIX}:fill:{fill.fill_id}", "matched", rows[min(i, len(rows) - 1)].id)
                run.result.matched += 1
            continue
        for fill in leftover:
            booked = _book_fill(run, asset_id, type_, day, fill)
            if booked is not None:
                broker_sync_repo.record(run.db, f"{PREFIX}:fill:{fill.fill_id}", "booked", booked.id)
                run.result.booked += 1


def _book_fill(run: _Run, asset_id: int, type_: TransactionType, day: date, fill: Fill) -> Transaction | None:
    instrument_ccy = fill.instrument.currency or "EUR"
    if fill.wallet_currency in ("", "EUR"):
        to_eur = Decimal(1)
        fx_rate = fill.fx_rate if instrument_ccy != "EUR" else None
    elif fill.wallet_currency == instrument_ccy:
        # Paid from the USD wallet: Trading 212 converted nothing, so the day's rate stands in.
        run.prices.ensure_fx_history(run.db, fill.wallet_currency, day - timedelta(days=7), day)
        to_eur = run.prices.get_fx_rate(run.db, fill.wallet_currency, day)
        fx_rate = _q(1 / to_eur) if to_eur else None
    else:
        run.result.problems.append(f"{fill.instrument.ticker}: paid in {fill.wallet_currency}, which gainr can't convert; not booked")
        return None
    total = _q(fill.net_value * to_eur)
    costs = _q(fill.fees * to_eur)
    value = total - costs if type_ == TT.BUY else total + costs
    note = "Trading 212 · auto-invest" if fill.auto_invest else "Trading 212"
    return transaction_repo.create_transaction(
        run.db,
        portfolio_id=run.portfolio_id, asset_id=asset_id, date=day, type=type_,
        quantity=_q(fill.quantity), price=_q(fill.price), local_value=_q(fill.quantity * fill.price),
        fx_rate=fx_rate, value_eur=value, costs=costs, total_eur=total,
        broker=BROKER, notes=note, source_ref=f"{PREFIX}:fill:{fill.fill_id}",
    )


# -- dividends -----------------------------------------------------------------------------------


def _sync_dividends(run: _Run, dividends: list[Dividend]) -> None:
    references = [f"{PREFIX}:dividend:{d.reference}" for d in dividends]
    handled = broker_sync_repo.handled_references(run.db, references)
    for dividend in sorted(dividends, key=lambda d: (d.paid_at, d.reference)):
        reference = f"{PREFIX}:dividend:{dividend.reference}"
        if reference in handled:
            continue
        day = local_date(dividend.paid_at)
        asset = run.asset_for(dividend.instrument, day)
        if asset is None:
            continue
        if dividend.amount_eur <= 0:
            broker_sync_repo.record(run.db, reference, "skipped")
            continue
        rows = broker_sync_repo.find_unclaimed(run.db, run.portfolio_id, BROKER, TT.DIVIDEND, asset.id, day, DIVIDEND_MATCH_DAYS, PREFIX)
        same = next((r for r in rows if abs(r.total_eur - dividend.amount_eur) <= DIVIDEND_TOLERANCE), None)
        if same is not None:
            broker_sync_repo.record(run.db, reference, "matched", same.id)
            run.result.matched += 1
            continue
        amount = _q(dividend.amount_eur)
        booked = transaction_repo.create_transaction(
            run.db,
            portfolio_id=run.portfolio_id, asset_id=asset.id, date=day, type=TT.DIVIDEND,
            value_eur=amount, costs=Decimal(0), total_eur=amount,
            broker=BROKER, notes="Trading 212", source_ref=reference,
        )
        broker_sync_repo.record(run.db, reference, "booked", booked.id)
        run.result.booked += 1


# -- weekly interest and cashback ----------------------------------------------------------------


def _pending_weeks(db: Session, since: date, as_of: date) -> dict[str, tuple[date, date]]:
    """Every completed week (Monday to Sunday, the Sunday before `as_of`) from the one `since` falls
    in, not yet booked -- by ISO week, with the days it covers (the first one starts at `since`)."""
    weeks: dict[str, tuple[date, date]] = {}
    monday, sunday = _week_bounds(since)
    while sunday < as_of:
        weeks[iso_week(monday)] = (max(monday, since), sunday)
        monday, sunday = monday + timedelta(days=7), sunday + timedelta(days=7)
    handled = broker_sync_repo.handled_references(db, [f"{PREFIX}:week:{w}" for w in weeks])
    return {w: bounds for w, bounds in weeks.items() if f"{PREFIX}:week:{w}" not in handled}


def _sync_weeks(run: _Run, weeks: dict[str, tuple[date, date]], cash: list[CashEntry]) -> None:
    totals: dict[str, dict[str, Decimal]] = {w: {"interest": Decimal(0), "cashback": Decimal(0)} for w in weeks}
    for entry in cash:
        kind = WEEKLY_ACTIONS.get(entry.action.casefold())
        day = entry.local_date
        week = iso_week(day)
        if kind is None or week not in weeks or not (weeks[week][0] <= day <= weeks[week][1]):
            continue
        amount = entry.amount
        if entry.currency not in ("", "EUR"):
            # Interest on the USD wallet: converted at that day's rate.
            run.prices.ensure_fx_history(run.db, entry.currency, day - timedelta(days=7), day)
            amount = amount * run.prices.get_fx_rate(run.db, entry.currency, day)
        totals[week][kind] += amount

    for week, (start, sunday) in sorted(weeks.items()):
        interest, cashback = (totals[week][k].quantize(Decimal("0.01")) for k in ("interest", "cashback"))
        total = interest + cashback
        reference = f"{PREFIX}:week:{week}"
        if total <= 0:
            broker_sync_repo.record(run.db, reference, "empty")
            continue
        number = week.split("-W")[1].lstrip("0")
        booked = transaction_repo.create_transaction(
            run.db,
            portfolio_id=run.portfolio_id, date=sunday, type=TT.DEPOSIT,
            value_eur=total, costs=Decimal(0), total_eur=total, broker=BROKER,
            notes=f"Trading 212: interest €{interest} + cashback €{cashback}, week {number} ({start:%d %b}–{sunday:%d %b})",
            source_ref=reference,
        )
        broker_sync_repo.record(run.db, reference, "booked", booked.id)
        run.result.deposits += 1
