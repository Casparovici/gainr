from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.asset import DltJudgment

# -- portfolios -----------------------------------------------------------------------------


class PortfolioCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class PortfolioUpdate(BaseModel):
    name: str | None = None
    is_archived: bool | None = None


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_archived: bool


# -- positions/summary/performance -----------------------------------------------------------


class PositionOut(BaseModel):
    asset_id: int
    ticker: str
    name: str
    asset_class: str
    quantity: Decimal
    avg_cost_eur: Decimal
    cost_basis_eur: Decimal
    current_price_native: Decimal | None
    price_date: date | None  # trading day the price is from (daily closes, refreshed once/day)
    native_currency: str
    market_value_eur: Decimal | None
    unrealized_pnl_eur: Decimal | None
    unrealized_pnl_pct: Decimal | None
    realized_pnl_eur: Decimal  # banked on earlier partial sells of this same position
    weight_pct: Decimal | None
    price_stale: bool
    # Null = no DLT coverage / not checked yet, distinct from an explicit "neutral" call --
    # the two used to render identically because this was always coalesced to NEUTRAL on the
    # wire; now that a rating can be cleared back to "no opinion" from the app (not just
    # scripts/update_dlt_ratings.py), that distinction has to survive the round trip, so the
    # frontend coalesces only where it renders the badge, not in the data itself.
    dlt_judgment: DltJudgment | None
    # Null = no target set for this holding (including the synthetic cash row). Distinct from
    # an explicit 0 — writes go through target_weight_service, which enforces that every
    # target (assets + cash) never sums past 100.
    target_weight_pct: Decimal | None
    # weight_pct - target_weight_pct: positive = overweight, negative = underweight. Null
    # whenever either side is null — there's nothing to drift from without a target, and no
    # weight to report while the position (or the whole portfolio) is unvalued.
    target_weight_diff_pct: Decimal | None
    # The euro amount that difference represents: market_value_eur minus what this holding
    # would be worth at its target weight of the current total portfolio value.
    target_weight_diff_eur: Decimal | None


class CashTargetWeightIn(BaseModel):
    target_weight_pct: Decimal | None


class ClosedPositionOut(BaseModel):
    asset_id: int
    ticker: str
    name: str
    asset_class: str
    total_bought: Decimal
    total_sold: Decimal
    realized_pnl_eur: Decimal
    first_buy_date: date | None
    last_sell_date: date | None


class SummaryOut(BaseModel):
    total_value_eur: Decimal
    cash_eur: Decimal
    # Same cash, split by which broker holds it -- see position_service.cash_balance_by_broker_eur.
    cash_by_broker_eur: dict[str, Decimal]
    holdings_value_eur: Decimal
    ytd_return_eur: Decimal
    ytd_return_pct: Decimal | None
    total_return_eur: Decimal
    total_return_pct: Decimal | None
    # Split of where the total return sits today. Unrealized is marked to the latest close on
    # open positions; realized is proceeds-minus-cost on everything already sold (dividends
    # and interest are cash income, not a gain, so they're in neither).
    unrealized_pnl_eur: Decimal
    unrealized_pnl_pct: Decimal | None
    realized_pnl_eur: Decimal
    total_invested_eur: Decimal
    as_of: date


class PerformancePoint(BaseModel):
    date: date
    value_eur: Decimal
    return_pct: Decimal | None = None  # time-weighted return since the start of the range


class BenchmarkPoint(BaseModel):
    date: date
    value: Decimal


class BenchmarkSeries(BaseModel):
    key: str
    label: str
    points: list[BenchmarkPoint]


class BenchmarkOut(BaseModel):
    key: str
    label: str


class PerformanceOut(BaseModel):
    range: str
    points: list[PerformancePoint]
    start_value_eur: Decimal | None
    end_value_eur: Decimal | None
    change_eur: Decimal | None
    change_pct: Decimal | None
    benchmarks: list[BenchmarkSeries] = []
