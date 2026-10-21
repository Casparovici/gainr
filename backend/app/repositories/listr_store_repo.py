from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.models.listr_category import ListrCategory
from app.models.listr_list import ListrList
from app.models.listr_store import ListrStore, ListrStoreCategory


def list_stores(db: Session, include_archived: bool = False) -> list[ListrStore]:
    query = select(ListrStore).options(selectinload(ListrStore.category_positions)).order_by(ListrStore.sort_order, ListrStore.name)
    if not include_archived:
        query = query.where(ListrStore.is_archived.is_(False))
    return list(db.execute(query).scalars().all())


def get_store(db: Session, store_id: int) -> ListrStore | None:
    return db.get(ListrStore, store_id)


def get_by_name(db: Session, name: str) -> ListrStore | None:
    return db.execute(select(ListrStore).where(ListrStore.name == name)).scalar_one_or_none()


def next_sort_order(db: Session) -> int:
    current_max = db.execute(select(func.max(ListrStore.sort_order))).scalar_one_or_none()
    return (current_max or 0) + 1


def create_store(db: Session, **fields) -> ListrStore:
    store = ListrStore(**fields)
    db.add(store)
    db.flush()
    return store


def update_store(db: Session, store: ListrStore, **fields) -> ListrStore:
    for key, value in fields.items():
        setattr(store, key, value)
    db.flush()
    return store


def delete_store(db: Session, store: ListrStore) -> None:
    # The app doesn't turn on SQLite's foreign keys, so the lists pointing at it are let go here
    # rather than left to ON DELETE SET NULL; its category rows go with it (model cascade).
    db.execute(update(ListrList).where(ListrList.store_id == store.id).values(store_id=None))
    db.delete(store)
    db.flush()


def set_positions(db: Session, store: ListrStore, category_ids: list[int]) -> None:
    """Replaces the store's order with `category_ids`, first to last."""
    store.category_positions.clear()
    db.flush()
    for position, category_id in enumerate(category_ids):
        store.category_positions.append(ListrStoreCategory(category_id=category_id, position=position))
    db.flush()


def all_categories_in_global_order(db: Session) -> list[ListrCategory]:
    return list(db.execute(select(ListrCategory).order_by(ListrCategory.sort_order, ListrCategory.name)).scalars().all())
