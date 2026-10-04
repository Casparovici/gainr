import enum
from datetime import date as date_
from decimal import Decimal

from sqlalchemy import Date, Enum, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class DltJudgment(str, enum.Enum):
    """A third party's (De Lange Termijn) buy/hold/avoid call on a holding, set by hand from
    a screenshot of their dashboard — there's no API or export, so this is refreshed
    occasionally via `scripts/update_dlt_ratings.py`, not fetched live."""

    ATTRACTIVE = "attractive"
    NEUTRAL = "neutral"
    CRITICAL = "critical"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    asset_class: Mapped[str] = mapped_column(String(16), default="equity")
    native_currency: Mapped[str] = mapped_column(String(8), default="EUR")
    # Multiplier applied to the raw provider price before it's treated as `native_currency`
    # units. Almost always 1 — exists because Yahoo quotes London-listed stocks in pence
    # (currency code "GBp") rather than pounds, so those need *0.01 to become real GBP.
    price_scale: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=1)
    # Symbol used to query the price provider (e.g. yfinance). Nullable/editable because
    # the auto-mapping heuristic applied on import can't reliably guess every exchange-listed
    # ticker or crypto pair — the asset editor lets the user correct it.
    yahoo_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # The instrument's ISIN, which is how a broker's own records (Trading 212's fills and
    # dividends) find the asset they're about -- tickers differ per broker ("TDIVa_EQ" there,
    # "AMS:TDIV" here). Not unique: two listings of one fund would share it, and a broker sync
    # holds back an ISIN that matches more than one asset rather than guess.
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Extra places to pull news from for this position, as a JSON list of source keys
    # ("industry:aerospace-defense", "sector:utilities", "ticker:GC=F") -- for holdings whose own
    # ticker has little or no news of its own (an ETF, a gold tracker). See
    # app/services/news_sources.py and docs/adr/0026-news-sources-per-position.md.
    news_sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Last calendar date we asked the provider for a fresh price — gates fetching to at most
    # once/day regardless of how many times positions are viewed that day.
    price_checked_at: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    # Same idea for the brand logo, which is resolved lazily and often simply doesn't exist
    # (crypto pairs, delisted tickers). Without this, every asset with no findable icon would
    # re-trigger a provider lookup on every Home page render.
    logo_checked_at: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    # Null means "no DLT coverage / not checked yet" — distinct from an actual "neutral" call
    # from them, even though the UI shows both the same way (see positions.py).
    dlt_judgment: Mapped[DltJudgment | None] = mapped_column(Enum(DltJudgment), nullable=True)

    transactions = relationship("Transaction", back_populates="asset")
    price_history = relationship("PriceHistory", back_populates="asset")
    logo = relationship("AssetLogo", back_populates="asset", uselist=False)
    snapshots = relationship("AssetSnapshot", back_populates="asset")
    position_notes = relationship("PositionNote", secondary="position_note_assets", back_populates="assets")
