import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from app.models.asset import DltJudgment

_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def _isin(value: str | None) -> str | None:
    """Upper-cased and checked for an ISIN's shape (two-letter country, nine characters, check
    digit); blank clears it."""
    if value is None:
        return None
    value = value.strip().upper()
    if not value:
        return None
    if not _ISIN.match(value):
        raise ValueError("isn't an ISIN (like NL0011683594)")
    return value


class AssetCreate(BaseModel):
    ticker: str
    name: str
    asset_class: str = "equity"
    native_currency: str = "EUR"
    # Defaults to `ticker` when omitted — most tickers are their own Yahoo symbol.
    yahoo_symbol: str | None = None
    # Set when the asset is created for a broker's instrument (Trading 212 links by ISIN).
    isin: str | None = None

    @field_validator("isin")
    @classmethod
    def _valid_isin(cls, value: str | None) -> str | None:
        return _isin(value)

    @field_validator("ticker", "name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: str
    asset_class: str
    native_currency: str
    yahoo_symbol: str | None
    isin: str | None = None
    notes: str | None
    # Null = no DLT coverage / not checked yet, distinct from an explicit "neutral" call. See
    # the matching comment on PositionOut.dlt_judgment.
    dlt_judgment: DltJudgment | None = None


class AssetUpdate(BaseModel):
    name: str | None = None
    asset_class: str | None = None
    native_currency: str | None = None
    yahoo_symbol: str | None = None
    # How a broker's own records (Trading 212's fills and dividends) find this asset.
    isin: str | None = None
    notes: str | None = None
    # Normally refreshed by hand from a screenshot (scripts/update_dlt_ratings.py) since DLT has
    # no API -- this field lets the same value be corrected/cleared from the app itself instead.
    dlt_judgment: DltJudgment | None = None

    @field_validator("isin")
    @classmethod
    def _valid_isin(cls, value: str | None) -> str | None:
        return _isin(value)


class AssetTargetWeightIn(BaseModel):
    # A target is a portfolio's own allocation judgment, not the asset's -- see docs/adr/0019.
    # Writes go through target_weight_service, which enforces the 100% cap.
    portfolio_id: int
    target_weight_pct: Decimal | None


class SymbolMatchOut(BaseModel):
    symbol: str
    name: str
    exchange: str
    quote_type: str


class SymbolLookupOut(BaseModel):
    query: str
    # The query is itself a listing the provider knows -- not necessarily the one meant (plain
    # "TDIV" is an American fund; the VanEck one is TDIV.AS), which is why every match is shown.
    exact: bool
    matches: list[SymbolMatchOut]


class PricePointOut(BaseModel):
    # An ISO date for a daily close, an ISO moment (UTC, "...Z") for an intraday bar.
    time: str
    price: Decimal


class PriceChartOut(BaseModel):
    """One position's price over a range, in the currency it trades in (docs/adr/0053)."""

    range: Literal["1D", "1W", "1M", "YTD", "3Y"]
    currency: str
    interval: Literal["intraday", "daily"]
    points: list[PricePointOut]
    # What the change is measured from: yesterday's close for 1D, the first close of the range.
    start_price: Decimal | None
    end_price: Decimal | None
    change: Decimal | None
    change_pct: Decimal | None
    # 1D was asked for but the provider had no intraday bars: the points are the last week's closes.
    is_fallback: bool = False
    # When the last point was traded (UTC), for a live or intraday price; null for a close.
    as_of: datetime | None = None

    # Naive UTC on the way in; stamped on the way out, so the browser doesn't read it as local time.
    @field_serializer("as_of")
    def _as_utc(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()
