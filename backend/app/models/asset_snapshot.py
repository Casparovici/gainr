from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AssetSnapshot(Base):
    """Cached response from a slow external fundamentals lookup, keyed by asset and kind.

    News and financial statements are scrapes that take seconds per asset and are asked for
    every time a position card is opened, so they get the same treatment prices do: fetch
    once, serve from here until the payload ages out. Stored as the JSON the API returns
    rather than as normalised columns — it's a cache of someone else's shape, and modelling
    every line item would mean a migration each time the provider adds a row.
    """

    __tablename__ = "asset_snapshots"

    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)  # "news" | "financials"
    payload: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    asset = relationship("Asset", back_populates="snapshots")
