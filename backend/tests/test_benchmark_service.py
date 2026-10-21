from datetime import date
from decimal import Decimal

import pytest

from app.models.price_history import PriceHistory
from app.repositories import asset_repo
from app.services import benchmark_service as module
from app.services.benchmark_service import benchmark_service


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    calls = []
    monkeypatch.setattr(module.price_service, "ensure_history", lambda db, asset, start, end: calls.append((asset.ticker, start, end)))
    monkeypatch.setattr(module.price_service, "get_daily_price", lambda db, asset: None)
    return calls


def test_the_three_benchmarks_are_offered_by_key():
    assert [(b.key, b.symbol) for b in benchmark_service.list_benchmarks()] == [
        ("sp500", "^GSPC"),
        ("nasdaq", "^IXIC"),
        ("iwda", "IWDA.AS"),
    ]


def test_a_series_is_the_cached_closes_of_its_pseudo_asset_within_the_range(db_session, no_network):
    # The first call creates the BM:sp500 pseudo-asset; seed its cache, then ask again.
    assert benchmark_service.get_series(db_session, "sp500", date(2026, 1, 2), date(2026, 1, 5)) == []
    asset = asset_repo.get_by_ticker(db_session, "BM:sp500")
    assert (asset.asset_class, asset.yahoo_symbol) == ("benchmark", "^GSPC")
    for day, close in ((date(2026, 1, 1), "5800.5"), (date(2026, 1, 2), "5850.25"), (date(2026, 1, 5), "5900")):
        db_session.add(PriceHistory(asset_id=asset.id, date=day, close_price=Decimal(close)))
    db_session.flush()

    series = benchmark_service.get_series(db_session, "sp500", date(2026, 1, 2), date(2026, 1, 5))

    assert series == [(date(2026, 1, 2), Decimal("5850.25")), (date(2026, 1, 5), Decimal("5900"))]
    # Backfilled for the asked range, and the pseudo-asset is reused rather than made twice.
    assert no_network == [("BM:sp500", date(2026, 1, 2), date(2026, 1, 5))] * 2


def test_an_unknown_benchmark_is_an_empty_series(db_session, no_network):
    assert benchmark_service.get_series(db_session, "dax", date(2026, 1, 1), date(2026, 1, 5)) == []
    assert no_network == []
