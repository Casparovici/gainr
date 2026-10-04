from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PortfolioAssetTarget(Base):
    """A holding's target allocation is a portfolio's own judgment, not the asset's -- the same
    ticker held in two portfolios can carry two different targets (or none). Replaces what used
    to be a single `Asset.target_weight_pct` column, which broke once an asset could belong to
    more than one portfolio. Writes go through target_weight_service, which enforces that every
    target weight in a portfolio (holdings + cash) never sums past 100. See docs/adr/0019."""

    __tablename__ = "portfolio_asset_targets"
    __table_args__ = (UniqueConstraint("portfolio_id", "asset_id", name="uq_portfolio_asset_target"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    target_weight_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
