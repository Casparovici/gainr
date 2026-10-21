"""Strategy interface for market data providers, so the backend isn't locked to one
external data source (yfinance today; a paid provider or IBKR feed later)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

def to_price(value) -> Decimal:
    """A provider's number as a Decimal, by way of its shortest decimal form: Yahoo hands back
    binary floats (42.64 arrives as 42.6400000000000005684...), and str() recovers the 42.64 it
    published instead of carrying the binary noise into every multiplication after it."""
    return Decimal(str(value))


# What a symbol search may return as something to hold -- not news, futures or options.
_HOLDABLE = {"EQUITY", "ETF", "MUTUALFUND", "CRYPTOCURRENCY"}


@dataclass(frozen=True)
class SymbolMatch:
    """One listing a provider knows for a search: the symbol to fetch prices with, and enough
    to tell listings of the same fund apart (and a same-named American fund from the European one
    the reader holds)."""

    symbol: str
    name: str
    exchange: str
    quote_type: str


@dataclass(frozen=True)
class Quote:
    """The provider's latest traded price for a symbol and the moment of that trade -- an
    intraday price while the session is open, the session's close once it has ended."""

    price: Decimal
    quoted_at: datetime  # timezone-aware


class PriceProvider(ABC):
    @abstractmethod
    def get_history(self, symbol: str, start: date, end: date) -> dict[date, Decimal]:
        """Daily close prices for `symbol` between start and end (inclusive), keyed by date.

        Daily closes are the only price granularity this app uses — the most recent one is
        normally the previous trading day's close."""

    @abstractmethod
    def get_currency(self, symbol: str) -> str | None:
        """ISO-ish currency code the provider quotes `symbol` in (e.g. "USD", "EUR", or
        "GBp" for London-listed stocks priced in pence rather than pounds)."""

    def search(self, query: str) -> list[SymbolMatch]:
        """Listings matching a ticker, ISIN or name -- how a new asset's price symbol is picked.
        A provider without search returns nothing, and the reader types the symbol themselves."""
        return []

    def get_quote(self, symbol: str) -> Quote | None:
        """The latest traded price, for the hourly live quote (docs/adr/0047). Never stored as
        a daily close. A provider without quotes returns None, and values stay on closes."""
        return None

    def get_intraday(self, symbol: str) -> list[tuple[datetime, Decimal]]:
        """The last trading session's prices through the day, oldest first, as timezone-aware
        (moment, price) pairs -- the 1D price chart (docs/adr/0053). A provider without intraday
        prices returns nothing, and the chart falls back to the daily closes. Never stored."""
        return []

    def get_last_settled_close(self, symbol: str) -> tuple[date, Decimal] | None:
        """The close of the most recent *finished* trading session, with the day it belongs to.

        Only for repairing a daily series that's missing a session it should have (see
        YFinanceProvider below). A provider whose daily feed is trustworthy can leave this
        alone — the default says "nothing to add", and callers fall back to `get_history`.
        """
        return None


class YFinanceProvider(PriceProvider):
    def search(self, query: str) -> list[SymbolMatch]:
        import yfinance as yf

        try:
            quotes = yf.Search(query, max_results=10, news_count=0).quotes
        except Exception:
            return []
        matches = []
        for quote in quotes:
            if not isinstance(quote, dict) or quote.get("quoteType") not in _HOLDABLE:
                continue
            symbol = str(quote.get("symbol") or "").strip()[:32]
            if not symbol:
                continue
            matches.append(
                SymbolMatch(
                    symbol=symbol,
                    name=str(quote.get("longname") or quote.get("shortname") or "").strip()[:120],
                    exchange=str(quote.get("exchDisp") or quote.get("exchange") or "").strip()[:60],
                    quote_type=str(quote.get("typeDisp") or quote.get("quoteType")).strip()[:20],
                )
            )
        return matches

    def get_currency(self, symbol: str) -> str | None:
        import yfinance as yf

        try:
            return yf.Ticker(symbol).fast_info.get("currency")
        except Exception:
            return None

    def get_history(self, symbol: str, start: date, end: date) -> dict[date, Decimal]:
        import yfinance as yf

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat())
            if hist.empty:
                return {}
            # Yahoo occasionally returns a NaN close for a listing on a given day (thin
            # trading, or a not-yet-settled session). Dropping those keeps NaN out of the
            # price cache — a cached NaN would poison every valuation that forward-fills
            # from it. Callers forward-fill over the gap instead.
            return {
                ts.date(): to_price(close)
                for ts, close in hist["Close"].items()
                if close is not None and close == close  # NaN != NaN
            }
        except Exception:
            return {}

    def get_intraday(self, symbol: str) -> list[tuple[datetime, Decimal]]:
        """Yahoo's 15-minute bars for the most recent trading session (the last five days are
        asked for, so a weekend or a holiday still finds the last session that traded)."""
        import yfinance as yf

        try:
            hist = yf.Ticker(symbol).history(period="5d", interval="15m")
            if hist.empty:
                return []
            rows = [
                (ts.to_pydatetime(), to_price(close))
                for ts, close in hist["Close"].items()
                if close is not None and close == close  # NaN != NaN
            ]
            if not rows:
                return []
            # The exchange's own calendar day, which is what the timestamps carry.
            last_day = rows[-1][0].date()
            return [(ts, price) for ts, price in rows if ts.date() == last_day]
        except Exception:
            return []

    def get_quote(self, symbol: str) -> Quote | None:
        """Yahoo's quote snapshot: the last trade and its timestamp, read off the chart metadata
        (one small request per symbol). Most European listings are about 15 minutes delayed."""
        import yfinance as yf

        try:
            meta = yf.Ticker(symbol).history_metadata
            price = meta.get("regularMarketPrice")
            stamped_at = meta.get("regularMarketTime")
            if price is None or stamped_at is None:
                return None
            stamped_at = self._exchange_local(stamped_at, meta.get("gmtoffset"))
            if stamped_at is None:
                return None
            return Quote(price=to_price(price), quoted_at=stamped_at)
        except Exception:
            return None

    def get_last_settled_close(self, symbol: str) -> tuple[date, Decimal] | None:
        """Yahoo's quote snapshot, used to repair gaps in its own daily series.

        Yahoo intermittently publishes a *null* close in the daily feed for a session that
        genuinely traded — routine on European listings, where a holding can sit two or three
        days behind while US tickers stay current. The quote snapshot for the same symbol is
        intact, and it carries the timestamp of the last trade it represents, so the day it
        belongs to is read off the data rather than assumed.

        Returns None while that timestamp is in today's session: an in-progress price is not a
        close, and this app stores daily closes only.
        """
        quote = self.get_quote(symbol)
        if quote is None:
            return None
        stamped_at = quote.quoted_at
        # "Today" on the exchange's own clock, not ours — a New York session is still open
        # well after midnight in Amsterdam.
        if stamped_at.date() >= datetime.now(stamped_at.tzinfo).date():
            return None
        return stamped_at.date(), quote.price

    @staticmethod
    def _exchange_local(stamped_at, gmt_offset_seconds) -> datetime | None:
        """Normalises the quote timestamp to an exchange-local aware datetime.

        yfinance hands this back as a tz-aware pandas Timestamp, but older versions (and the
        raw payload) use a bare epoch, where the exchange's UTC offset is the only thing that
        says which calendar day the trade fell on.
        """
        if isinstance(stamped_at, datetime):
            return stamped_at if stamped_at.tzinfo is not None else None
        if isinstance(stamped_at, (int, float)) and gmt_offset_seconds is not None:
            tz = timezone(timedelta(seconds=int(gmt_offset_seconds)))
            return datetime.fromtimestamp(float(stamped_at), tz=tz)
        return None
