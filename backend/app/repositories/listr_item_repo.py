from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.listr_item import ListrItem


def list_items(db: Session, include_archived: bool = False, category_id: int | None = None) -> list[ListrItem]:
    query = select(ListrItem).options(joinedload(ListrItem.category)).order_by(ListrItem.name)
    if not include_archived:
        query = query.where(ListrItem.is_archived.is_(False))
    if category_id is not None:
        query = query.where(ListrItem.category_id == category_id)
    return list(db.execute(query).unique().scalars().all())


def get_item(db: Session, item_id: int) -> ListrItem | None:
    return db.get(ListrItem, item_id)


def list_picnic_mapped(db: Session) -> list[ListrItem]:
    """Every catalog item linked to a Picnic product, archived ones included -- their price is
    still worth knowing if they come back."""
    query = select(ListrItem).where(ListrItem.picnic_product_id.is_not(None)).order_by(ListrItem.name)
    return list(db.execute(query).scalars().all())


def list_by_picnic_product_ids(db: Session, product_ids: list[str]) -> list[ListrItem]:
    if not product_ids:
        return []
    return list(db.execute(select(ListrItem).where(ListrItem.picnic_product_id.in_(product_ids))).scalars().all())


def get_by_name(db: Session, name: str) -> ListrItem | None:
    return db.execute(select(ListrItem).where(ListrItem.name == name)).scalar_one_or_none()


def list_inventory(db: Session) -> list[ListrItem]:
    """Every item currently tracked in the inventory (inventory_status is not null) -- not the
    whole catalog. An archived item drops out even if it still carries a status, same as it
    drops out of every other listr view by default."""
    query = (
        select(ListrItem)
        .options(joinedload(ListrItem.category))
        .where(ListrItem.inventory_status.is_not(None))
        .where(ListrItem.is_archived.is_(False))
        .order_by(ListrItem.name)
    )
    return list(db.execute(query).unique().scalars().all())


def create_item(db: Session, **fields) -> ListrItem:
    item = ListrItem(**fields)
    db.add(item)
    db.flush()
    return item


def update_item(db: Session, item: ListrItem, **fields) -> ListrItem:
    for key, value in fields.items():
        setattr(item, key, value)
    db.flush()
    return item
