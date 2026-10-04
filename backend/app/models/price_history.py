from datetime import date as date_, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (UniqueConstraint("asset_id", "date", name="uq_price_history_asset_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    date: Mapped[date_] = mapped_column(Date, index=True)
    close_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))  # native currency
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    asset = relationship("Asset", back_populates="price_history")
