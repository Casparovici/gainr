"""The product catalog's writes that are more than a field update: adding a product by name
without duplicating it, linking it to a Picnic product, and tracking it in Voorraad. Also how an
ingredient's name finds its product, for recipes that arrive from elsewhere (Mealie, briefr)."""

import re
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.listr_item import ListrItem
from app.repositories import listr_category_repo, listr_item_repo
from app.services import listr_inventory_service
from app.services.errors import NotFound


_DOUBLE_VOWEL_CLOSED = re.compile(r"^(.*)([aeou])\2([^aeiou])$")


def dutch_plurals(word: str) -> set[str]:
    """The plural spellings a Dutch singular food name plausibly has in the catalog -- Mealie
    names foods in the singular ("tomaat", "ui"), the catalog was seeded as shopping items
    ("Tomaten", "Uien"). Deliberately a handful of regular patterns plus "ei", not a lexicon:
    a miss just means no match, never a wrong one."""
    forms = {word + "en", word + "s", word + "'s", word + "n", word + "eren"}
    if match := _DOUBLE_VOWEL_CLOSED.match(word):  # tomaat -> tomaten, boon -> bonen
        forms.add(f"{match[1]}{match[2]}{match[3]}en")
    if len(word) > 2 and word[-1] not in "aeiou" and word[-2] in "aeiou" and word[-3] not in "aeiou":
        forms.add(word + word[-1] + "en")  # kip -> kippen
    return forms


def match_product(name: str, by_name: dict[str, ListrItem]) -> ListrItem | None:
    """The product an ingredient's name means, when that's certain: the same name ignoring case,
    or its plural ("tomaat" -> Tomaten). `by_name` is the catalog keyed by casefolded name. Nothing
    looser than that, since the caller saves the match without asking."""
    words = name.casefold().split()
    if not words:
        return None
    if (item := by_name.get(" ".join(words))) is not None:
        return item
    for plural in sorted(dutch_plurals(words[-1])):
        if (item := by_name.get(" ".join([*words[:-1], plural]))) is not None:
            return item
    return None


def get_or_create_item(db: Session, *, name: str, category_id: int, default_unit: str) -> ListrItem:
    """A product that already exists by name is returned as it is rather than duplicated, the same
    as adding an asset in gainr."""
    if listr_category_repo.get_category(db, category_id) is None:
        raise NotFound("Category not found")
    existing = listr_item_repo.get_by_name(db, name)
    if existing is not None:
        return existing
    return listr_item_repo.create_item(db, name=name, category_id=category_id, default_unit=default_unit)


def set_picnic_mapping(
    db: Session,
    item: ListrItem,
    *,
    product_id: str,
    product_name: str,
    display_price_cents: int | None,
    unit_quantity: str | None,
    image_id: str | None,
    now: datetime,
) -> ListrItem:
    """Which Picnic product this item means (ADR 0011). The picked search result's own price shows
    straight away; a pick without one clears the price rather than keeping the previous product's."""
    has_price = display_price_cents is not None
    return listr_item_repo.update_item(
        db,
        item,
        picnic_product_id=product_id,
        picnic_product_name=product_name,
        picnic_price=Decimal(display_price_cents) / 100 if has_price else None,
        picnic_unit_quantity=unit_quantity,
        picnic_price_at=now if has_price else None,
        picnic_image_id=image_id,
    )


def set_tracked(db: Session, item: ListrItem, tracked: bool) -> ListrItem:
    """Tracking computes the status from the count and minimum (ADR 0015); untracking clears the
    status but keeps both, so tracking again picks up where it left off."""
    status = listr_inventory_service.compute_status(item.inventory_count, item.inventory_minimum) if tracked else None
    return listr_item_repo.update_item(db, item, inventory_status=status)
