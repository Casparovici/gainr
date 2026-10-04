from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.picnic_sync import PicnicSyncedDelivery, PicnicSyncSettings

SETTINGS_ID = 1  # single row, like picnic_session


def get_settings(db: Session) -> PicnicSyncSettings:
    """The settings row, created (switched off) on first use."""
    settings = db.get(PicnicSyncSettings, SETTINGS_ID)
    if settings is None:
        settings = PicnicSyncSettings(id=SETTINGS_ID, enabled=False)
        db.add(settings)
        db.flush()
    return settings


def update_settings(db: Session, **fields) -> PicnicSyncSettings:
    settings = get_settings(db)
    for key, value in fields.items():
        setattr(settings, key, value)
    db.flush()
    return settings


def synced_by_id(db: Session, delivery_ids: list[str]) -> dict[str, PicnicSyncedDelivery]:
    if not delivery_ids:
        return {}
    query = select(PicnicSyncedDelivery).where(PicnicSyncedDelivery.delivery_id.in_(delivery_ids))
    return {row.delivery_id: row for row in db.execute(query).scalars().all()}


def mark_synced(
    db: Session, delivery_id: str, delivered_on: date, *, orders_booked: int, orders_matched: int, items_restocked: int
) -> PicnicSyncedDelivery:
    row = PicnicSyncedDelivery(
        delivery_id=delivery_id,
        delivered_on=delivered_on,
        synced_at=datetime.now(),
        orders_booked=orders_booked,
        orders_matched=orders_matched,
        items_restocked=items_restocked,
    )
    db.add(row)
    db.flush()
    return row
