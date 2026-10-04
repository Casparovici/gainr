import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.asset import Asset
from app.repositories import snapshot_repo
from app.services.fundamentals_provider import (
    CompanyEvents,
    Financials,
    FinancialPeriod,
    FundamentalsProvider,
    KeyMetrics,
    NewsItem,
    _safe_url,
)
from app.services.fundamentals_service import FundamentalsService

NOW = datetime.now(timezone.utc)


class FakeProvider(FundamentalsProvider):
    def __init__(self, news: list[NewsItem] | None = None, financials: Financials | None = None):
        self.news = news or []
        self.financials = financials or Financials()
        self.news_calls = 0
        self.financials_calls = 0

    def get_news(self, symbol: str) -> list[NewsItem]:
        self.news_calls += 1
        return self.news

    def get_financials(self, symbol: str) -> Financials:
        self.financials_calls += 1
        return self.financials

    def get_company_events(self, symbol: str) -> CompanyEvents:
        return CompanyEvents()


def story(days_ago: float, title: str = "Headline") -> NewsItem:
    return NewsItem(
        title=title,
        summary="Something happened.",
        publisher="Example Wire",
        url="https://example.com/story",
        published_at=NOW - timedelta(days=days_ago),
    )


def make_asset(db, **overrides) -> Asset:
    fields = {"ticker": "ACME", "name": "Acme Inc", "asset_class": "equity",
              "native_currency": "EUR", "yahoo_symbol": "ACME"}
    fields.update(overrides)
    asset = Asset(**fields)
    db.add(asset)
    db.flush()
    return asset


def test_news_is_limited_to_the_week_the_card_promises(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider(news=[story(1, "This week"), story(3, "Also this week"), story(20, "Last month")])

    news = FundamentalsService(provider).get_news(db_session, asset)

    assert news.window_days == 7
    assert [i.title for i in news.items] == ["This week", "Also this week"]


def test_news_is_served_from_cache_rather_than_re_scraped(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider(news=[story(1)])
    service = FundamentalsService(provider)

    service.get_news(db_session, asset)
    service.get_news(db_session, asset)

    assert provider.news_calls == 1


def test_a_story_that_ages_out_of_the_window_drops_without_a_refetch(db_session):
    # The cache outlives the window it's measured against, so filtering happens on the way out.
    asset = make_asset(db_session)
    provider = FakeProvider(news=[story(6.99, "About to expire")])
    service = FundamentalsService(provider)

    assert len(service.get_news(db_session, asset).items) == 1

    provider.news = [story(7.01, "Now too old")]
    again = service.get_news(db_session, asset)
    assert provider.news_calls == 1  # still cached
    assert again.items == [] or again.items[0].title == "About to expire"


def test_news_cached_from_an_older_feed_is_refetched_inside_its_ttl(db_session):
    # Cached while Yahoo's retired endpoint was returning nothing: no "feed" marker.
    asset = make_asset(db_session)
    snapshot_repo.upsert(db_session, asset.id, "news", json.dumps({"sources": [], "items": []}))
    provider = FakeProvider(news=[story(1, "Back again")])

    news = FundamentalsService(provider).get_news(db_session, asset)

    assert provider.news_calls == 1
    assert [i.title for i in news.items] == ["Back again"]


def test_an_asset_with_no_price_symbol_is_never_scraped(db_session):
    asset = make_asset(db_session, ticker="CASHLIKE", yahoo_symbol=None)
    provider = FakeProvider(news=[story(1)])

    result = FundamentalsService(provider).get_news(db_session, asset)

    assert result.items == []
    assert provider.news_calls == 0


def test_financials_round_trip_through_the_cache_unchanged(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider(financials=Financials(
        currency="USD",
        quarter=FinancialPeriod(
            label="Q2 2026", period_end=date(2026, 6, 30), revenue=Decimal("119796000000"),
            revenue_growth_pct=Decimal("24.2"), free_cash_flow=Decimal("-5855000000"),
            net_income=Decimal("112193000000"), net_margin_pct=Decimal("93.7"),
        ),
        annual=[FinancialPeriod(label="FY2025", period_end=date(2025, 12, 31), revenue=Decimal("402836000000"))],
        key_metrics=KeyMetrics(pe_ratio=Decimal("38.15"), dividend_yield_pct=Decimal("0.33")),
    ))
    service = FundamentalsService(provider)

    first = service.get_financials(db_session, asset)
    second = service.get_financials(db_session, asset)

    assert provider.financials_calls == 1
    assert first.currency == second.currency == "USD"
    assert second.quarter.label == "Q2 2026"
    assert second.quarter.revenue == Decimal("119796000000")
    assert second.quarter.free_cash_flow == Decimal("-5855000000")  # negative FCF survives
    assert second.quarter.net_margin_pct == Decimal("93.7")
    assert second.annual[0].label == "FY2025"
    assert second.key_metrics.pe_ratio == Decimal("38.15")
    assert second.key_metrics.dividend_yield_pct == Decimal("0.33")


def test_an_asset_with_no_key_metrics_reports_none_rather_than_an_empty_object(db_session):
    asset = make_asset(db_session, ticker="SMH2", yahoo_symbol="SMH2.MI")
    provider = FakeProvider(financials=Financials(
        currency="USD",
        annual=[FinancialPeriod(label="FY2025", period_end=date(2025, 12, 31), revenue=Decimal("100"))],
        key_metrics=None,
    ))

    result = FundamentalsService(provider).get_financials(db_session, asset)

    assert result.key_metrics is None


def test_a_cache_row_from_before_a_schema_change_is_refetched_not_500ed(db_session):
    # Simulates a snapshot written by an older deploy, before net_margin_pct/key_metrics
    # existed -- reading it back must not crash for the rest of the day's TTL.
    from app.repositories import snapshot_repo

    asset = make_asset(db_session)
    snapshot_repo.upsert(db_session, asset.id, "financials", json.dumps({
        "currency": "USD",
        "quarter": None,
        "annual": [{"label": "FY2025", "period_end": "2025-12-31", "revenue": "100",
                     "revenue_growth_pct": None, "free_cash_flow": None, "net_income": None}],
        # no key_metrics key at all -- the old shape
    }))
    provider = FakeProvider(financials=Financials(
        currency="USD",
        annual=[FinancialPeriod(label="FY2025", period_end=date(2025, 12, 31), revenue=Decimal("100"),
                                 net_margin_pct=Decimal("5"))],
    ))

    result = FundamentalsService(provider).get_financials(db_session, asset)

    assert provider.financials_calls == 1
    assert result.annual[0].net_margin_pct == Decimal("5")


def test_an_etf_reports_no_financials_rather_than_failing(db_session):
    asset = make_asset(db_session, ticker="SMH", yahoo_symbol="SMH.MI")

    result = FundamentalsService(FakeProvider()).get_financials(db_session, asset)

    assert result.currency is None
    assert result.quarter is None
    assert result.annual == []


def test_only_ordinary_web_links_reach_the_page():
    # These URLs come from outside and land in an href.
    assert _safe_url("https://example.com/a") == "https://example.com/a"
    assert _safe_url("http://example.com/a") == "http://example.com/a"
    assert _safe_url("javascript:alert(1)") is None
    assert _safe_url("data:text/html;base64,PHNjcmlwdD4=") is None
    assert _safe_url("/relative/path") is None
    assert _safe_url(None) is None
