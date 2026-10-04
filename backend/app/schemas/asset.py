import re
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

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
