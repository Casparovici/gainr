"""Strategy interface for company fundamentals — news and financial statements — so the
backend isn't tied to one external source (yfinance today, a paid data vendor later).

Everything here fails soft: a missing statement or an empty news list is an ordinary answer,
not an error. Plenty of holdings legitimately have neither — an ETF has no income statement,
and a currency pair has no quarterly revenue.
"""

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields, replace
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

from app.services import news_sources
from app.services.fundamentals_metrics import (
    CAPEX, DEPRECIATION, FREE_CASH_FLOW, INVENTORY, NET_INCOME, NET_INTEREST_INCOME, OPERATING_CASH_FLOW,
    OPERATING_EXPENSE, OPERATING_INCOME, REVENUE, FundSnapshot, MetricInputs,
)

# Yahoo returns the ~10-20 most recent stories regardless of age; the card only shows the last
# week, but caching a few more means the window can move without re-fetching.
MAX_NEWS_ITEMS = 20

# yfinance's `Ticker.news` posts to finance.yahoo.com/xhr/ncp, which Yahoo retired in
# October 2026 (a 404 that yfinance turns into an empty list). The per-symbol RSS headline
# feed still answers, for any symbol including European listings and sector indices.
YAHOO_HEADLINE_FEED = "https://feeds.finance.yahoo.com/rss/2.0/headline"
NEWS_TIMEOUT_SECONDS = 10
# The feed 404s without a User-Agent and rate-limits a full browser one; a plain identifying
# one is let through.
NEWS_USER_AGENT = "Mozilla/5.0 (compatible; gainr/1.0; local portfolio dashboard)"
ANNUAL_PERIODS = 3

# Row labels differ by filer and by statement vintage, so each figure is looked up through an
# ordered list of the names Yahoo is known to use.
REVENUE_ROWS = ("Total Revenue", "Operating Revenue")
NET_INCOME_ROWS = ("Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest")
FCF_ROWS = ("Free Cash Flow",)
OPERATING_CASH_ROWS = ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
CAPEX_ROWS = ("Capital Expenditure", "Capital Expenditure Reported")
OPERATING_EXPENSE_ROWS = ("Operating Expense",)

# Yahoo's `industry` for a bank always starts with this ("Banks - Diversified", "Banks -
# Regional"). Cost/income is only shown for those: for any other business, "Operating Expense"
# leaves out the cost of goods sold, so the same division would mean nothing.
BANK_INDUSTRY_PREFIX = "Banks"


@dataclass
class NewsItem:
    title: str
    summary: str
    publisher: str
    url: str
    published_at: datetime


@dataclass
class FinancialPeriod:
    label: str  # "Q2 2026" / "FY2025"
    period_end: date
    revenue: Decimal | None = None
    # Against the comparable prior period: the year before for an annual figure, the same
    # quarter a year earlier for a quarterly one. Never the preceding quarter — most
    # businesses are seasonal, and that comparison invents growth that isn't there.
    revenue_growth_pct: Decimal | None = None
    free_cash_flow: Decimal | None = None
    net_income: Decimal | None = None
    # Within this same period only (net_income / revenue) -- a margin *trend* across the row
    # of periods is what tells you whether the business is scaling or getting squeezed, which
    # a single latest-quarter number can't show on its own.
    net_margin_pct: Decimal | None = None
    # Banks only (see BANK_INDUSTRY_PREFIX): operating expenses / total income for this period,
    # the efficiency figure a bank is judged on -- lower is better. Loan-loss provisions aren't
    # in operating expenses, so this matches how banks report it themselves.
    cost_income_pct: Decimal | None = None


@dataclass
class KeyMetrics:
    """A point-in-time valuation/quality read, the way an analyst opens a position: is it
    cheap or expensive, how good is the business, how leveraged, does the dividend hold up.

    Snapshot only -- unlike FinancialPeriod these don't have a "period_end", they're as of
    whenever the provider last refreshed its quote, and are never blended with the reported
    statement figures above.
    """

    pe_ratio: Decimal | None = None
    forward_pe_ratio: Decimal | None = None
    price_to_fcf: Decimal | None = None
    ev_to_ebitda: Decimal | None = None
    gross_margin_pct: Decimal | None = None
    operating_margin_pct: Decimal | None = None
    net_margin_pct: Decimal | None = None
    return_on_equity_pct: Decimal | None = None
    debt_to_equity: Decimal | None = None
    # totalCash - totalDebt, in `Financials.currency` -- a company can carry debt and still be
    # net-cash, which the debt/equity ratio alone doesn't tell you.
    net_cash: Decimal | None = None
    dividend_yield_pct: Decimal | None = None
    payout_ratio_pct: Decimal | None = None

    def is_empty(self) -> bool:
        return all(getattr(self, f.name) is None for f in fields(self))


@dataclass
class Financials:
    # The currency the filer reports in, which is often not the currency the share trades in
    # and is never converted here — restating three years of statements would need
    # point-in-time FX for every line, and a mislabelled figure is worse than an honest one.
    currency: str | None = None
    quarter: FinancialPeriod | None = None
    annual: list[FinancialPeriod] = field(default_factory=list)
    key_metrics: KeyMetrics | None = None

    def is_empty(self) -> bool:
        return self.quarter is None and not self.annual


@dataclass
class EarningsResult:
    """One reported quarter: what analysts expected per share, and what came in."""

    report_date: date
    eps_estimate: Decimal | None = None
    eps_actual: Decimal | None = None


@dataclass
class CompanyEvents:
    """A company's dated milestones as the provider knows them -- the next earnings release,
    upcoming dividend dates, and recent results. Kept raw (no "is this still upcoming" filter):
    the service filters against today on the way out, since its cache outlives a day boundary.
    """

    # The currency the EPS/revenue figures are in (the filer's reporting currency, not
    # necessarily the listing's) -- never converted, same reasoning as Financials.currency.
    currency: str | None = None
    # Every date the provider offers as the next earnings release; more than one means it's a
    # window, not a confirmed day.
    earnings_dates: list[date] = field(default_factory=list)
    earnings_is_estimate: bool = False
    # "before_open" / "after_close", only where it can be trusted (US listings -- see
    # build_company_events).
    earnings_time: str | None = None
    eps_estimate: Decimal | None = None
    revenue_estimate: Decimal | None = None
    ex_dividend_date: date | None = None
    dividend_payment_date: date | None = None
    # Newest first; past quarters with a reported figure, plus any future-dated rows (a
    # fallback for "next earnings" when the calendar entry itself is stale).
    results: list[EarningsResult] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.earnings_dates or self.ex_dividend_date or self.dividend_payment_date or self.results)


class FundamentalsProvider(ABC):
    @abstractmethod
    def get_news(self, symbol: str) -> list[NewsItem]:
        """Recent stories about `symbol`, newest first. Empty when there are none."""

    @abstractmethod
    def get_financials(self, symbol: str) -> Financials:
        """Reported figures for `symbol`. Empty for anything that doesn't file statements."""

    @abstractmethod
    def get_company_events(self, symbol: str) -> CompanyEvents:
        """Earnings and dividend dates for `symbol`. Empty for funds, crypto and commodities."""

    def get_metric_inputs(self, symbol: str, kind: str, price_symbols: tuple[str, ...] = ()) -> MetricInputs:
        """The raw figures a position's metric checklist is computed from (see
        fundamentals_metrics). `kind` says what to fetch: statements for an "equity", the fund
        breakdown for an "etf", price history for "crypto" and "gold". Empty when the provider
        has nothing -- every metric then simply reads as unavailable."""
        return MetricInputs()

    def get_source_news(self, source: str) -> list[NewsItem]:
        """Recent stories for an extra news source ("sector:<key>", "industry:<key>",
        "ticker:<symbol>" -- see news_sources.py), newest first. Optional: a provider without
        sector/industry feeds just offers none."""
        return []


def _safe_url(raw: str | None) -> str | None:
    """Only ever hand the browser an ordinary web link.

    These URLs come from outside and end up in an href, so a `javascript:` or `data:` scheme
    reaching the page would be a scripting hole in a card that just lists headlines.
    """
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    return raw if parsed.scheme in ("http", "https") and parsed.netloc else None


def parse_headline_feed(xml: bytes) -> list[NewsItem]:
    """Stories from Yahoo's RSS headline feed, newest first. The feed names no publisher, so
    the story's own site stands in for one."""
    items: list[NewsItem] = []
    for entry in ET.fromstring(xml).findall("./channel/item")[:MAX_NEWS_ITEMS]:
        title = (entry.findtext("title") or "").strip()
        url = _safe_url((entry.findtext("link") or "").strip())
        published_at = _rfc822(entry.findtext("pubDate"))
        if not title or url is None or published_at is None:
            continue
        items.append(
            NewsItem(
                title=title,
                summary=(entry.findtext("description") or "").strip(),
                publisher=_publisher_from_url(url),
                url=url,
                published_at=published_at,
            )
        )
    items.sort(key=lambda i: i.published_at, reverse=True)
    return items


def parse_search_news(raw: list) -> list[NewsItem]:
    """Stories from a Yahoo news search (`yf.Search(...).news`), newest first. These carry a
    publisher but no summary."""
    items: list[NewsItem] = []
    for entry in raw[:MAX_NEWS_ITEMS]:
        title = (entry.get("title") or "").strip()
        url = _safe_url(entry.get("link"))
        timestamp = entry.get("providerPublishTime")
        if not title or url is None or not isinstance(timestamp, (int, float)):
            continue
        items.append(
            NewsItem(
                title=title,
                summary="",
                publisher=(entry.get("publisher") or "").strip(),
                url=url,
                published_at=datetime.fromtimestamp(float(timestamp), tz=timezone.utc),
            )
        )
    items.sort(key=lambda i: i.published_at, reverse=True)
    return items


def _rfc822(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _publisher_from_url(url: str) -> str:
    """"247wallst.com" for a 247wallst.com story; Yahoo's own syndicated copies read as Yahoo
    Finance rather than "finance.yahoo.com"."""
    host = (urlparse(url).hostname or "").removeprefix("www.")
    return "Yahoo Finance" if host == "yahoo.com" or host.endswith(".yahoo.com") else host


def _decimal(value) -> Decimal | None:
    """Statement cells arrive as numpy floats, None, or NaN."""
    if value is None or value != value:  # NaN != NaN
        return None
    try:
        return Decimal(str(float(value)))
    except (TypeError, ValueError, InvalidOperation):
        return None


def _quarter_label(period_end: date) -> str:
    return f"Q{(period_end.month - 1) // 3 + 1} {period_end.year}"


def _margin_pct(net_income: Decimal | None, revenue: Decimal | None) -> Decimal | None:
    """Net margin for a single reported period -- distinct from `_pct`, which converts an
    already-fractional yfinance `.info` ratio rather than dividing two statement lines."""
    if net_income is None or revenue is None or revenue == 0:
        return None
    return net_income / revenue * 100


def keep_cost_income_for_banks(periods: list[FinancialPeriod], industry: str | None) -> list[FinancialPeriod]:
    """Drops cost/income from every period unless Yahoo files the company under a bank
    industry -- an unknown industry counts as "not a bank", since a meaningless ratio is worse
    than a missing one."""
    if industry and industry.startswith(BANK_INDUSTRY_PREFIX):
        return periods
    return [replace(p, cost_income_pct=None) for p in periods]


def _pct(fraction) -> Decimal | None:
    """A yfinance `.info` ratio (e.g. `profitMargins`, `payoutRatio`) expressed as 0-1, turned
    into a percentage. Not for `dividendYield`, which this yfinance version already reports
    as a percentage rather than a fraction -- pass that straight to `_decimal` instead."""
    if fraction is None or fraction != fraction:  # NaN != NaN
        return None
    return _decimal(fraction * 100)


def build_key_metrics(info: dict) -> KeyMetrics:
    """Pure mapping from a yfinance `.info` payload to the snapshot an analyst actually reads
    a position by. Kept separate from the network call so it's unit-testable with a plain
    dict -- no live ticker required to cover the derivation logic (unit conversions, the
    price/FCF fallback math) that's actually at risk of being wrong.
    """
    market_cap = info.get("marketCap")
    free_cash_flow = info.get("freeCashflow")
    # A P/FCF multiple is only meaningful when the business is actually generating cash; for
    # a negative or zero FCF the ratio would be a negative or undefined multiple, which reads
    # as "cheap" at a glance when the truth is closer to the opposite.
    price_to_fcf = (
        _decimal(market_cap / free_cash_flow)
        if market_cap is not None and free_cash_flow is not None and free_cash_flow > 0
        else None
    )

    total_cash, total_debt = info.get("totalCash"), info.get("totalDebt")
    net_cash = _decimal(total_cash) - _decimal(total_debt) if total_cash is not None and total_debt is not None else None

    debt_to_equity = info.get("debtToEquity")

    return KeyMetrics(
        pe_ratio=_decimal(info.get("trailingPE")),
        forward_pe_ratio=_decimal(info.get("forwardPE")),
        price_to_fcf=price_to_fcf,
        ev_to_ebitda=_decimal(info.get("enterpriseToEbitda")),
        gross_margin_pct=_pct(info.get("grossMargins")),
        operating_margin_pct=_pct(info.get("operatingMargins")),
        net_margin_pct=_pct(info.get("profitMargins")),
        return_on_equity_pct=_pct(info.get("returnOnEquity")),
        # Yahoo reports this pre-multiplied by 100 (a D/E of 1.5x comes back as 150), unlike
        # every other ratio in `.info` -- divide back down to a plain multiple.
        debt_to_equity=_decimal(debt_to_equity / 100) if debt_to_equity is not None else None,
        net_cash=net_cash,
        # Unlike payoutRatio below, this yfinance version already returns dividendYield as a
        # percentage (5.59 for a ~5.6% yield), not a 0-1 fraction -- verified against several
        # live tickers spanning no/low/high yield rather than assumed from the field name.
        dividend_yield_pct=_decimal(info.get("dividendYield")),
        payout_ratio_pct=_pct(info.get("payoutRatio")),
    )


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and value == value:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).date()
    return None


# Yahoo stamps an earnings row with the release time in New York time, which only means
# something for a US listing -- a European report comes back at an arbitrary-looking hour
# (ABN AMRO's 07:00 CET release shows as 10:00 or 22:00 New York). So the time of day is only
# derived when the listing itself trades in New York.
US_EXCHANGE_TIMEZONE = "America/New_York"
US_MARKET_OPEN = (9, 30)
US_MARKET_CLOSE = (16, 0)


def _us_session_side(release: datetime) -> str | None:
    hm = (release.hour, release.minute)
    if hm >= US_MARKET_CLOSE:
        return "after_close"
    if hm < US_MARKET_OPEN:
        return "before_open"
    return None  # mid-session releases are rare and not worth a label


def build_company_events(calendar: dict | None, info: dict | None, earnings_rows: list[tuple[datetime, float | None, float | None]]) -> CompanyEvents:
    """Pure mapping from yfinance's `.calendar`, `.info` and `get_earnings_dates()` rows
    (release datetime, EPS estimate, reported EPS) to CompanyEvents. Separate from the network
    call so the date/estimate/time-of-day rules are testable with plain values."""
    calendar = calendar or {}
    info = info or {}

    earnings_dates = sorted({d for d in (_as_date(v) for v in calendar.get("Earnings Date") or []) if d})
    # A window (two dates) is an estimate by definition; otherwise trust Yahoo's own flag.
    is_estimate = len(earnings_dates) > 1 or bool(info.get("isEarningsDateEstimate"))

    results: list[EarningsResult] = []
    earnings_time = None
    us_listing = info.get("exchangeTimezoneName") == US_EXCHANGE_TIMEZONE
    for released, estimate, actual in sorted(earnings_rows, key=lambda r: r[0], reverse=True):
        results.append(EarningsResult(report_date=released.date(), eps_estimate=_decimal(estimate), eps_actual=_decimal(actual)))
        if us_listing and earnings_dates and released.date() == earnings_dates[0] and not is_estimate:
            earnings_time = _us_session_side(released)

    return CompanyEvents(
        currency=info.get("financialCurrency"),
        earnings_dates=earnings_dates,
        earnings_is_estimate=is_estimate,
        earnings_time=earnings_time,
        eps_estimate=_decimal(calendar.get("Earnings Average")),
        revenue_estimate=_decimal(calendar.get("Revenue Average")),
        ex_dividend_date=_as_date(calendar.get("Ex-Dividend Date")),
        dividend_payment_date=_as_date(calendar.get("Dividend Date")),
        results=results,
    )


class YFinanceFundamentalsProvider(FundamentalsProvider):
    def get_news(self, symbol: str) -> list[NewsItem]:
        return self._headline_feed(symbol)

    def get_source_news(self, source: str) -> list[NewsItem]:
        import yfinance as yf

        kind, _, key = source.partition(":")
        try:
            if kind == "sector":
                # The sector's index symbol (^YH311 for technology) has its own headline feed.
                return self._headline_feed(yf.Sector(key).ticker.ticker)
            if kind == "industry":
                # An industry index's headline feed is empty, but a news search for the
                # industry's name returns its current stories.
                return parse_search_news(yf.Search(news_sources.label(source), news_count=MAX_NEWS_ITEMS, max_results=0).news)
            if kind == "ticker":
                return self._headline_feed(key)
        except Exception:
            pass  # one unavailable source shouldn't cost the position its other news
        return []

    @staticmethod
    def _headline_feed(symbol: str) -> list[NewsItem]:
        try:
            response = httpx.get(
                YAHOO_HEADLINE_FEED,
                params={"s": symbol, "region": "US", "lang": "en-US"},
                headers={"User-Agent": NEWS_USER_AGENT},
                timeout=NEWS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return parse_headline_feed(response.content)
        except (httpx.HTTPError, ET.ParseError):
            return []

    def get_financials(self, symbol: str) -> Financials:
        import yfinance as yf

        try:
            ticker = yf.Ticker(symbol)
            annual = self._build(ticker.income_stmt, ticker.cashflow, quarterly=False, limit=ANNUAL_PERIODS)
            quarters = self._build(ticker.quarterly_income_stmt, ticker.quarterly_cashflow, quarterly=True, limit=1)
        except Exception:
            return Financials()

        if not annual and not quarters:
            return Financials()

        currency, key_metrics, industry = None, None, None
        try:
            info = ticker.info
            currency = info.get("financialCurrency")
            industry = info.get("industry")
            key_metrics = build_key_metrics(info)
            if key_metrics.is_empty():
                key_metrics = None
        except Exception:
            pass
        annual = keep_cost_income_for_banks(annual, industry)
        quarters = keep_cost_income_for_banks(quarters, industry)

        return Financials(currency=currency, quarter=quarters[0] if quarters else None, annual=annual, key_metrics=key_metrics)

    def _build(self, income, cashflow, *, quarterly: bool, limit: int) -> list[FinancialPeriod]:
        revenue = self._series(income, REVENUE_ROWS)
        net_income = self._series(income, NET_INCOME_ROWS)
        free_cash_flow = self._series(cashflow, FCF_ROWS)
        operating_cash = self._series(cashflow, OPERATING_CASH_ROWS)
        capex = self._series(cashflow, CAPEX_ROWS)
        operating_expense = self._series(income, OPERATING_EXPENSE_ROWS)

        # Newest first, and computed over the *full* series — the comparison period for a
        # growth figure is usually outside the handful of periods actually shown.
        period_ends = sorted(set(revenue) | set(net_income) | set(free_cash_flow), reverse=True)
        # Same quarter last year is 4 quarters back; the year before is 1 annual period back.
        step = 4 if quarterly else 1

        periods: list[FinancialPeriod] = []
        for index, period_end in enumerate(period_ends[:limit]):
            current = revenue.get(period_end)
            previous = revenue.get(period_ends[index + step]) if index + step < len(period_ends) else None

            fcf = free_cash_flow.get(period_end)
            if fcf is None:
                # Capital expenditure is reported negative, so this is a subtraction.
                operating, spend = operating_cash.get(period_end), capex.get(period_end)
                fcf = operating + spend if operating is not None and spend is not None else None

            periods.append(
                FinancialPeriod(
                    label=_quarter_label(period_end) if quarterly else f"FY{period_end.year}",
                    period_end=period_end,
                    revenue=current,
                    revenue_growth_pct=(
                        (current - previous) / abs(previous) * 100
                        if current is not None and previous is not None and previous != 0
                        else None
                    ),
                    free_cash_flow=fcf,
                    net_income=net_income.get(period_end),
                    net_margin_pct=_margin_pct(net_income.get(period_end), current),
                    # The same within-period division as a margin, just over a different line.
                    cost_income_pct=_margin_pct(operating_expense.get(period_end), current),
                )
            )
        return periods

    @staticmethod
    def _series(frame, row_names: tuple[str, ...]) -> dict[date, Decimal]:
        """One statement line as {period end: value}, for the first row label that exists."""
        if frame is None or getattr(frame, "empty", True):
            return {}
        for row in row_names:
            if row not in frame.index:
                continue
            series = {}
            for column, value in frame.loc[row].items():
                amount = _decimal(value)
                if amount is not None:
                    series[column.date() if hasattr(column, "date") else column] = amount
            if series:
                return series
        return {}

    # Enough past quarters for a two-year beat/miss read, plus the upcoming row or two.
    EARNINGS_ROWS = 12

    ANNUAL_ROWS = {
        REVENUE: ("income", REVENUE_ROWS),
        OPERATING_INCOME: ("income", ("Operating Income", "Total Operating Income As Reported")),
        NET_INCOME: ("income", NET_INCOME_ROWS),
        OPERATING_EXPENSE: ("income", OPERATING_EXPENSE_ROWS),
        NET_INTEREST_INCOME: ("income", ("Net Interest Income",)),
        FREE_CASH_FLOW: ("cashflow", FCF_ROWS),
        OPERATING_CASH_FLOW: ("cashflow", OPERATING_CASH_ROWS),
        CAPEX: ("cashflow", CAPEX_ROWS),
        DEPRECIATION: ("cashflow", ("Depreciation And Amortization", "Depreciation Amortization Depletion")),
        INVENTORY: ("balance", ("Inventory",)),
    }

    def get_metric_inputs(self, symbol: str, kind: str, price_symbols: tuple[str, ...] = ()) -> MetricInputs:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        try:
            info = ticker.info or {}
        except Exception:
            info = {}
        inputs = MetricInputs(info=info, currency=info.get("financialCurrency") or info.get("currency"))
        try:
            if kind == "equity":
                frames = {"income": ticker.income_stmt, "cashflow": ticker.cashflow, "balance": ticker.balance_sheet}
                inputs.annual = {
                    row: series
                    for row, (frame, names) in self.ANNUAL_ROWS.items()
                    if (series := self._series(frames[frame], names))
                }
            elif kind == "etf":
                inputs.fund = self._fund_snapshot(ticker)
        except Exception:
            pass  # a partial checklist beats none
        if kind in ("crypto", "gold") or price_symbols:
            for s in (symbol, *price_symbols):
                closes = self._closes(yf, s)
                if closes:
                    inputs.prices[s] = closes
        return inputs

    @staticmethod
    def _closes(yf, symbol: str) -> dict[date, Decimal]:
        try:
            history = yf.Ticker(symbol).history(period="1y")["Close"]
        except Exception:
            return {}
        closes = {}
        for day, close in history.items():
            value = _decimal(close)
            if value is not None:
                closes[day.date() if hasattr(day, "date") else day] = value
        return closes

    @staticmethod
    def _fund_snapshot(ticker) -> FundSnapshot | None:
        try:
            data = ticker.funds_data
        except Exception:
            return None
        snapshot = FundSnapshot()
        try:
            holdings = data.top_holdings
            if holdings is not None and not holdings.empty:
                snapshot.top_holdings = [
                    (str(symbol), weight * 100)
                    for symbol, fraction in holdings["Holding Percent"].items()
                    if (weight := _decimal(fraction)) is not None
                ]
        except Exception:
            pass
        try:
            snapshot.sectors = {
                name: weight * 100 for name, fraction in (data.sector_weightings or {}).items() if (weight := _decimal(fraction)) is not None
            }
        except Exception:
            pass
        try:
            earnings_yield = _decimal(data.equity_holdings.loc["Price/Earnings"].iloc[0])
            snapshot.holdings_earnings_yield = earnings_yield if earnings_yield and earnings_yield > 0 else None
        except Exception:
            pass
        try:
            ratio = _decimal(data.fund_operations.loc["Annual Report Expense Ratio"].iloc[0])
            snapshot.expense_ratio_pct = ratio * 100 if ratio is not None else None
        except Exception:
            pass
        return snapshot

    def get_company_events(self, symbol: str) -> CompanyEvents:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        try:
            calendar = ticker.calendar
        except Exception:
            calendar = {}
        try:
            info = ticker.info
        except Exception:
            info = {}

        rows: list[tuple[datetime, float | None, float | None]] = []
        try:
            frame = ticker.get_earnings_dates(limit=self.EARNINGS_ROWS)
            if frame is not None and not frame.empty:
                for released, row in frame.iterrows():
                    rows.append((released.to_pydatetime(), row.get("EPS Estimate"), row.get("Reported EPS")))
        except Exception:
            pass  # funds, crypto and commodities have none -- not an error

        return build_company_events(calendar if isinstance(calendar, dict) else {}, info, rows)
