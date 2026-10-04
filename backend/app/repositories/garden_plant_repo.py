from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.garden_plant import GardenPlant


def list_plants(db: Session, area_id: int | None = None, include_archived: bool = False) -> list[GardenPlant]:
    query = select(GardenPlant)
    if area_id is not None:
        query = query.where(GardenPlant.area_id == area_id)
    if not include_archived:
        query = query.where(GardenPlant.is_archived.is_(False))
    return list(db.execute(query.order_by(GardenPlant.name)).scalars().all())


def get_plant(db: Session, plant_id: int) -> GardenPlant | None:
    return db.get(GardenPlant, plant_id)


def create_plant(db: Session, **fields) -> GardenPlant:
    plant = GardenPlant(**fields)
    db.add(plant)
    db.flush()
    return plant


def update_plant(db: Session, plant: GardenPlant, **fields) -> GardenPlant:
    # Present key means "apply this", including an explicit None -- clearing species/notes or
    # unplacing a marker (x/y) from the detail panel otherwise silently no-opped. Callers pass
    # model_dump(exclude_unset=True). See gripr_transaction_repo.update_transaction.
    for key, value in fields.items():
        setattr(plant, key, value)
    db.flush()
    return plant


def delete_plant(db: Session, plant: GardenPlant) -> None:
    db.delete(plant)
    db.flush()
