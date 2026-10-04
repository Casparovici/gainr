"""Fetches and caches asset prices and FX rates from a free public source (Yahoo Finance
via yfinance).

Prices are daily closes — the most recent one available is typically the previous trading
day's close. Everything is cached in `price_history`, and each asset is refreshed from the
provider **at most once per calendar day** (tracked on `Asset.price_checked_at`), so repeat
page loads within a day never hit the network again. FX rates go through exactly the same
path, stored as price history on a synthetic pseudo-asset (ticker `FX:<CCY>`).
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import BASE_CURRENCY
from app.models.asset import Asset
from app.repositories import asset_repo, price_repo
from app.services.price_provider import PriceProvider, YFinanceProvider

# Trailing window requested on a daily refresh — wide enough to reach back past a weekend
# or holiday run to the last actual trading day.
RECENT_WINDOW_DAYS = 10


class PriceService:
    def __init__(self, provider: PriceProvider | None = None):
        self.provider = provider or YFinanceProvider()

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

        scale = float(asset.price_scale)
        if scale != 1:
            history = {d: p * scale for d, p in history.items()}
        price_repo.upsert_prices(db, asset.id, history)

    @staticmethod
    def _daily_feed_is_behind(history: dict[date, float], today: date) -> bool:
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
        scale = float(asset.price_scale)
        if scale != 1:
            history = {d: p * scale for d, p in history.items()}
        price_repo.upsert_prices(db, asset.id, history)

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
        """Rate to convert 1 unit of `currency` into BASE_CURRENCY."""
        if currency == BASE_CURRENCY:
            return Decimal(1)
        fx_asset = self._fx_asset(db, currency)
        if on_date is None or on_date == date.today():
            rate = self.get_daily_price(db, fx_asset)
        else:
            rate = self.get_price_on(db, fx_asset, on_date)
        return rate if rate is not None else Decimal(1)

    def ensure_fx_history(self, db: Session, currency: str, start: date, end: date) -> None:
        if currency == BASE_CURRENCY:
            return
        fx_asset = self._fx_asset(db, currency)
        self.ensure_history(db, fx_asset, start, end)


price_service = PriceService()
