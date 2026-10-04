from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portfolio_asset_target import PortfolioAssetTarget


def targets_by_asset_id(db: Session, portfolio_id: int) -> dict[int, Decimal]:
    """Every target this portfolio has set, keyed by asset id -- one query for a whole
    positions list rather than one lookup per position, mirroring asset_repo's
    dlt_judgments_by_asset_id shape."""
    query = select(PortfolioAssetTarget.asset_id, PortfolioAssetTarget.target_weight_pct).where(
        PortfolioAssetTarget.portfolio_id == portfolio_id
    )
    return {asset_id: weight for asset_id, weight in db.execute(query).all()}


def get(db: Session, portfolio_id: int, asset_id: int) -> PortfolioAssetTarget | None:
    query = select(PortfolioAssetTarget).where(
        PortfolioAssetTarget.portfolio_id == portfolio_id, PortfolioAssetTarget.asset_id == asset_id
    )
    return db.execute(query).scalar_one_or_none()


def set_target(db: Session, portfolio_id: int, asset_id: int, value: Decimal | None) -> None:
    existing = get(db, portfolio_id, asset_id)
    if value is None:
        if existing is not None:
            db.delete(existing)
            db.flush()
        return
    if existing is not None:
        existing.target_weight_pct = value
    else:
        db.add(PortfolioAssetTarget(portfolio_id=portfolio_id, asset_id=asset_id, target_weight_pct=value))
    db.flush()


def sum_targets(db: Session, portfolio_id: int, exclude_asset_id: int | None) -> Decimal:
    """Sum of every target this portfolio has set, excluding one asset's own current value so a
    caller raising that asset's target doesn't double-count it against itself."""
    rows = db.execute(
        select(PortfolioAssetTarget.asset_id, PortfolioAssetTarget.target_weight_pct).where(
            PortfolioAssetTarget.portfolio_id == portfolio_id
        )
    ).all()
    return sum((w for asset_id, w in rows if asset_id != exclude_asset_id), Decimal(0))
