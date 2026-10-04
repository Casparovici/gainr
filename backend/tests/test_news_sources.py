"""Extra news sources per position (docs/adr/0026): sector/industry/ticker feeds merged into a
position's own news, for holdings whose own ticker has little or none (a gold tracker, an ETF)."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.asset import Asset
from app.repositories import snapshot_repo
from app.routers import fundamentals as fundamentals_router
from app.services import news_sources
from app.services.fundamentals_provider import CompanyEvents, Financials, FundamentalsProvider, NewsItem
from app.services.fundamentals_service import NEWS_KIND, FundamentalsService

NOW = datetime.now(timezone.utc)


def story(title, hours_ago=1, url=None) -> NewsItem:
    return NewsItem(
        title=title, summary="", publisher="Wire", url=url or f"https://example.com/{title.replace(' ', '-')}",
        published_at=NOW - timedelta(hours=hours_ago),
    )


class FakeProvider(FundamentalsProvider):
    def __init__(self, own=None, by_source=None):
        self.own = own or []
        self.by_source = by_source or {}
        self.source_calls: list[str] = []

    def get_news(self, symbol):
        return self.own

    def get_source_news(self, source):
        self.source_calls.append(source)
        return self.by_source.get(source, [])

    def get_financials(self, symbol):
        return Financials()

    def get_company_events(self, symbol):
        return CompanyEvents()


def make_asset(db, ticker="JEDI", yahoo_symbol="JEDI.PA", sources=None) -> Asset:
    asset = Asset(ticker=ticker, name=ticker, asset_class="equity", native_currency="EUR", yahoo_symbol=yahoo_symbol,
                  news_sources=json.dumps(sources) if sources else None)
    db.add(asset)
    db.flush()
    return asset


# -- the catalogue ----------------------------------------------------------------------------


def test_the_catalogue_uses_keys_yahoo_accepts():
    # yfinance's own lowercase table spells this "utilities—renewable" (em-dash), which Yahoo rejects.
    assert "utilities-renewable" in news_sources.INDUSTRIES
    assert "aerospace-defense" in news_sources.INDUSTRIES
    assert "solar" in news_sources.INDUSTRIES
    assert len(news_sources.SECTORS) == 11
    assert news_sources.label("industry:aerospace-defense") == "Aerospace & Defense"
    assert news_sources.label("ticker:GC=F") == "Gold (futures)"
    assert news_sources.label("ticker:NVDA") == "NVDA"


def test_validation_normalises_dedupes_and_rejects_unknown_sources():
    assert news_sources.validate(["industry:solar", "ticker:gc=f", "industry:solar"]) == ["industry:solar", "ticker:GC=F"]
    for bad in ("industry:not-a-thing", "sector:commodities", "market:crypto", "ticker:<script>", "solar"):
        with pytest.raises(news_sources.InvalidNewsSource):
            news_sources.validate([bad])
    with pytest.raises(news_sources.InvalidNewsSource):
        news_sources.validate([f"ticker:T{i}" for i in range(news_sources.MAX_SOURCES + 1)])


def test_unreadable_stored_sources_count_as_none():
    assert news_sources.parse_stored("not json") == []
    assert news_sources.parse_stored('{"a": 1}') == []
    assert news_sources.parse_stored(None) == []


# -- merging ----------------------------------------------------------------------------------


def test_source_news_is_merged_newest_first_and_labelled(db_session):
    asset = make_asset(db_session, sources=["industry:aerospace-defense"])
    provider = FakeProvider(
        own=[story("Fund rebalances", hours_ago=5)],
        by_source={"industry:aerospace-defense": [story("Defence budgets rise", hours_ago=1)]},
    )
    news = FundamentalsService(provider).get_news(db_session, asset)

    assert [(i.title, i.source) for i in news.items] == [("Defence budgets rise", "Aerospace & Defense"), ("Fund rebalances", None)]
    assert [(s.key, s.label) for s in news.sources] == [("industry:aerospace-defense", "Aerospace & Defense")]


def test_a_story_in_several_feeds_shows_once_preferring_the_positions_own(db_session):
    asset = make_asset(db_session, sources=["industry:utilities-renewable", "industry:solar"])
    shared = story("Solar tariffs cut", url="https://example.com/shared")
    provider = FakeProvider(
        own=[shared],
        by_source={
            "industry:utilities-renewable": [shared, story("Grid build-out")],
            "industry:solar": [story("Solar tariffs cut", url="https://other.example/same-story")],
        },
    )
    news = FundamentalsService(provider).get_news(db_session, asset)

    assert sorted((i.title, i.source) for i in news.items) == [("Grid build-out", "Utilities – Renewable"), ("Solar tariffs cut", None)]


def test_a_position_without_its_own_symbol_still_gets_its_sources(db_session):
    asset = make_asset(db_session, yahoo_symbol=None, sources=["ticker:GC=F"])
    provider = FakeProvider(by_source={"ticker:GC=F": [story("Gold edges up")]})
    assert [i.title for i in FundamentalsService(provider).get_news(db_session, asset).items] == ["Gold edges up"]


def test_changing_sources_refetches_even_inside_the_cache_window(db_session):
    asset = make_asset(db_session, sources=["industry:solar"])
    provider = FakeProvider(by_source={"industry:solar": [story("A")], "sector:utilities": [story("B")]})
    service = FundamentalsService(provider)
    service.get_news(db_session, asset)
    service.get_news(db_session, asset)
    assert provider.source_calls == ["industry:solar"]  # cached

    service.set_news_sources(db_session, asset, ["sector:utilities"])
    news = service.get_news(db_session, asset)
    assert [i.title for i in news.items] == ["B"]
    assert provider.source_calls == ["industry:solar", "sector:utilities"]


def test_a_cache_from_before_sources_existed_is_refetched(db_session):
    asset = make_asset(db_session)
    snapshot_repo.upsert(db_session, asset.id, NEWS_KIND, json.dumps([]))  # old bare-list format
    provider = FakeProvider(own=[story("Fresh")])
    assert [i.title for i in FundamentalsService(provider).get_news(db_session, asset).items] == ["Fresh"]


# -- the API ----------------------------------------------------------------------------------


@pytest.fixture()
def client(db_session, monkeypatch):
    service = FundamentalsService(FakeProvider(by_source={"ticker:GC=F": [story("Gold edges up")]}))
    monkeypatch.setattr(fundamentals_router, "fundamentals_service", service)
    app = FastAPI()
    app.include_router(fundamentals_router.router)
    app.include_router(fundamentals_router.catalog_router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_setting_sources_returns_the_news_with_them(client, db_session):
    asset = make_asset(db_session, ticker="4GLD", yahoo_symbol="4GLD.DE")
    response = client.put(f"/api/assets/{asset.id}/news-sources", json={"sources": ["ticker:gc=f"]})

    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == [{"key": "ticker:GC=F", "label": "Gold (futures)"}]
    assert [i["title"] for i in body["items"]] == ["Gold edges up"]
    assert client.get(f"/api/assets/{asset.id}/news").json()["sources"][0]["key"] == "ticker:GC=F"

    cleared = client.put(f"/api/assets/{asset.id}/news-sources", json={"sources": []}).json()
    assert cleared["sources"] == [] and cleared["items"] == []


def test_unknown_sources_are_rejected(client, db_session):
    asset = make_asset(db_session)
    assert client.put(f"/api/assets/{asset.id}/news-sources", json={"sources": ["sector:commodities"]}).status_code == 400
    assert client.put("/api/assets/9999/news-sources", json={"sources": []}).status_code == 404


def test_the_catalogue_endpoint_lists_markets_sectors_and_industries(client):
    body = client.get("/api/news-sources/catalog").json()
    assert {"key": "ticker:GC=F", "label": "Gold (futures)"} in body["markets"]
    assert len(body["sectors"]) == 11
    assert {"key": "industry:aerospace-defense", "label": "Aerospace & Defense", "sector": "Industrials"} in body["industries"]
