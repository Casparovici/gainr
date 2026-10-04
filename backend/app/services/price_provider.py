"""Strategy interface for market data providers, so the backend isn't locked to one
external data source (yfinance today; a paid provider or IBKR feed later)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

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


class PriceProvider(ABC):
    @abstractmethod
    def get_history(self, symbol: str, start: date, end: date) -> dict[date, float]:
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

    def get_last_settled_close(self, symbol: str) -> tuple[date, float] | None:
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

    def get_history(self, symbol: str, start: date, end: date) -> dict[date, float]:
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
                ts.date(): float(close)
                for ts, close in hist["Close"].items()
                if close is not None and close == close  # NaN != NaN
            }
        except Exception:
            return {}

    def get_last_settled_close(self, symbol: str) -> tuple[date, float] | None:
        """Yahoo's quote snapshot, used to repair gaps in its own daily series.

        Yahoo intermittently publishes a *null* close in the daily feed for a session that
        genuinely traded — routine on European listings, where a holding can sit two or three
        days behind while US tickers stay current. The quote snapshot for the same symbol is
        intact, and it carries the timestamp of the last trade it represents, so the day it
        belongs to is read off the data rather than assumed.

        Returns None while that timestamp is in today's session: an in-progress price is not a
        close, and this app stores daily closes only.
        """
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
            # "Today" on the exchange's own clock, not ours — a New York session is still open
            # well after midnight in Amsterdam.
            if stamped_at.date() >= datetime.now(stamped_at.tzinfo).date():
                return None

            return stamped_at.date(), float(price)
        except Exception:
            return None

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
