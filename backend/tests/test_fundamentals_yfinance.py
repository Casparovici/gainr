"""YFinanceFundamentalsProvider against a stand-in for yfinance: statements, metric inputs, fund
data, company events and the news sources. No network."""

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pandas as pd
import pytest
import yfinance

from app.services import fundamentals_provider
from app.services.fundamentals_metrics import CAPEX, FREE_CASH_FLOW, INVENTORY, REVENUE
from app.services.fundamentals_provider import YFinanceFundamentalsProvider

Y = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31")]
Q = [pd.Timestamp("2026-06-30"), pd.Timestamp("2026-03-31"), pd.Timestamp("2025-12-31"), pd.Timestamp("2025-09-30"), pd.Timestamp("2025-06-30")]


def statement(rows: dict[str, list], columns) -> pd.DataFrame:
    return pd.DataFrame(rows, index=columns).T


class FakeTicker(SimpleNamespace):
    """Attributes as yfinance names them; one set to an Exception raises when read."""

    def __getattribute__(self, name):
        value = super().__getattribute__(name)
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture()
def tickers(monkeypatch):
    registry: dict[str, FakeTicker] = {}
    monkeypatch.setattr(yfinance, "Ticker", lambda symbol: registry[symbol])
    return registry


def company(**overrides) -> FakeTicker:
    fields = dict(
        income_stmt=statement({"Total Revenue": [120, 100, 80], "Net Income": [12, 10, 8], "Operating Expense": [60, 55, 50]}, Y),
        cashflow=statement({"Operating Cash Flow": [30, 25, 20], "Capital Expenditure": [-10, -8, -6]}, Y),
        quarterly_income_stmt=statement({"Total Revenue": [33, 31, 30, 29, 30], "Net Income": [3, 3, 3, 3, 3]}, Q),
        quarterly_cashflow=statement({"Free Cash Flow": [5, 4, 4, 4, 4]}, Q),
        balance_sheet=statement({"Inventory": [7, 6, 5]}, Y),
        info={"financialCurrency": "EUR", "industry": "Semiconductors", "trailingPE": 30},
    )
    fields.update(overrides)
    return FakeTicker(**fields)


# -- financials -------------------------------------------------------------------------------


def test_annual_figures_carry_growth_and_a_derived_free_cash_flow(tickers):
    tickers["ASML.AS"] = company()

    financials = YFinanceFundamentalsProvider().get_financials("ASML.AS")

    assert financials.currency == "EUR"
    assert [p.label for p in financials.annual] == ["FY2025", "FY2024", "FY2023"]
    fy25 = financials.annual[0]
    assert fy25.revenue == Decimal(120)
    assert fy25.revenue_growth_pct == Decimal(20)
    assert fy25.free_cash_flow == Decimal(20)  # operating cash 30 plus capex -10
    assert fy25.net_margin_pct == Decimal(10)
    assert fy25.cost_income_pct is None  # only kept for banks
    assert financials.annual[-1].revenue_growth_pct is None  # nothing earlier to compare with
    assert financials.key_metrics is not None


def test_the_latest_quarter_compares_with_the_same_quarter_a_year_earlier(tickers):
    tickers["X"] = company()
    quarter = YFinanceFundamentalsProvider().get_financials("X").quarter
    assert quarter.period_end == date(2026, 6, 30)
    assert quarter.revenue_growth_pct == Decimal(10)  # 33 vs 30 four quarters back
    assert quarter.free_cash_flow == Decimal(5)


def test_no_statements_or_a_failure_is_empty_financials(tickers):
    empty = pd.DataFrame()
    tickers["FUND"] = company(income_stmt=empty, cashflow=empty, quarterly_income_stmt=empty, quarterly_cashflow=empty)
    assert YFinanceFundamentalsProvider().get_financials("FUND").is_empty()
    tickers["DOWN"] = company(income_stmt=RuntimeError("rate limited"))
    assert YFinanceFundamentalsProvider().get_financials("DOWN").is_empty()


def test_financials_survive_info_failing(tickers):
    tickers["X"] = company(info=RuntimeError("scrape broke"))
    financials = YFinanceFundamentalsProvider().get_financials("X")
    assert financials.annual
    assert financials.currency is None
    assert financials.key_metrics is None


# -- metric inputs ----------------------------------------------------------------------------


def test_an_equitys_inputs_are_its_annual_lines(tickers):
    tickers["X"] = company()
    inputs = YFinanceFundamentalsProvider().get_metric_inputs("X", "equity")
    assert inputs.currency == "EUR"
    assert inputs.annual[REVENUE][date(2025, 12, 31)] == Decimal(120)
    assert inputs.annual[CAPEX][date(2023, 12, 31)] == Decimal(-6)
    assert inputs.annual[INVENTORY][date(2024, 12, 31)] == Decimal(6)
    assert FREE_CASH_FLOW not in inputs.annual  # no such line reported


def test_a_funds_inputs_are_its_holdings_sectors_and_costs(tickers):
    funds = SimpleNamespace(
        top_holdings=pd.DataFrame({"Holding Percent": [0.05, 0.04]}, index=["AAPL", "MSFT"]),
        sector_weightings={"technology": 0.25, "energy": None},
        equity_holdings=pd.DataFrame({"IWDA": [0.045]}, index=["Price/Earnings"]),
        fund_operations=pd.DataFrame({"IWDA": [0.002]}, index=["Annual Report Expense Ratio"]),
    )
    tickers["IWDA.AS"] = company(info={"currency": "USD"}, funds_data=funds)

    inputs = YFinanceFundamentalsProvider().get_metric_inputs("IWDA.AS", "etf")

    assert inputs.currency == "USD"
    assert inputs.fund.top_holdings == [("AAPL", Decimal("5.00")), ("MSFT", Decimal("4.00"))]
    assert inputs.fund.sectors == {"technology": Decimal("25.00")}
    assert inputs.fund.holdings_earnings_yield == Decimal("0.045")
    assert inputs.fund.expense_ratio_pct == Decimal("0.200")


def test_a_fund_without_fund_data_has_no_snapshot(tickers):
    tickers["F"] = company(funds_data=RuntimeError("not a fund"))
    assert YFinanceFundamentalsProvider().get_metric_inputs("F", "etf").fund is None


def test_crypto_and_extra_symbols_bring_a_year_of_closes(tickers):
    days = pd.to_datetime(["2026-10-01", "2026-10-02"])
    history = pd.DataFrame({"Close": [60000.5, float("nan")]}, index=days)
    tickers["BTC-EUR"] = company(info={}, history=lambda period: history)
    tickers["GC=F"] = company(history=lambda period: (_ for _ in ()).throw(RuntimeError("no data")))

    inputs = YFinanceFundamentalsProvider().get_metric_inputs("BTC-EUR", "crypto", ("GC=F",))

    assert inputs.prices == {"BTC-EUR": {date(2026, 10, 1): Decimal("60000.5")}}


def test_a_failing_info_still_gives_inputs(tickers):
    tickers["X"] = company(info=RuntimeError("scrape broke"))
    inputs = YFinanceFundamentalsProvider().get_metric_inputs("X", "equity")
    assert inputs.info == {}
    assert inputs.annual[REVENUE]


# -- company events ---------------------------------------------------------------------------


def test_company_events_combine_the_calendar_and_past_earnings(tickers):
    released = pd.Timestamp(datetime(2026, 7, 16, 7, 0, tzinfo=timezone.utc))
    tickers["ASML.AS"] = company(
        calendar={"Earnings Date": [date(2026, 10, 15)], "Earnings Average": 5.1, "Ex-Dividend Date": date(2026, 10, 28)},
        get_earnings_dates=lambda limit: pd.DataFrame({"EPS Estimate": [4.0], "Reported EPS": [4.3]}, index=[released]),
    )

    events = YFinanceFundamentalsProvider().get_company_events("ASML.AS")

    assert events.ex_dividend_date == date(2026, 10, 28)
    assert events.eps_estimate == Decimal("5.1")
    assert len(events.results) == 1


def test_a_symbol_without_a_calendar_or_earnings_has_no_events(tickers):
    def no_dates(limit):
        raise KeyError("no earnings")

    tickers["BTC-EUR"] = company(calendar=RuntimeError("none"), info=RuntimeError("none"), get_earnings_dates=no_dates)
    assert YFinanceFundamentalsProvider().get_company_events("BTC-EUR").is_empty()


# -- news -------------------------------------------------------------------------------------

FEED = b"""<?xml version="1.0"?><rss><channel>
<item><title>ASML beats</title><link>https://www.reuters.com/a</link><pubDate>Wed, 15 Oct 2026 07:00:00 GMT</pubDate></item>
</channel></rss>"""


@pytest.fixture()
def feed(monkeypatch):
    asked = []

    def fake_get(url, params, headers, timeout):
        asked.append(params["s"])
        if params["s"] == "DOWN":
            raise httpx.ConnectError("down")
        return httpx.Response(200, content=FEED, request=httpx.Request("GET", url))

    monkeypatch.setattr(fundamentals_provider.httpx, "get", fake_get)
    return asked


def test_a_positions_news_is_its_headline_feed(feed):
    news = YFinanceFundamentalsProvider().get_news("ASML")
    assert [n.title for n in news] == ["ASML beats"]
    assert feed == ["ASML"]
    assert YFinanceFundamentalsProvider().get_news("DOWN") == []


def test_a_sector_source_reads_its_index_feed_and_a_ticker_source_its_own(feed, monkeypatch):
    monkeypatch.setattr(yfinance, "Sector", lambda key: SimpleNamespace(ticker=SimpleNamespace(ticker="^YH311")))
    assert YFinanceFundamentalsProvider().get_source_news("sector:technology")[0].title == "ASML beats"
    assert YFinanceFundamentalsProvider().get_source_news("ticker:NVDA")
    assert feed == ["^YH311", "NVDA"]


def test_an_industry_source_is_a_news_search(monkeypatch):
    story = {"title": "Chips rally", "publisher": "Example", "link": "https://example.com/chips",
             "providerPublishTime": 1_790_960_000}
    monkeypatch.setattr(yfinance, "Search", lambda query, news_count, max_results: SimpleNamespace(news=[story]))
    news = YFinanceFundamentalsProvider().get_source_news("industry:semiconductors")
    assert [n.title for n in news] == ["Chips rally"]


def test_an_unknown_or_failing_source_has_no_news(monkeypatch):
    def boom(key):
        raise RuntimeError("unknown sector")

    monkeypatch.setattr(yfinance, "Sector", boom)
    assert YFinanceFundamentalsProvider().get_source_news("sector:nope") == []
    assert YFinanceFundamentalsProvider().get_source_news("bogus:thing") == []
