"""Fetches and caches asset prices and FX rates from a free public source (Yahoo Finance
via yfinance).

Prices are daily closes — the most recent one available is typically the previous trading
day's close. Everything is cached in `price_history`, and each asset is refreshed from the
provider **at most once per calendar day** (tracked on `Asset.price_checked_at`), so repeat
page loads within a day never hit the network again. FX rates go through exactly the same
path, stored as price history on a synthetic pseudo-asset (ticker `FX:<CCY>`).

On top of the closes sits a live quote per asset (docs/adr/0047): the latest traded price,
fetched by `scripts/refresh_quotes.py` **at most once an hour** and kept on the asset row, never
in `price_history`. Current values prefer it while it's fresh; history and returns don't see it.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import BASE_CURRENCY
from app.models.asset import Asset
from app.repositories import asset_repo, price_repo
from app.services.price_provider import PriceProvider, YFinanceProvider

# Trailing window requested on a daily refresh — wide enough to reach back past a weekend
# or holiday run to the last actual trading day.
RECENT_WINDOW_DAYS = 10

# A live quote is fetched at most once per this interval per asset. The slack lets an hourly
# timer that fires a few seconds early still find the previous run's quote due.
QUOTE_REFRESH_INTERVAL = timedelta(hours=1)
QUOTE_REFRESH_SLACK = timedelta(minutes=1)
# Past this, a quote no longer counts as current (the hourly refresh stopped): values fall back
# to the daily close rather than freeze on an old intraday price. Two runs' worth, so one
# missed run doesn't flicker the dashboard back to yesterday's close.
QUOTE_MAX_AGE = timedelta(hours=2)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class CurrentPrice:
    price: Decimal
    price_date: date  # trading day the price belongs to
    quoted_at: datetime | None  # UTC, aware; set only when the price is a live quote


class PriceService:
    def __init__(self, provider: PriceProvider | None = None, clock: Callable[[], datetime] = _utcnow):
        self.provider = provider or YFinanceProvider()
        # Naive UTC, like every DateTime column here; injectable so tests never read the real clock.
        self.clock = clock

    # -- asset prices -----------------------------------------------------

    def get_daily_price(self, db: Session, asset: Asset) -> Decimal | None:
        """Most recent cached daily close, refreshing from the provider once per day."""
        if asset.yahoo_symbol and asset.price_checked_at != date.today():
            self._refresh_recent(db, asset)
            asset.price_checked_at = date.today()
            db.flush()

        cached = price_repo.get_latest_price(db, asset.id)
        return Decimal(str(cached.close_price)) if cached else None

    def _refresh_recent(self, db: Session, asset: Asset) -> None:
        today = date.today()
        history = self.provider.get_history(asset.yahoo_symbol, today - timedelta(days=RECENT_WINDOW_DAYS), today)

        if self._daily_feed_is_behind(history, today):
            settled = self.provider.get_last_settled_close(asset.yahoo_symbol)
            if settled is not None:
                settled_date, close = settled
                # setdefault, not assignment: a real daily close always outranks the quote
                # snapshot. This only ever fills a day the daily feed left empty.
                history.setdefault(settled_date, close)

        price_repo.upsert_prices(db, asset.id, self._scaled(history, asset))

    @staticmethod
    def _scaled(history: dict[date, Decimal], asset: Asset) -> dict[date, Decimal]:
        """Closes in the asset's own currency unit: Yahoo quotes London listings in pence, which
        `price_scale` (0.01) turns into pounds. Decimal throughout, so 1234.5p is exactly £12.345."""
        scale = Decimal(asset.price_scale)
        if scale == 1:
            return history
        return {d: p * scale for d, p in history.items()}

    @staticmethod
    def _daily_feed_is_behind(history: dict[date, Decimal], today: date) -> bool:
        """Whether the daily feed is missing a session recent enough to matter for valuation.

        Yesterday is the newest close that can normally exist, so anything older than that is
        either a market that was shut (a weekend, a holiday) or — the case worth repairing — a
        session Yahoo published as null. Both look the same from here; asking for the quote
        snapshot costs one request and a closed market simply confirms what we already have.

        Older gaps *inside* the window are left alone: the chart forward-fills across them,
        and only the newest price feeds a position's current value.
        """
        return not history or max(history) < today - timedelta(days=1)

    def price_as_of(self, db: Session, asset: Asset) -> date | None:
        """Trading day the price returned by `get_daily_price` belongs to."""
        cached = price_repo.get_latest_price(db, asset.id)
        return cached.date if cached else None

    def ensure_history(self, db: Session, asset: Asset, start: date, end: date) -> None:
        """Backfills any missing daily closes for `asset` in [start, end] from the provider.

        Markets aren't open every calendar day, so "coverage" is judged by whether cached
        data reaches close to both ends of the range rather than by a full day count.
        """
        if not asset.yahoo_symbol:
            return
        existing = sorted(p.date for p in price_repo.get_history(db, asset.id, start, end))
        covers_start = bool(existing) and (existing[0] - start).days <= 5
        covers_end = bool(existing) and (end - existing[-1]).days <= 5
        if covers_start and covers_end:
            return
        history = self.provider.get_history(asset.yahoo_symbol, start, end)
        price_repo.upsert_prices(db, asset.id, self._scaled(history, asset))

    def sync_currency(self, db: Session, asset: Asset) -> None:
        """(Re)detects `native_currency`/`price_scale` for `asset` from the provider — in
        particular, catches Yahoo quoting London-listed stocks in pence ("GBp") rather than
        pounds, which would otherwise overvalue the position 100x."""
        if not asset.yahoo_symbol:
            return
        currency = self.provider.get_currency(asset.yahoo_symbol)
        if not currency:
            return
        if currency in ("GBp", "GBX"):
            asset.native_currency = "GBP"
            asset.price_scale = Decimal("0.01")
        else:
            asset.native_currency = currency
            asset.price_scale = Decimal(1)

    # -- live quotes ----------------------------------------------------------

    def refresh_quote(self, db: Session, asset: Asset) -> bool:
        """Fetches `asset`'s live quote unless it was fetched within the last hour. Returns
        whether the provider was asked. A failed fetch counts towards the hour too and keeps the
        previous quote, so a provider that's down isn't asked again on every run."""
        if not asset.yahoo_symbol:
            return False
        now = self.clock()
        if asset.quote_checked_at is not None and now - asset.quote_checked_at < QUOTE_REFRESH_INTERVAL - QUOTE_REFRESH_SLACK:
            return False
        asset.quote_checked_at = now
        quote = self.provider.get_quote(asset.yahoo_symbol)
        if quote is not None:
            asset.quote_price = quote.price * Decimal(asset.price_scale)
            asset.quoted_at = quote.quoted_at.astimezone(timezone.utc).replace(tzinfo=None)
        db.flush()
        return True

    def refresh_fx_quote(self, db: Session, currency: str) -> bool:
        if currency == BASE_CURRENCY:
            return False
        return self.refresh_quote(db, self._fx_asset(db, currency))

    def get_live_quote(self, db: Session, asset: Asset) -> CurrentPrice | None:
        """The asset's live quote, when there is a current one that's at least as new as its
        latest daily close; None otherwise, and the close stands."""
        if asset.quote_price is None or asset.quoted_at is None or asset.quote_checked_at is None:
            return None
        if self.clock() - asset.quote_checked_at > QUOTE_MAX_AGE:
            return None
        quoted_at = asset.quoted_at.replace(tzinfo=timezone.utc)
        latest_close = price_repo.get_latest_price(db, asset.id)
        if latest_close is not None and quoted_at.date() < latest_close.date:
            return None
        return CurrentPrice(Decimal(str(asset.quote_price)), quoted_at.date(), quoted_at)

    def get_current_price(self, db: Session, asset: Asset) -> CurrentPrice | None:
        """What `asset` is worth per unit right now: its live quote when there's a current one,
        else its latest daily close."""
        live = self.get_live_quote(db, asset)
        if live is not None:
            return live
        price = self.get_daily_price(db, asset)
        if price is None:
            return None
        return CurrentPrice(price, self.price_as_of(db, asset), None)

    def get_price_on(self, db: Session, asset: Asset, on_date: date) -> Decimal | None:
        row = price_repo.get_price_on_or_before(db, asset.id, on_date)
        return Decimal(str(row.close_price)) if row else None

    # -- FX -----------------------------------------------------------------

    def _fx_asset(self, db: Session, currency: str) -> Asset:
        ticker = f"FX:{currency}"
        symbol = f"{currency}{BASE_CURRENCY}=X"
        return asset_repo.get_or_create_asset(
            db, ticker=ticker, name=f"{currency}/{BASE_CURRENCY}", asset_class="fx",
            native_currency=BASE_CURRENCY, yahoo_symbol=symbol,
        )

    def get_fx_rate(self, db: Session, currency: str, on_date: date | None = None) -> Decimal:
        """Rate to convert 1 unit of `currency` into BASE_CURRENCY. Today's rate is the live
        quote while there's a current one, so it moves with the live prices it converts."""
        if currency == BASE_CURRENCY:
            return Decimal(1)
        fx_asset = self._fx_asset(db, currency)
        if on_date is None or on_date == date.today():
            current = self.get_current_price(db, fx_asset)
            rate = current.price if current is not None else None
        else:
            rate = self.get_price_on(db, fx_asset, on_date)
        return rate if rate is not None else Decimal(1)

    def ensure_fx_history(self, db: Session, currency: str, start: date, end: date) -> None:
        if currency == BASE_CURRENCY:
            return
        fx_asset = self._fx_asset(db, currency)
        self.ensure_history(db, fx_asset, start, end)


price_service = PriceService()
