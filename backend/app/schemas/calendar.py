from datetime import date as date_
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.position_event import PositionEventKind

CalendarEventKind = Literal[
    # From the data provider
    "earnings",
    "ex_dividend",
    "dividend_payment",
    # Added by hand (PositionEventKind)
    "investor_day",
    "capital_markets_day",
    "agm",
    "product_event",
    "other",
]


class CalendarEventOut(BaseModel):
    # Only set on events the user added -- the handle for editing/deleting them.
    id: int | None = None
    source: Literal["yahoo", "manual"]
    kind: CalendarEventKind
    date: date_
    # Set only when the provider gives a window rather than a confirmed day.
    end_date: date_ | None = None
    title: str
    is_estimate: bool = False
    time_of_day: Literal["before_open", "after_close"] | None = None
    # Earnings only: consensus for the quarter being reported, in PositionCalendarOut.currency.
    eps_estimate: Decimal | None = None
    revenue_estimate: Decimal | None = None
    notes: str | None = None


class EarningsResultOut(BaseModel):
    report_date: date_
    eps_estimate: Decimal | None = None
    eps_actual: Decimal | None = None
    # (actual - estimate) / |estimate|, as a percentage -- positive is a beat.
    surprise_pct: Decimal | None = None


class PositionCalendarOut(BaseModel):
    currency: str | None  # of the EPS/revenue figures; the filer's reporting currency
    upcoming: list[CalendarEventOut]  # soonest first
    past: list[CalendarEventOut]  # the user's own events from the last year, newest first
    results: list[EarningsResultOut]  # reported quarters, newest first


class PositionEventCreate(BaseModel):
    date: date_
    kind: PositionEventKind
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class PositionEventUpdate(BaseModel):
    date: date_ | None = None
    kind: PositionEventKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class _EarningsResultCache(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_date: date_
    eps_estimate: Decimal | None = None
    eps_actual: Decimal | None = None


class CompanyEventsCache(BaseModel):
    """The provider's CompanyEvents as stored in asset_snapshots -- raw, unfiltered by date."""

    model_config = ConfigDict(from_attributes=True)

    currency: str | None = None
    earnings_dates: list[date_] = []
    earnings_is_estimate: bool = False
    earnings_time: Literal["before_open", "after_close"] | None = None
    eps_estimate: Decimal | None = None
    revenue_estimate: Decimal | None = None
    ex_dividend_date: date_ | None = None
    dividend_payment_date: date_ | None = None
    results: list[_EarningsResultCache] = []
