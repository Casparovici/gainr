from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PortfolioSettings(Base):
    """One row per portfolio -- cash has no Asset row (it's a synthetic position, see
    positions.py's CASH_ASSET_ID), so its target weight can't live on
    PortfolioAssetTarget/`assets.target_weight_pct` like every other holding's. Writes go
    through target_weight_service. See docs/adr/0019 for why this stopped being a singleton."""

    __tablename__ = "portfolio_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), unique=True, index=True)
    # Null = no target set. Writes go through target_weight_service.
    cash_target_weight_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
