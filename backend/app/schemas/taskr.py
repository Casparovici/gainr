import enum
from datetime import date as date_, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.notr import NotrPinnedNoteOut


class AgendaSource(str, enum.Enum):
    GARDNR = "gardnr"
    TRAINR = "trainr"
    TASKR = "taskr"


class AgendaItemOut(BaseModel):
    """One thing on the agenda, in the shape every module's agenda provider returns. `key` is
    stable per item so the frontend can tell items apart. A module's item carries `link`, the
    owning module's page where it's completed; taskr's own task carries `task_id` instead, and is
    ticked off right on the agenda (docs/adr/0038 and its addendum)."""

    key: str
    source: AgendaSource
    title: str
    detail: str | None = None
    due_date: date_
    is_overdue: bool
    link: str | None = None
    task_id: int | None = None


class AgendaDayOut(BaseModel):
    date: date_
    items: list[AgendaItemOut]


class AgendaOut(BaseModel):
    date_from: date_
    date_to: date_
    # Everything due before `date_from` and not yet done, oldest first.
    overdue: list[AgendaItemOut]
    # One entry per day in the range that has something due, in date order.
    days: list[AgendaDayOut]


# -- taskr's own tasks ---------------------------------------------------------------------------


class TaskrTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    notes: str | None
    due_date: date_
    completed_at: datetime | None


class TaskrTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    due_date: date_


class TaskrTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    # Sent as null (or blank), clears the notes.
    notes: str | None = Field(default=None, max_length=2000)
    due_date: date_ | None = None


class TaskrTaskCompletedIn(BaseModel):
    is_completed: bool


# -- Vandaag: the app's start screen -------------------------------------------------------------


class TodayPortfolioOut(BaseModel):
    """The chosen gainr portfolio's value and its move since yesterday's close (the chart's 1D
    range: time-weighted, at the hourly live prices while they're current)."""

    portfolio_id: int
    name: str
    value_eur: Decimal | None
    day_change_eur: Decimal | None
    day_change_pct: Decimal | None


class TodayMoneyOut(BaseModel):
    """gripr's checking balance forecast for the running period: what could leave the account
    today without the forecast dipping into a week of everyday spending."""

    safe_to_move_eur: Decimal | None
    expected_end_eur: Decimal | None


class TodayReportOut(BaseModel):
    id: int
    title: str
    attention: str


class TodayMealOut(BaseModel):
    title: str
    is_cooked: bool


class TodayCountsOut(BaseModel):
    """What waits in each module, for Vandaag's attention list and the module switcher's badges."""

    gripr_uncategorized: int
    gardnr_due: int  # overdue or due today
    trainr_today: int  # planned for today, not done yet
    taskr_overdue: int
    listr_to_get: int  # unticked items on the active shopping lists
    briefr_unread: int
    notr_pinned: int = 0  # pinned notes


class TodayOut(BaseModel):
    date: date_
    agenda: AgendaOut  # overdue, and today's items
    portfolio: TodayPortfolioOut | None
    money: TodayMoneyOut | None
    latest_unread_report: TodayReportOut | None
    meal: TodayMealOut | None
    pinned_notes: list[NotrPinnedNoteOut] = []  # notr's pinned notes, newest edit first
    counts: TodayCountsOut
