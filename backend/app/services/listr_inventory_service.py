"""Voorraad's one rule -- how a count and a minimum turn into in_stock/low/out -- in one place,
for the Voorraad endpoints and for a Picnic delivery restocking items alike. See
docs/adr/0015-listr-inventory.md.
"""

from sqlalchemy.orm import Session

from app.models.listr_item import ListrItem
from app.repositories import listr_item_repo


def compute_status(count: int, minimum: int) -> str:
    """0 left is always out -- there's nothing left to be "low" on. Otherwise: at or above the
    minimum is in_stock, below it is low. Minimum defaults to 0, which (count can't go negative)
    means "always in_stock until it hits zero" until the reader sets a real reorder point for
    that product. See docs/adr/0015-listr-inventory.md's fourth addendum: the earlier "1 or 0 is
    always out" floor overrode a minimum of 1 itself, permanently red-flagging fully-stocked
    single-unit items (the freezer items this was reported against)."""
    if count == 0:
        return "out"
    if count < minimum:
        return "low"
    return "in_stock"


def adjust_count(db: Session, item: ListrItem, delta: int) -> ListrItem:
    """Adds `delta` (negative to take away) to the tally, never below zero, and recomputes the
    status when the item is tracked."""
    new_count = max(0, item.inventory_count + delta)
    fields: dict = {"inventory_count": new_count}
    if item.inventory_status is not None:
        fields["inventory_status"] = compute_status(new_count, item.inventory_minimum)
    return listr_item_repo.update_item(db, item, **fields)


def adjust_minimum(db: Session, item: ListrItem, delta: int) -> ListrItem:
    new_minimum = max(0, item.inventory_minimum + delta)
    fields: dict = {"inventory_minimum": new_minimum}
    if item.inventory_status is not None:
        fields["inventory_status"] = compute_status(item.inventory_count, new_minimum)
    return listr_item_repo.update_item(db, item, **fields)
