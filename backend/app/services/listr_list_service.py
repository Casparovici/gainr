"""The one place grocery-list writes have real logic beyond a plain insert/update/delete --
merging ingredient lines onto a list, clearing what's been bought, and duplicating a list to
reuse as a template. See docs/adr/0005-listr-module.md.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.listr_list import ListrList
from app.repositories import listr_list_repo


@dataclass(frozen=True)
class IngredientLine:
    grocery_item_id: int
    quantity: Decimal
    unit: str


def add_ingredients_to_list(db: Session, list_id: int, lines: list[IngredientLine]) -> None:
    """Adds each line to the list, merging onto an existing line for the same grocery item
    *and* unit (summing quantities) rather than creating a duplicate. A different unit for the
    same item is deliberately kept as its own line -- never guessing a conversion between
    e.g. "stuks" and "gram"."""
    for line in lines:
        existing = listr_list_repo.get_item_for_grocery_item(db, list_id, line.grocery_item_id, line.unit)
        if existing is not None:
            listr_list_repo.update_list_item(db, existing, quantity=existing.quantity + line.quantity)
        else:
            sort_order = listr_list_repo.next_sort_order(db, list_id)
            listr_list_repo.create_list_item(
                db,
                list_id=list_id,
                grocery_item_id=line.grocery_item_id,
                quantity=line.quantity,
                unit=line.unit,
                sort_order=sort_order,
            )


def clear_checked(db: Session, list_id: int) -> int:
    """Hard-deletes every checked line -- a bought-and-crossed-off item has no lasting record
    value the way a financial transaction does, so nothing here is archived."""
    return listr_list_repo.delete_checked_items(db, list_id)


def duplicate_list(db: Session, list_id: int, new_name: str) -> ListrList:
    """Copies every line on `list_id` into a brand-new list, unchecked -- the "reusable
    template" use case named/saved lists exist for (start next week's list from this week's)."""
    source_items = listr_list_repo.list_items(db, list_id)
    new_list = listr_list_repo.create_list(db, name=new_name)
    for item in source_items:
        listr_list_repo.create_list_item(
            db,
            list_id=new_list.id,
            grocery_item_id=item.grocery_item_id,
            quantity=item.quantity,
            unit=item.unit,
            is_checked=False,
            sort_order=item.sort_order,
        )
    return new_list
