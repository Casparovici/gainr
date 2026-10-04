from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.price_history import PriceHistory


def get_price_on_or_before(db: Session, asset_id: int, target_date: date) -> PriceHistory | None:
    query = (
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset_id, PriceHistory.date <= target_date)
        .order_by(PriceHistory.date.desc())
        .limit(1)
    )
    return db.execute(query).scalar_one_or_none()


def get_latest_price(db: Session, asset_id: int) -> PriceHistory | None:
    query = select(PriceHistory).where(PriceHistory.asset_id == asset_id).order_by(PriceHistory.date.desc()).limit(1)
    return db.execute(query).scalar_one_or_none()


def get_history(db: Session, asset_id: int, start: date, end: date) -> list[PriceHistory]:
    query = (
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset_id, PriceHistory.date >= start, PriceHistory.date <= end)
        .order_by(PriceHistory.date)
    )
    return list(db.execute(query).scalars().all())


def upsert_prices(db: Session, asset_id: int, prices: dict[date, float]) -> None:
    if not prices:
        return
    existing_dates = {
        row.date
        for row in db.execute(
            select(PriceHistory.date).where(
                PriceHistory.asset_id == asset_id, PriceHistory.date.in_(prices.keys())
            )
        )
    }
    for d, close in prices.items():
        if d in existing_dates:
            continue
        db.add(PriceHistory(asset_id=asset_id, date=d, close_price=close))
    db.flush()
