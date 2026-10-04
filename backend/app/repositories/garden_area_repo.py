from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.garden_area import GardenArea
from app.models.garden_plant import GardenPlant


def list_areas(db: Session) -> list[tuple[GardenArea, int]]:
    """Areas with their (non-archived) plant count, for the Areas tile grid."""
    query = (
        select(GardenArea, func.count(GardenPlant.id))
        .outerjoin(GardenPlant, (GardenPlant.area_id == GardenArea.id) & (GardenPlant.is_archived.is_(False)))
        .group_by(GardenArea.id)
        .order_by(GardenArea.sort_order, GardenArea.name)
    )
    return [(area, count) for area, count in db.execute(query).all()]


def get_area(db: Session, area_id: int) -> GardenArea | None:
    return db.get(GardenArea, area_id)


def next_sort_order(db: Session) -> int:
    current_max = db.execute(select(func.max(GardenArea.sort_order))).scalar_one_or_none()
    return (current_max or 0) + 1


def create_area(db: Session, **fields) -> GardenArea:
    area = GardenArea(sort_order=next_sort_order(db), **fields)
    db.add(area)
    db.flush()
    return area


def update_area(db: Session, area: GardenArea, **fields) -> GardenArea:
    # Present key means "apply this", including an explicit None to clear -- callers pass
    # model_dump(exclude_unset=True). See gripr_transaction_repo.update_transaction.
    for key, value in fields.items():
        setattr(area, key, value)
    db.flush()
    return area


def delete_area(db: Session, area: GardenArea) -> None:
    db.delete(area)
    db.flush()


def reorder(db: Session, area_ids: list[int]) -> None:
    for position, area_id in enumerate(area_ids):
        area = db.get(GardenArea, area_id)
        if area is not None:
            area.sort_order = position
    db.flush()
