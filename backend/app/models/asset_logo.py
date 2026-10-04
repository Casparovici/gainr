from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AssetLogo(Base):
    """Locally cached brand icon for an asset.

    The bytes are stored rather than a remote URL because the Home page renders one logo per
    holding: pointing those <img> tags at a third-party icon CDN would hand that host the
    full list of tickers in this portfolio on every page load. Fetched once from the
    company's own website instead — see logo_service.
    """

    __tablename__ = "asset_logos"

    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(64))
    image: Mapped[bytes] = mapped_column(LargeBinary)
    source_url: Mapped[str] = mapped_column(String(500))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    asset = relationship("Asset", back_populates="logo")
