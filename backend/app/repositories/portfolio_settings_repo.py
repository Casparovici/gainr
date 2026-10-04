from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portfolio_settings import PortfolioSettings


def get(db: Session, portfolio_id: int) -> PortfolioSettings | None:
    query = select(PortfolioSettings).where(PortfolioSettings.portfolio_id == portfolio_id)
    return db.execute(query).scalar_one_or_none()


def get_cash_target_weight_pct(db: Session, portfolio_id: int) -> Decimal | None:
    settings = get(db, portfolio_id)
    return settings.cash_target_weight_pct if settings else None


def set_cash_target_weight_pct(db: Session, portfolio_id: int, value: Decimal | None) -> PortfolioSettings:
    settings = get(db, portfolio_id)
    if settings is None:
        settings = PortfolioSettings(portfolio_id=portfolio_id)
        db.add(settings)
    settings.cash_target_weight_pct = value
    db.flush()
    return settings
