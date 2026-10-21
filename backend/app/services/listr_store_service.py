"""listr: supermarkets and the order their aisles come in (docs/adr/0052-listr-store-order.md).

A list set to a store shows its categories in that store's order; a list with no store follows the
global category order (`ListrCategory.sort_order`, then name). Nothing about a list's lines changes:
the order is only how the lines are grouped when shown."""

from sqlalchemy.orm import Session

from app.models.listr_list import ListrList
from app.models.listr_store import ListrStore
from app.repositories import listr_category_repo, listr_store_repo
from app.services.errors import Conflict, InvalidRequest, NotFound


def _clean_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise InvalidRequest("A store needs a name")
    return name


def create_store(db: Session, name: str, copy_order_from_id: int | None = None) -> ListrStore:
    """A new store. It starts with the order of `copy_order_from_id` when given (two shops of one
    chain share a layout), and otherwise follows the global order until it's arranged."""
    name = _clean_name(name)
    if listr_store_repo.get_by_name(db, name) is not None:
        raise Conflict(f"There is already a store called {name}")
    source = None
    if copy_order_from_id is not None:
        source = listr_store_repo.get_store(db, copy_order_from_id)
        if source is None:
            raise NotFound("The store to copy the order from doesn't exist")
    store = listr_store_repo.create_store(db, name=name, sort_order=listr_store_repo.next_sort_order(db))
    if source is not None:
        listr_store_repo.set_positions(db, store, [row.category_id for row in source.category_positions])
    return store


def rename_store(db: Session, store: ListrStore, name: str) -> ListrStore:
    name = _clean_name(name)
    other = listr_store_repo.get_by_name(db, name)
    if other is not None and other.id != store.id:
        raise Conflict(f"There is already a store called {name}")
    return listr_store_repo.update_store(db, store, name=name)


def set_order(db: Session, store: ListrStore, category_ids: list[int]) -> ListrStore:
    """The store's walk, first aisle to last. A category left out comes after these, in the global
    order; an unknown one is refused rather than quietly dropped."""
    ordered = list(dict.fromkeys(category_ids))
    known = {c.id for c in listr_store_repo.all_categories_in_global_order(db)}
    unknown = [i for i in ordered if i not in known]
    if unknown:
        raise InvalidRequest(f"Unknown categories: {unknown}")
    listr_store_repo.set_positions(db, store, ordered)
    return store


def assign_store(db: Session, grocery_list: ListrList, store_id: int | None) -> None:
    """Sets the list's store (None: back to the global order)."""
    if store_id is not None and listr_store_repo.get_store(db, store_id) is None:
        raise NotFound("Store not found")
    grocery_list.store_id = store_id
    db.flush()


def category_order(db: Session, store_id: int | None) -> list[int]:
    """Every category id, in the order a list for this store shows them: the store's own aisles
    first, then the rest by the global order. The whole set, archived categories included, so a line
    whose category was archived afterwards still has a place."""
    everything = [c.id for c in listr_category_repo.list_categories(db, include_archived=True)]
    store = listr_store_repo.get_store(db, store_id) if store_id is not None else None
    if store is None:
        return everything
    own = [row.category_id for row in store.category_positions if row.category_id in set(everything)]
    return own + [i for i in everything if i not in set(own)]
