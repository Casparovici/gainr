from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class NewsItemOut(BaseModel):
    title: str
    summary: str
    publisher: str
    url: str
    published_at: datetime
    # Label of the extra news source this came from ("Aerospace & Defense"); None for the
    # position's own news.
    source: str | None = None


class NewsSourceOut(BaseModel):
    key: str
    label: str


class NewsSourcesUpdate(BaseModel):
    sources: list[str]


class NewsOut(BaseModel):
    # How far back the list reaches, so the card can say what it's showing rather than
    # implying "everything".
    window_days: int
    items: list[NewsItemOut]
    # The position's extra news sources (see news_sources.py), in the order they were added.
    sources: list[NewsSourceOut] = []


class FinancialPeriodOut(BaseModel):
    # Built straight from the provider's dataclass as well as from cached JSON.
    model_config = ConfigDict(from_attributes=True)

    label: str
    period_end: date
    revenue: Decimal | None
    revenue_growth_pct: Decimal | None  # vs the comparable prior period, not the prior quarter
    free_cash_flow: Decimal | None
    net_income: Decimal | None
    net_margin_pct: Decimal | None  # net_income / revenue for this period only
    cost_income_pct: Decimal | None  # banks only: operating expenses / total income, this period


class KeyMetricsOut(BaseModel):
    """A point-in-time valuation/quality snapshot -- as of whenever the provider last quoted
    it, never blended with the reported-period figures in FinancialsOut."""

    model_config = ConfigDict(from_attributes=True)

    pe_ratio: Decimal | None
    forward_pe_ratio: Decimal | None
    price_to_fcf: Decimal | None
    ev_to_ebitda: Decimal | None
    gross_margin_pct: Decimal | None
    operating_margin_pct: Decimal | None
    net_margin_pct: Decimal | None
    return_on_equity_pct: Decimal | None
    debt_to_equity: Decimal | None
    net_cash: Decimal | None  # in FinancialsOut.currency
    dividend_yield_pct: Decimal | None
    payout_ratio_pct: Decimal | None


class FinancialsOut(BaseModel):
    currency: str | None  # the filer's reporting currency; figures are never converted
    quarter: FinancialPeriodOut | None
    annual: list[FinancialPeriodOut]
    key_metrics: KeyMetricsOut | None


class MetricHistoryPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str  # "FY2025"
    value: Decimal


class PositionMetricOut(BaseModel):
    """One line of a position's analyst checklist. `value` and `text` both empty means Yahoo
    doesn't carry it: `source_hint` says where to look instead."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    unit: str  # pct | multiple | amount | number | text
    why: str | None  # why this metric matters for this holding
    value: Decimal | None
    text: str | None  # for a metric that is a list rather than a figure (top holdings)
    detail: str | None  # what the figure is, or why there is none
    history: list[MetricHistoryPointOut]  # oldest first
    source_hint: str | None


class PositionMetricsOut(BaseModel):
    lens: str | None  # "Growth company"; None when the position has no checklist
    currency: str | None  # for the "amount" metrics; never converted
    metrics: list[PositionMetricOut]
