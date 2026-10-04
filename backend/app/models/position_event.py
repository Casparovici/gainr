import enum
from datetime import date as date_
from datetime import datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class PositionEventKind(str, enum.Enum):
    INVESTOR_DAY = "investor_day"
    CAPITAL_MARKETS_DAY = "capital_markets_day"
    AGM = "agm"
    PRODUCT_EVENT = "product_event"
    OTHER = "other"


class PositionEvent(Base):
    """A company milestone the user adds by hand -- an investor day, an AGM, a product launch.
    Yahoo only knows earnings and dividend dates, so everything else on a position's Calendar
    tab lives here. Per asset, not per portfolio, like journal notes: a date is about the
    company, wherever it's held. See docs/adr/0025-position-calendar.md."""

    __tablename__ = "position_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    date: Mapped[date_] = mapped_column(Date, index=True)
    kind: Mapped[PositionEventKind] = mapped_column(Enum(PositionEventKind))
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    asset = relationship("Asset")
