"""The price chart of one position (docs/adr/0053): an asset's own price over 1D, 1W, 1M, YTD or 3Y,
in the currency it trades in -- not the portfolio's value, and not a return.

The longer ranges are daily closes from `price_history`, backfilled from the provider when the
range reaches further back than what is cached (as the performance series does), with the live
quote (ADR 0047) as today's point while it is current. 1D is the last session through the day: the
provider's 15-minute bars, fetched when asked for and kept in memory for a few minutes. They are
never stored, since an intraday price is not a close. When the provider has none, 1D falls back to
the last week's closes and says so.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.repositories import price_repo
from app.services.price_service import PriceService, price_service

RANGES = ("1D", "1W", "1M", "YTD", "3Y")
# Days back for the rolling ranges; YTD starts on 1 January.
_DAYS_BACK = {"1W": 7, "1M": 30, "3Y": 3 * 365}
# What 1D shows when there are no intraday bars: the last week of closes.
FALLBACK_DAYS = 7
# How long an asset's intraday bars are kept. A person flicking between ranges and positions
# shouldn't ask Yahoo for the same session each time, and 15-minute bars barely move in ten.
INTRADAY_TTL = timedelta(minutes=10)

ZERO = Decimal(0)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class ChartPoint:
    # An ISO date for a daily close, an ISO moment (UTC) for an intraday bar.
    time: str
    price: Decimal


@dataclass(frozen=True)
class PriceChart:
    range: str
    currency: str
    interval: str  # "intraday" or "daily"
    points: list[ChartPoint]
    # What the change is measured from: yesterday's close for 1D, the first close of the range
    # otherwise. None without a price to compare with.
    start_price: Decimal | None
    end_price: Decimal | None
    change: Decimal | None
    change_pct: Decimal | None
    # 1D asked for, intraday bars unavailable: the points are the last week's closes.
    is_fallback: bool = False
    # When the last point was traded (UTC), for a live or intraday price.
    as_of: datetime | None = None


def _range_start(range_key: str, today: date) -> date:
    return date(today.year, 1, 1) if range_key == "YTD" else today - timedelta(days=_DAYS_BACK[range_key])


def _iso_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PriceChartService:
    def __init__(self, prices: PriceService | None = None, clock: Callable[[], datetime] = _utcnow):
        self.prices = prices or price_service
        # Naive UTC, like every DateTime column here; injectable so tests never read the real clock.
        self.clock = clock
        self._intraday: dict[str, tuple[datetime, list[tuple[datetime, Decimal]]]] = {}

    def build(self, db: Session, asset: Asset, range_key: str, today: date) -> PriceChart:
        if range_key not in RANGES:
            raise ValueError(f"Unknown range {range_key}")
        if range_key == "1D":
            chart = self._one_day(db, asset, today)
            if chart is not None:
                return chart
            return self._daily(db, asset, "1D", today - timedelta(days=FALLBACK_DAYS), today, is_fallback=True)
        return self._daily(db, asset, range_key, _range_start(range_key, today), today)

    # -- daily closes -----------------------------------------------------------------------

    def _daily(self, db: Session, asset: Asset, range_key: str, start: date, today: date, is_fallback: bool = False) -> PriceChart:
        self.prices.ensure_history(db, asset, start, today)
        rows = price_repo.get_history(db, asset.id, start, today)
        points = [ChartPoint(time=r.date.isoformat(), price=Decimal(str(r.close_price))) for r in rows]
        as_of = None
        live = self.prices.get_live_quote(db, asset)
        # Today's point is the live quote while there is a current one and no close for its day yet.
        if live is not None and live.quoted_at is not None and (not rows or live.price_date > rows[-1].date):
            points.append(ChartPoint(time=live.price_date.isoformat(), price=live.price))
            as_of = live.quoted_at.astimezone(timezone.utc).replace(tzinfo=None)
        return self._chart(asset, range_key, "daily", points, start_price=points[0].price if points else None, is_fallback=is_fallback, as_of=as_of)

    # -- the last session, through the day --------------------------------------------------

    def _bars(self, asset: Asset) -> list[tuple[datetime, Decimal]]:
        now = self.clock()
        cached = self._intraday.get(asset.yahoo_symbol)
        if cached is not None and now - cached[0] < INTRADAY_TTL:
            return cached[1]
        bars = self.prices.provider.get_intraday(asset.yahoo_symbol)
        # A failed fetch is remembered too, for the same time: a provider that is down isn't
        # asked again on every click.
        self._intraday[asset.yahoo_symbol] = (now, bars)
        return bars

    def _one_day(self, db: Session, asset: Asset, today: date) -> PriceChart | None:
        if not asset.yahoo_symbol:
            return None
        bars = self._bars(asset)
        if not bars:
            return None
        scale = Decimal(asset.price_scale)
        points = [ChartPoint(time=_iso_utc(ts), price=price * scale) for ts, price in bars]
        # The change is the day's move: from the close before the session to its last price.
        session_day = bars[-1][0].date()
        before = price_repo.get_price_on_or_before(db, asset.id, session_day - timedelta(days=1))
        start_price = Decimal(str(before.close_price)) if before is not None else points[0].price
        return self._chart(
            asset, "1D", "intraday", points, start_price=start_price, as_of=bars[-1][0].astimezone(timezone.utc).replace(tzinfo=None)
        )

    # -- the figures ------------------------------------------------------------------------

    @staticmethod
    def _chart(
        asset: Asset,
        range_key: str,
        interval: str,
        points: list[ChartPoint],
        start_price: Decimal | None,
        is_fallback: bool = False,
        as_of: datetime | None = None,
    ) -> PriceChart:
        end_price = points[-1].price if points else None
        change = end_price - start_price if end_price is not None and start_price is not None else None
        change_pct = change / start_price * 100 if change is not None and start_price else None
        return PriceChart(
            range=range_key,
            currency=asset.native_currency,
            interval=interval,
            points=points,
            start_price=start_price,
            end_price=end_price,
            change=change,
            change_pct=change_pct,
            is_fallback=is_fallback,
            as_of=as_of,
        )


price_chart_service = PriceChartService()
