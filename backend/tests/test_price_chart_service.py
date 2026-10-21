"""A position's price chart: daily closes with the live quote for 1W, 1M, YTD and 3Y, and the last
session through the day for 1D (docs/adr/0053). Dates and clock are fixed, nothing reads the real
ones, and the provider is a fake."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.asset import Asset
from app.models.price_history import PriceHistory
from app.routers import assets as assets_router
from app.services.price_chart_service import FALLBACK_DAYS, INTRADAY_TTL, PriceChartService
from app.services.price_provider import PriceProvider
from app.services.price_service import PriceService

TODAY = date(2026, 10, 20)  # a Tuesday
NOW = datetime(2026, 10, 20, 12, 0)  # naive UTC


class FakeProvider(PriceProvider):
    def __init__(self, bars=None, history=None):
        self.bars = bars or []
        self.history = history or {}
        self.intraday_calls = 0

    def get_history(self, symbol, start, end):
        return {d: p for d, p in self.history.items() if start <= d <= end}

    def get_currency(self, symbol):
        return "EUR"

    def get_intraday(self, symbol):
        self.intraday_calls += 1
        return list(self.bars)


class Clock:
    def __init__(self, now=NOW):
        self.now = now

    def __call__(self):
        return self.now


def make_asset(db, **overrides) -> Asset:
    fields = {"ticker": "ACME", "name": "Acme", "asset_class": "equity", "native_currency": "EUR",
              "yahoo_symbol": "ACME", "price_scale": Decimal(1)}
    fields.update(overrides)
    asset = Asset(**fields)
    db.add(asset)
    db.flush()
    return asset


def seed_closes(db, asset, start: date, end: date, first=Decimal(100), step=Decimal(1)):
    """A close on every weekday from start to end, rising by `step` a day."""
    price, day, rows = first, start, {}
    while day <= end:
        if day.weekday() < 5:
            rows[day] = price
            db.add(PriceHistory(asset_id=asset.id, date=day, close_price=price))
            price += step
        day += timedelta(days=1)
    db.flush()
    return rows


def service(provider=None, clock=None):
    provider = provider or FakeProvider()
    clock = clock or Clock()
    prices = PriceService(provider=provider, clock=clock)
    return PriceChartService(prices=prices, clock=clock), provider, clock


def bars(day: date, prices: list[str], hour=9, tz=timezone(timedelta(hours=2))):
    """15-minute bars from `hour`:00 on `day`, in the exchange's timezone (UTC+2)."""
    start = datetime(day.year, day.month, day.day, hour, 0, tzinfo=tz)
    return [(start + timedelta(minutes=15 * i), Decimal(p)) for i, p in enumerate(prices)]


# -- daily ranges ---------------------------------------------------------------------------


def test_a_month_of_closes_with_the_change_from_the_first_to_the_last(db_session):
    asset = make_asset(db_session)
    seed_closes(db_session, asset, TODAY - timedelta(days=60), TODAY)
    svc, _, _ = service()

    chart = svc.build(db_session, asset, "1M", TODAY)

    assert chart.interval == "daily" and chart.currency == "EUR" and chart.range == "1M"
    dates = [p.time for p in chart.points]
    assert dates == sorted(dates) and dates[0] >= (TODAY - timedelta(days=30)).isoformat() and dates[-1] == TODAY.isoformat()
    assert chart.start_price == chart.points[0].price and chart.end_price == chart.points[-1].price
    assert chart.change == chart.end_price - chart.start_price
    assert chart.change_pct == chart.change / chart.start_price * 100
    assert chart.is_fallback is False and chart.as_of is None


@pytest.mark.parametrize(
    ("range_key", "earliest"),
    [("1W", TODAY - timedelta(days=7)), ("1M", TODAY - timedelta(days=30)), ("YTD", date(2026, 1, 1)), ("3Y", TODAY - timedelta(days=1095))],
)
def test_each_range_starts_where_it_says(db_session, range_key, earliest):
    asset = make_asset(db_session)
    seed_closes(db_session, asset, TODAY - timedelta(days=4 * 365), TODAY)
    svc, _, _ = service()

    chart = svc.build(db_session, asset, range_key, TODAY)

    assert chart.points[0].time >= earliest.isoformat()
    # the first point is within a few days of the start: markets are shut on weekends
    assert date.fromisoformat(chart.points[0].time) - earliest <= timedelta(days=4)


def test_a_range_reaching_back_past_the_cache_backfills_it_from_the_provider(db_session):
    asset = make_asset(db_session)
    history = seed_closes(db_session, asset, TODAY - timedelta(days=30), TODAY)  # cached: a month
    older = {d: Decimal(50) for d in (TODAY - timedelta(days=400) + timedelta(days=i) for i in range(0, 400)) if d.weekday() < 5}
    svc, provider, _ = service(FakeProvider(history={**older, **history}))

    chart = svc.build(db_session, asset, "3Y", TODAY)

    assert date.fromisoformat(chart.points[0].time) <= TODAY - timedelta(days=395)
    assert len(chart.points) > len(history)


def test_the_live_quote_is_todays_point_while_there_is_no_close_for_it(db_session):
    asset = make_asset(db_session)
    seed_closes(db_session, asset, TODAY - timedelta(days=30), TODAY - timedelta(days=1))
    asset.quote_price = Decimal("150.5")
    asset.quoted_at = datetime(2026, 10, 20, 9, 45)
    asset.quote_checked_at = NOW - timedelta(minutes=20)
    svc, _, _ = service()

    chart = svc.build(db_session, asset, "1M", TODAY)

    assert (chart.points[-1].time, chart.points[-1].price) == (TODAY.isoformat(), Decimal("150.5"))
    assert chart.end_price == Decimal("150.5")
    assert chart.as_of == datetime(2026, 10, 20, 9, 45, tzinfo=timezone.utc).replace(tzinfo=None)


def test_a_stale_live_quote_is_left_out(db_session):
    asset = make_asset(db_session)
    seed_closes(db_session, asset, TODAY - timedelta(days=30), TODAY - timedelta(days=1))
    asset.quote_price = Decimal("150.5")
    asset.quoted_at = datetime(2026, 10, 20, 9, 45)
    asset.quote_checked_at = NOW - timedelta(hours=5)  # the hourly refresh stopped
    svc, _, _ = service()

    chart = svc.build(db_session, asset, "1M", TODAY)

    assert chart.points[-1].time == (TODAY - timedelta(days=1)).isoformat() and chart.as_of is None


def test_a_close_for_the_quotes_day_wins_over_the_quote(db_session):
    asset = make_asset(db_session)
    seed_closes(db_session, asset, TODAY - timedelta(days=30), TODAY)
    asset.quote_price = Decimal("999")
    asset.quoted_at = datetime(2026, 10, 20, 9, 45)
    asset.quote_checked_at = NOW - timedelta(minutes=20)
    svc, _, _ = service()

    chart = svc.build(db_session, asset, "1M", TODAY)

    assert chart.points[-1].price != Decimal("999") and chart.as_of is None


def test_an_asset_without_a_price_symbol_has_an_empty_chart(db_session):
    asset = make_asset(db_session, yahoo_symbol=None, ticker="CASH", asset_class="cash")
    svc, provider, _ = service()

    for range_key in ("1D", "1M", "3Y"):
        chart = svc.build(db_session, asset, range_key, TODAY)
        assert chart.points == [] and chart.change is None and chart.change_pct is None and chart.end_price is None

    assert provider.intraday_calls == 0


def test_an_unknown_range_is_refused(db_session):
    asset = make_asset(db_session)
    svc, _, _ = service()

    with pytest.raises(ValueError):
        svc.build(db_session, asset, "5Y", TODAY)


# -- 1D -------------------------------------------------------------------------------------


def test_one_day_is_the_last_session_through_the_day_measured_from_the_previous_close(db_session):
    asset = make_asset(db_session)
    seed_closes(db_session, asset, TODAY - timedelta(days=10), TODAY - timedelta(days=1), first=Decimal(100))
    previous_close = db_session.query(PriceHistory).filter_by(asset_id=asset.id, date=TODAY - timedelta(days=1)).one().close_price
    svc, _, _ = service(FakeProvider(bars=bars(TODAY, ["101", "102.5", "99"])))

    chart = svc.build(db_session, asset, "1D", TODAY)

    assert chart.interval == "intraday" and chart.is_fallback is False
    # 09:00 in UTC+2 is 07:00 UTC
    assert [p.time for p in chart.points] == ["2026-10-20T07:00:00Z", "2026-10-20T07:15:00Z", "2026-10-20T07:30:00Z"]
    assert [p.price for p in chart.points] == [Decimal("101"), Decimal("102.5"), Decimal("99")]
    assert chart.start_price == Decimal(str(previous_close))
    assert chart.change == Decimal("99") - Decimal(str(previous_close))
    assert chart.as_of == datetime(2026, 10, 20, 7, 30)


def test_one_day_without_an_earlier_close_is_measured_from_the_first_bar(db_session):
    asset = make_asset(db_session)
    svc, _, _ = service(FakeProvider(bars=bars(TODAY, ["50", "55"])))

    chart = svc.build(db_session, asset, "1D", TODAY)

    assert chart.start_price == Decimal(50) and chart.change == Decimal(5) and chart.change_pct == Decimal(10)


def test_intraday_prices_are_scaled_like_closes(db_session):
    asset = make_asset(db_session, native_currency="GBP", price_scale=Decimal("0.01"))  # quoted in pence
    svc, _, _ = service(FakeProvider(bars=bars(TODAY, ["1234.5", "1240"])))

    chart = svc.build(db_session, asset, "1D", TODAY)

    assert chart.currency == "GBP" and chart.points[0].price == Decimal("12.345")


def test_intraday_bars_are_kept_for_ten_minutes_and_then_fetched_again(db_session):
    asset = make_asset(db_session)
    svc, provider, clock = service(FakeProvider(bars=bars(TODAY, ["10", "11"])))

    svc.build(db_session, asset, "1D", TODAY)
    clock.now = NOW + INTRADAY_TTL - timedelta(seconds=1)
    svc.build(db_session, asset, "1D", TODAY)
    assert provider.intraday_calls == 1

    clock.now = NOW + INTRADAY_TTL
    svc.build(db_session, asset, "1D", TODAY)
    assert provider.intraday_calls == 2


def test_the_range_buttons_share_one_fetch_but_other_assets_do_not(db_session):
    first, second = make_asset(db_session), make_asset(db_session, ticker="OTHER", yahoo_symbol="OTHER")
    svc, provider, _ = service(FakeProvider(bars=bars(TODAY, ["10", "11"])))

    svc.build(db_session, first, "1D", TODAY)
    svc.build(db_session, first, "1D", TODAY)
    svc.build(db_session, second, "1D", TODAY)

    assert provider.intraday_calls == 2


def test_one_day_falls_back_to_the_last_weeks_closes_when_there_are_no_bars(db_session):
    asset = make_asset(db_session)
    seed_closes(db_session, asset, TODAY - timedelta(days=30), TODAY - timedelta(days=1))
    svc, _, _ = service(FakeProvider(bars=[]))

    chart = svc.build(db_session, asset, "1D", TODAY)

    assert chart.is_fallback is True and chart.interval == "daily" and chart.range == "1D"
    assert date.fromisoformat(chart.points[0].time) >= TODAY - timedelta(days=FALLBACK_DAYS)
    assert chart.change is not None


def test_a_failed_intraday_fetch_isnt_retried_on_every_click(db_session):
    asset = make_asset(db_session)
    seed_closes(db_session, asset, TODAY - timedelta(days=30), TODAY - timedelta(days=1))
    svc, provider, _ = service(FakeProvider(bars=[]))

    svc.build(db_session, asset, "1D", TODAY)
    svc.build(db_session, asset, "1D", TODAY)

    assert provider.intraday_calls == 1


# -- the HTTP surface -----------------------------------------------------------------------


@pytest.fixture()
def client(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(assets_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    svc, _, _ = service(FakeProvider(bars=bars(date.today(), ["10", "11"])))
    monkeypatch.setattr(assets_router, "price_chart_service", svc)
    return TestClient(app)


def test_the_endpoint_returns_the_chart(client, db_session):
    asset = make_asset(db_session)
    seed_closes(db_session, asset, date.today() - timedelta(days=60), date.today() - timedelta(days=1))
    db_session.commit()

    body = client.get(f"/api/assets/{asset.id}/prices", params={"range": "1M"}).json()

    assert body["range"] == "1M" and body["currency"] == "EUR" and body["interval"] == "daily"
    assert len(body["points"]) > 10 and set(body["points"][0]) == {"time", "price"}
    assert body["change_pct"] is not None and body["as_of"] is None


def test_the_endpoint_defaults_to_a_month_and_serves_one_day_intraday(client, db_session):
    asset = make_asset(db_session)
    db_session.commit()

    assert client.get(f"/api/assets/{asset.id}/prices").json()["range"] == "1M"
    one_day = client.get(f"/api/assets/{asset.id}/prices", params={"range": "1D"}).json()
    assert one_day["interval"] == "intraday" and one_day["as_of"].endswith("+00:00")


def test_the_endpoint_refuses_an_unknown_range_and_asset(client, db_session):
    asset = make_asset(db_session)
    db_session.commit()

    assert client.get(f"/api/assets/{asset.id}/prices", params={"range": "5Y"}).status_code == 422
    assert client.get("/api/assets/999/prices").status_code == 404
