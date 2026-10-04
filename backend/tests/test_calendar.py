"""A position's Calendar tab (docs/adr/0025): the provider's earnings/dividend dates, filtered
against today, merged with the user's own events."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.asset import Asset
from app.models.position_event import PositionEvent, PositionEventKind
from app.routers import calendar as calendar_router
from app.services.calendar_service import CalendarService, surprise_pct
from app.services.fundamentals_provider import (
    CompanyEvents,
    EarningsResult,
    FundamentalsProvider,
    build_company_events,
)

TODAY = date(2026, 9, 30)
NY = ZoneInfo("America/New_York")


class FakeProvider(FundamentalsProvider):
    def __init__(self, events: CompanyEvents | None = None):
        self.events = events or CompanyEvents()
        self.calls = 0

    def get_news(self, symbol):
        return []

    def get_financials(self, symbol):
        raise NotImplementedError

    def get_company_events(self, symbol):
        self.calls += 1
        return self.events


def make_asset(db, ticker="AMZN", yahoo_symbol="AMZN") -> Asset:
    asset = Asset(ticker=ticker, name=f"{ticker} Inc", asset_class="equity", native_currency="USD", yahoo_symbol=yahoo_symbol)
    db.add(asset)
    db.flush()
    return asset


# -- parsing yfinance's payloads -----------------------------------------------------------------


def test_a_confirmed_us_release_after_4pm_is_after_close():
    events = build_company_events(
        {"Earnings Date": [date(2026, 10, 29)], "Earnings Average": 1.97, "Revenue Average": 2.0e11},
        {"exchangeTimezoneName": "America/New_York", "isEarningsDateEstimate": False, "financialCurrency": "USD"},
        [(datetime(2026, 10, 29, 16, 0, tzinfo=NY), 1.95, None), (datetime(2026, 7, 30, 16, 0, tzinfo=NY), 1.83, 5.75)],
    )
    assert events.earnings_dates == [date(2026, 10, 29)]
    assert events.earnings_time == "after_close"
    assert events.eps_estimate == Decimal("1.97")
    assert events.currency == "USD"
    assert [r.report_date for r in events.results] == [date(2026, 10, 29), date(2026, 7, 30)]


def test_a_us_release_before_the_open_is_before_open():
    events = build_company_events(
        {"Earnings Date": [date(2026, 11, 5)]},
        {"exchangeTimezoneName": "America/New_York"},
        [(datetime(2026, 11, 5, 7, 0, tzinfo=NY), 1.0, None)],
    )
    assert events.earnings_time == "before_open"


def test_a_european_listing_gets_no_time_of_day():
    events = build_company_events(
        {"Earnings Date": [date(2026, 11, 11)]},
        {"exchangeTimezoneName": "Europe/Amsterdam"},
        [(datetime(2026, 11, 11, 10, 0, tzinfo=NY), 0.92, None)],
    )
    assert events.earnings_time is None


def test_two_calendar_dates_are_an_estimated_window():
    events = build_company_events({"Earnings Date": [date(2026, 11, 3), date(2026, 11, 7)]}, {}, [])
    assert events.earnings_is_estimate is True
    assert events.earnings_dates == [date(2026, 11, 3), date(2026, 11, 7)]


def test_nothing_known_is_empty():
    assert build_company_events({}, {}, []).is_empty()


def test_surprise_is_relative_to_the_estimates_size():
    assert surprise_pct(Decimal("1.83"), Decimal("5.75")) == Decimal("214.21")
    assert surprise_pct(Decimal("-0.10"), Decimal("-0.05")) == Decimal("50.00")
    assert surprise_pct(Decimal("0"), Decimal("1")) is None
    assert surprise_pct(None, Decimal("1")) is None


# -- the service -------------------------------------------------------------------------------


def test_upcoming_earnings_and_dividends_come_with_their_details(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider(CompanyEvents(
        currency="USD", earnings_dates=[date(2026, 10, 29)], earnings_time="after_close",
        eps_estimate=Decimal("1.97"), revenue_estimate=Decimal("2.0E+11"),
        ex_dividend_date=date(2026, 11, 20), dividend_payment_date=date(2026, 12, 10),
    ))
    calendar = CalendarService(provider).get_calendar(db_session, asset, today=TODAY)

    assert [(e.kind, e.date) for e in calendar.upcoming] == [
        ("earnings", date(2026, 10, 29)), ("ex_dividend", date(2026, 11, 20)), ("dividend_payment", date(2026, 12, 10)),
    ]
    earnings = calendar.upcoming[0]
    assert earnings.time_of_day == "after_close" and earnings.eps_estimate == Decimal("1.97")
    assert calendar.currency == "USD"


def test_a_stale_calendar_date_falls_back_to_the_next_scheduled_release(db_session):
    # tonies: Yahoo's calendar still says August, but a future row exists for April.
    asset = make_asset(db_session, "TNIE", "TNIE.DE")
    provider = FakeProvider(CompanyEvents(
        earnings_dates=[date(2026, 8, 20)], eps_estimate=Decimal("0.1"),
        results=[EarningsResult(report_date=date(2027, 4, 13))],
    ))
    calendar = CalendarService(provider).get_calendar(db_session, asset, today=TODAY)

    (earnings,) = calendar.upcoming
    assert earnings.date == date(2027, 4, 13)
    assert earnings.is_estimate is True
    assert earnings.eps_estimate is None  # that figure belonged to the stale August entry


def test_past_dividend_dates_are_left_out(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider(CompanyEvents(ex_dividend_date=date(2017, 12, 28), dividend_payment_date=date(2018, 1, 16)))
    assert CalendarService(provider).get_calendar(db_session, asset, today=TODAY).upcoming == []


def test_results_are_past_reported_quarters_only_newest_first_capped_at_eight(db_session):
    asset = make_asset(db_session)
    past = [EarningsResult(report_date=TODAY - timedelta(days=90 * i), eps_estimate=Decimal("1"), eps_actual=Decimal("1.1"))
            for i in range(1, 11)]
    upcoming = EarningsResult(report_date=TODAY + timedelta(days=29), eps_estimate=Decimal("2"))
    provider = FakeProvider(CompanyEvents(results=[upcoming, *past]))
    results = CalendarService(provider).get_calendar(db_session, asset, today=TODAY).results

    assert len(results) == 8
    assert results[0].report_date == TODAY - timedelta(days=90)
    assert results[0].surprise_pct == Decimal("10.00")


def test_own_events_split_into_upcoming_and_the_last_years_past(db_session):
    asset = make_asset(db_session)
    for d, title in ((TODAY + timedelta(days=49), "Investor Day"), (TODAY - timedelta(days=30), "AGM"),
                     (TODAY - timedelta(days=400), "Old CMD")):
        db_session.add(PositionEvent(asset_id=asset.id, date=d, kind=PositionEventKind.INVESTOR_DAY, title=title))
    db_session.flush()
    calendar = CalendarService(FakeProvider()).get_calendar(db_session, asset, today=TODAY)

    assert [(e.title, e.source) for e in calendar.upcoming] == [("Investor Day", "manual")]
    assert [e.title for e in calendar.past] == ["AGM"]


def test_the_provider_is_asked_once_a_day(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider(CompanyEvents(earnings_dates=[date(2026, 10, 29)]))
    service = CalendarService(provider)
    service.get_calendar(db_session, asset, today=TODAY)
    again = service.get_calendar(db_session, asset, today=TODAY)

    assert provider.calls == 1
    assert again.upcoming[0].date == date(2026, 10, 29)


def test_an_asset_without_a_yahoo_symbol_is_never_looked_up(db_session):
    asset = make_asset(db_session, "CASH", None)
    provider = FakeProvider()
    calendar = CalendarService(provider).get_calendar(db_session, asset, today=TODAY)
    assert provider.calls == 0 and calendar.upcoming == [] and calendar.results == []


# -- the API: your own events ---------------------------------------------------------------------


@pytest.fixture()
def client(db_session, monkeypatch):
    from app.services import calendar_service as module
    monkeypatch.setattr(module, "calendar_service", CalendarService(FakeProvider()))
    monkeypatch.setattr(calendar_router, "calendar_service", module.calendar_service)
    app = FastAPI()
    app.include_router(calendar_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_adding_editing_and_deleting_an_own_event(client, db_session):
    asset = make_asset(db_session)
    future = (date.today() + timedelta(days=30)).isoformat()
    created = client.post(f"/api/assets/{asset.id}/events", json={"date": future, "kind": "investor_day", "title": "Investor Day"})
    assert created.status_code == 200
    event = created.json()
    assert event["source"] == "manual" and event["kind"] == "investor_day"

    upcoming = client.get(f"/api/assets/{asset.id}/calendar").json()["upcoming"]
    assert [e["title"] for e in upcoming] == ["Investor Day"]

    edited = client.put(f"/api/assets/{asset.id}/events/{event['id']}", json={"title": "Investor Day 2026", "notes": "AWS margins"}).json()
    assert edited["title"] == "Investor Day 2026" and edited["notes"] == "AWS margins"

    assert client.delete(f"/api/assets/{asset.id}/events/{event['id']}").status_code == 204
    assert client.get(f"/api/assets/{asset.id}/calendar").json()["upcoming"] == []


def test_own_events_are_validated_and_scoped_to_their_asset(client, db_session):
    asset = make_asset(db_session)
    other = make_asset(db_session, "GOOGL", "GOOGL")
    when = date.today().isoformat()

    assert client.post(f"/api/assets/{asset.id}/events", json={"date": when, "kind": "agm", "title": ""}).status_code == 422
    assert client.post(f"/api/assets/{asset.id}/events", json={"date": when, "kind": "earnings", "title": "x"}).status_code == 422
    assert client.post("/api/assets/9999/events", json={"date": when, "kind": "agm", "title": "AGM"}).status_code == 404

    event = client.post(f"/api/assets/{asset.id}/events", json={"date": when, "kind": "agm", "title": "AGM"}).json()
    assert client.put(f"/api/assets/{other.id}/events/{event['id']}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/api/assets/{other.id}/events/{event['id']}").status_code == 404
    assert client.put(f"/api/assets/{asset.id}/events/{event['id']}", json={"title": None}).status_code == 400
