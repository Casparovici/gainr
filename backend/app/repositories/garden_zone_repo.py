from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.garden_zone import GardenZone


def list_zones(db: Session, area_id: int) -> list[GardenZone]:
    query = select(GardenZone).where(GardenZone.area_id == area_id).order_by(GardenZone.sort_order, GardenZone.id)
    return list(db.execute(query).scalars().all())


def get_zone(db: Session, zone_id: int) -> GardenZone | None:
    return db.get(GardenZone, zone_id)


def create_zone(db: Session, **fields) -> GardenZone:
    zone = GardenZone(**fields)
    db.add(zone)
    db.flush()
    return zone


def update_zone(db: Session, zone: GardenZone, **fields) -> GardenZone:
    # Present key means "apply this", including an explicit None to clear -- callers pass
    # model_dump(exclude_unset=True). See gripr_transaction_repo.update_transaction.
    for key, value in fields.items():
        setattr(zone, key, value)
    db.flush()
    return zone


def delete_zone(db: Session, zone: GardenZone) -> None:
    db.delete(zone)
    db.flush()
