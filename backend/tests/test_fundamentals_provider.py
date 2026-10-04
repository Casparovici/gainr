from decimal import Decimal

from datetime import date, datetime, timezone

from app.services.fundamentals_provider import (
    FinancialPeriod,
    YFinanceFundamentalsProvider,
    _margin_pct,
    _pct,
    build_key_metrics,
    keep_cost_income_for_banks,
    parse_headline_feed,
    parse_search_news,
)


def test_key_metrics_maps_a_full_info_payload():
    info = {
        "trailingPE": 38.15,
        "forwardPE": 34.70,
        "marketCap": 4_849_207_869_440,
        "freeCashflow": 107_721_875_456,
        "enterpriseToEbitda": 29.0,
        "grossMargins": 0.4865,
        "operatingMargins": 0.3262,
        "profitMargins": 0.2762,
        "returnOnEquity": 1.4875,
        "debtToEquity": 78.445,
        "totalCash": 62_399_000_576,
        "totalDebt": 84_343_996_416,
        "dividendYield": 0.33,
        "payoutRatio": 0.1204,
    }

    metrics = build_key_metrics(info)

    assert metrics.pe_ratio == Decimal("38.15")
    assert metrics.forward_pe_ratio == Decimal("34.7")
    assert metrics.price_to_fcf == Decimal(str(4_849_207_869_440 / 107_721_875_456))
    assert metrics.ev_to_ebitda == Decimal("29")
    assert metrics.gross_margin_pct == Decimal("48.65")
    assert metrics.operating_margin_pct == Decimal("32.62")
    assert metrics.net_margin_pct == Decimal("27.62")
    assert metrics.return_on_equity_pct == Decimal("148.75")
    # Yahoo's debtToEquity is pre-multiplied by 100; the provider divides it back down.
    assert metrics.debt_to_equity == Decimal("0.78445")
    assert metrics.net_cash == Decimal(62_399_000_576) - Decimal(84_343_996_416)
    # dividendYield is passed straight through -- this yfinance version already reports it as
    # a percentage, unlike payoutRatio which is a 0-1 fraction.
    assert metrics.dividend_yield_pct == Decimal("0.33")
    assert metrics.payout_ratio_pct == Decimal("12.04")
    assert not metrics.is_empty()


def test_key_metrics_from_an_empty_info_payload_is_empty():
    metrics = build_key_metrics({})

    assert metrics.is_empty()
    assert metrics.pe_ratio is None
    assert metrics.net_cash is None


def test_price_to_fcf_is_none_when_free_cash_flow_is_not_positive():
    # A negative or zero FCF makes the multiple meaningless (or actively misleading, reading
    # as "cheap" at a glance) rather than merely large.
    negative = build_key_metrics({"marketCap": 1_000, "freeCashflow": -500})
    zero = build_key_metrics({"marketCap": 1_000, "freeCashflow": 0})

    assert negative.price_to_fcf is None
    assert zero.price_to_fcf is None


def test_net_cash_requires_both_cash_and_debt_to_be_known():
    only_cash = build_key_metrics({"totalCash": 1_000})
    only_debt = build_key_metrics({"totalDebt": 1_000})

    assert only_cash.net_cash is None
    assert only_debt.net_cash is None


def test_margin_pct_divides_within_a_single_period():
    assert _margin_pct(Decimal("25"), Decimal("100")) == Decimal("25")
    assert _margin_pct(Decimal("-10"), Decimal("100")) == Decimal("-10")


def test_margin_pct_is_none_without_both_figures_or_on_zero_revenue():
    assert _margin_pct(None, Decimal("100")) is None
    assert _margin_pct(Decimal("10"), None) is None
    assert _margin_pct(Decimal("10"), Decimal("0")) is None


def test_pct_converts_a_fraction_and_passes_through_nan_and_none_as_missing():
    assert _pct(0.1204) == Decimal("12.04")
    assert _pct(None) is None
    assert _pct(float("nan")) is None


def test_build_computes_cost_income_from_operating_expense_over_total_revenue():
    import pandas as pd

    # ABN AMRO's FY2025/FY2024 lines, in millions.
    columns = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")]
    income = pd.DataFrame(
        {columns[0]: [8732.0, 5482.0, 2252.0], columns[1]: [8896.0, 5373.0, 2403.0]},
        index=["Total Revenue", "Operating Expense", "Net Income"],
    )

    periods = YFinanceFundamentalsProvider()._build(income, pd.DataFrame(), quarterly=False, limit=2)

    assert [p.label for p in periods] == ["FY2025", "FY2024"]
    assert round(periods[0].cost_income_pct, 1) == Decimal("62.8")
    assert round(periods[1].cost_income_pct, 1) == Decimal("60.4")


def test_cost_income_is_kept_only_for_banks():
    period = FinancialPeriod(label="FY2025", period_end=date(2025, 12, 31), cost_income_pct=Decimal("62.8"))

    assert keep_cost_income_for_banks([period], "Banks - Diversified")[0].cost_income_pct == Decimal("62.8")
    assert keep_cost_income_for_banks([period], "Banks - Regional")[0].cost_income_pct == Decimal("62.8")
    # For anyone else "Operating Expense" excludes cost of goods sold -- the ratio means nothing.
    assert keep_cost_income_for_banks([period], "Internet Retail")[0].cost_income_pct is None
    assert keep_cost_income_for_banks([period], None)[0].cost_income_pct is None
    # Everything else about the period is untouched.
    assert keep_cost_income_for_banks([period], None)[0].label == "FY2025"


HEADLINE_FEED = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<rss version="2.0"><channel>
  <description>Latest Financial News for RHM.DE</description>
  <item>
    <description>Analysts see further upside.</description>
    <guid isPermaLink="false">a</guid>
    <link>https://finance.yahoo.com/markets/stocks/articles/defence-ideas-140814.html</link>
    <pubDate>Wed, 30 Sep 2026 14:08:14 +0000</pubDate>
    <title>European Defence: top ideas for Q4</title>
  </item>
  <item>
    <description></description>
    <link>https://www.247wallst.com/investing/2026/10/01/rheinmetall/?.tsrc=rss</link>
    <pubDate>Thu, 01 Oct 2026 09:00:00 +0000</pubDate>
    <title>Rheinmetall &amp; the rearmament trade</title>
  </item>
  <item>
    <link>javascript:alert(1)</link>
    <pubDate>Thu, 01 Oct 2026 10:00:00 +0000</pubDate>
    <title>Not a web link</title>
  </item>
  <item>
    <link>https://example.com/undated</link>
    <title>No date</title>
  </item>
</channel></rss>"""


def test_headline_feed_parses_stories_newest_first():
    items = parse_headline_feed(HEADLINE_FEED)

    assert [i.title for i in items] == ["Rheinmetall & the rearmament trade", "European Defence: top ideas for Q4"]
    assert items[0].published_at == datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    assert items[1].summary == "Analysts see further upside."
    assert items[0].summary == ""


def test_headline_feed_names_the_story_s_site_as_its_publisher():
    items = parse_headline_feed(HEADLINE_FEED)

    assert items[0].publisher == "247wallst.com"
    # Yahoo's own syndicated copy reads as Yahoo Finance, not a hostname.
    assert items[1].publisher == "Yahoo Finance"


def test_headline_feed_with_no_stories_is_empty():
    assert parse_headline_feed(b"<rss version='2.0'><channel><description>None</description></channel></rss>") == []


def test_search_news_parses_stories_and_skips_unusable_ones():
    raw = [
        {"title": "Older", "publisher": "Zacks", "link": "https://example.com/a", "providerPublishTime": 1790900000},
        {"title": "Newer", "publisher": "Reuters", "link": "https://example.com/b", "providerPublishTime": 1790960000},
        {"title": "No time", "publisher": "X", "link": "https://example.com/c"},
        {"title": "Bad link", "publisher": "X", "link": "data:text/html,hi", "providerPublishTime": 1790960000},
        {"title": "", "publisher": "X", "link": "https://example.com/d", "providerPublishTime": 1790960000},
    ]

    items = parse_search_news(raw)

    assert [(i.title, i.publisher) for i in items] == [("Newer", "Reuters"), ("Older", "Zacks")]
    assert items[0].published_at == datetime.fromtimestamp(1790960000, tz=timezone.utc)
    assert items[0].summary == ""
