"""A position's Calendar tab: the provider's earnings and dividend dates merged with the
milestones the user adds by hand (investor days, AGMs, ...). See docs/adr/0025.

The provider's part is a slow scrape, cached per asset for a day in asset_snapshots like
financials are -- an earnings date only moves when the company confirms it. It's cached raw and
filtered against today on the way out, since a cached "upcoming" date turns into a past one
without anything being re-fetched.
"""

import json
from datetime import date, timedelta
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.position_event import PositionEvent, PositionEventKind
from app.repositories import position_event_repo, snapshot_repo
from app.schemas.calendar import CalendarEventOut, CompanyEventsCache, EarningsResultOut, PositionCalendarOut
from app.services.fundamentals_provider import FundamentalsProvider, YFinanceFundamentalsProvider

CALENDAR_KIND = "calendar"
CALENDAR_TTL = timedelta(days=1)
# Two years of quarters: enough to see whether a company habitually beats, without a wall.
RESULTS_SHOWN = 8
# The user's own past events stay visible for a year (last year's investor day is useful
# context for this year's), then drop off the tab.
PAST_EVENTS_DAYS = 365

MANUAL_TITLES = {
    PositionEventKind.INVESTOR_DAY: "Investor day",
    PositionEventKind.CAPITAL_MARKETS_DAY: "Capital markets day",
    PositionEventKind.AGM: "Shareholder meeting",
    PositionEventKind.PRODUCT_EVENT: "Product event",
    PositionEventKind.OTHER: "Event",
}


def surprise_pct(estimate: Decimal | None, actual: Decimal | None) -> Decimal | None:
    if estimate is None or actual is None or estimate == 0:
        return None
    return ((actual - estimate) / abs(estimate) * 100).quantize(Decimal("0.01"))


def manual_event_out(event: PositionEvent) -> CalendarEventOut:
    return CalendarEventOut(
        id=event.id,
        source="manual",
        kind=event.kind.value,
        date=event.date,
        title=event.title,
        notes=event.notes,
    )


class CalendarService:
    def __init__(self, provider: FundamentalsProvider | None = None):
        self.provider = provider or YFinanceFundamentalsProvider()

    def get_calendar(self, db: Session, asset: Asset, today: date | None = None) -> PositionCalendarOut:
        today = today or date.today()
        company = self._company_events(db, asset)

        upcoming: list[CalendarEventOut] = []
        earnings = self._next_earnings(company, today)
        if earnings:
            upcoming.append(earnings)
        if company.ex_dividend_date and company.ex_dividend_date >= today:
            upcoming.append(CalendarEventOut(source="yahoo", kind="ex_dividend", date=company.ex_dividend_date, title="Ex-dividend"))
        if company.dividend_payment_date and company.dividend_payment_date >= today:
            upcoming.append(
                CalendarEventOut(source="yahoo", kind="dividend_payment", date=company.dividend_payment_date, title="Dividend paid")
            )

        past: list[CalendarEventOut] = []
        for event in position_event_repo.list_events(db, asset.id):
            if event.date >= today:
                upcoming.append(manual_event_out(event))
            elif event.date >= today - timedelta(days=PAST_EVENTS_DAYS):
                past.append(manual_event_out(event))

        results = [
            EarningsResultOut(
                report_date=r.report_date,
                eps_estimate=r.eps_estimate,
                eps_actual=r.eps_actual,
                surprise_pct=surprise_pct(r.eps_estimate, r.eps_actual),
            )
            for r in company.results
            if r.report_date < today and r.eps_actual is not None
        ][:RESULTS_SHOWN]

        return PositionCalendarOut(
            currency=company.currency,
            upcoming=sorted(upcoming, key=lambda e: e.date),
            past=sorted(past, key=lambda e: e.date, reverse=True),
            results=results,
        )

    @staticmethod
    def _next_earnings(company: CompanyEventsCache, today: date) -> CalendarEventOut | None:
        """The next earnings release on or after today. Yahoo's calendar entry is the primary
        source (it carries the consensus figures); when it's stale -- a small cap whose "next"
        date is one that already passed -- a future row in the earnings history stands in,
        marked as an estimate and without figures, since those belonged to the stale entry."""
        dates = [d for d in company.earnings_dates if d >= today]
        if dates:
            window_end = dates[-1] if company.earnings_is_estimate and len(dates) > 1 else None
            return CalendarEventOut(
                source="yahoo",
                kind="earnings",
                date=dates[0],
                end_date=window_end,
                title="Earnings",
                is_estimate=company.earnings_is_estimate,
                time_of_day=company.earnings_time,
                eps_estimate=company.eps_estimate,
                revenue_estimate=company.revenue_estimate,
            )
        scheduled = sorted(r.report_date for r in company.results if r.report_date >= today and r.eps_actual is None)
        if scheduled:
            return CalendarEventOut(source="yahoo", kind="earnings", date=scheduled[0], title="Earnings", is_estimate=True)
        return None

    def _company_events(self, db: Session, asset: Asset) -> CompanyEventsCache:
        snapshot = snapshot_repo.get_fresh(db, asset.id, CALENDAR_KIND, CALENDAR_TTL)
        if snapshot is not None:
            try:
                return CompanyEventsCache(**json.loads(snapshot.payload))
            except (json.JSONDecodeError, ValidationError, TypeError):
                pass  # unreadable or outdated cache row: re-fetch, same as financials

        if asset.yahoo_symbol:
            company = CompanyEventsCache.model_validate(self.provider.get_company_events(asset.yahoo_symbol))
        else:
            company = CompanyEventsCache()
        snapshot_repo.upsert(db, asset.id, CALENDAR_KIND, json.dumps(company.model_dump(mode="json")))
        return company


calendar_service = CalendarService()
