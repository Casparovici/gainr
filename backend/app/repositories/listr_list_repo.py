from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.listr_item import ListrItem
from app.models.listr_list import ListrList, ListrListItem


def list_lists(db: Session, include_archived: bool = False) -> list[ListrList]:
    query = select(ListrList).order_by(ListrList.updated_at.desc())
    if not include_archived:
        query = query.where(ListrList.is_archived.is_(False))
    return list(db.execute(query).scalars().all())


def get_list(db: Session, list_id: int) -> ListrList | None:
    return db.get(ListrList, list_id)


def counts_by_list(db: Session) -> dict[int, tuple[int, int]]:
    """(item_count, checked_count) per list id -- one query for the whole Lijsten overview
    instead of one lookup per list."""
    rows = db.execute(
        select(ListrListItem.list_id, ListrListItem.is_checked, func.count())
        .group_by(ListrListItem.list_id, ListrListItem.is_checked)
    ).all()
    counts: dict[int, tuple[int, int]] = {}
    for list_id, is_checked, n in rows:
        total, checked = counts.get(list_id, (0, 0))
        total += n
        checked += n if is_checked else 0
        counts[list_id] = (total, checked)
    return counts


def create_list(db: Session, **fields) -> ListrList:
    grocery_list = ListrList(**fields)
    db.add(grocery_list)
    db.flush()
    return grocery_list


def update_list(db: Session, grocery_list: ListrList, **fields) -> ListrList:
    for key, value in fields.items():
        setattr(grocery_list, key, value)
    db.flush()
    return grocery_list


# -- list items ---------------------------------------------------------------------------


def list_items(db: Session, list_id: int) -> list[ListrListItem]:
    query = (
        select(ListrListItem)
        .options(joinedload(ListrListItem.grocery_item).joinedload(ListrItem.category))
        .where(ListrListItem.list_id == list_id)
        .order_by(ListrListItem.sort_order, ListrListItem.id)
    )
    return list(db.execute(query).unique().scalars().all())


def get_item_for_grocery_item(db: Session, list_id: int, grocery_item_id: int, unit: str) -> ListrListItem | None:
    """The existing line for this grocery item *and* unit on this list, if any -- the merge
    key for add_ingredients_to_list. A different unit for the same item is a different line,
    never silently combined."""
    query = select(ListrListItem).where(
        ListrListItem.list_id == list_id,
        ListrListItem.grocery_item_id == grocery_item_id,
        ListrListItem.unit == unit,
    )
    return db.execute(query).scalar_one_or_none()


def get_list_item(db: Session, item_id: int) -> ListrListItem | None:
    return db.get(ListrListItem, item_id)


def next_sort_order(db: Session, list_id: int) -> int:
    current_max = db.execute(
        select(func.max(ListrListItem.sort_order)).where(ListrListItem.list_id == list_id)
    ).scalar_one_or_none()
    return (current_max or 0) + 1


def create_list_item(db: Session, **fields) -> ListrListItem:
    item = ListrListItem(**fields)
    db.add(item)
    db.flush()
    return item


def update_list_item(db: Session, item: ListrListItem, **fields) -> ListrListItem:
    for key, value in fields.items():
        setattr(item, key, value)
    db.flush()
    return item


def delete_list(db: Session, grocery_list: ListrList) -> None:
    db.delete(grocery_list)  # its lines go with it (model relationship)
    db.flush()


def delete_list_item(db: Session, item: ListrListItem) -> None:
    db.delete(item)
    db.flush()


def delete_checked_items(db: Session, list_id: int) -> int:
    items = db.execute(
        select(ListrListItem).where(ListrListItem.list_id == list_id, ListrListItem.is_checked.is_(True))
    ).scalars().all()
    for item in items:
        db.delete(item)
    db.flush()
    return len(items)
