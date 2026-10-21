"""The one place grocery-list writes have real logic beyond a plain insert/update/delete --
merging ingredient lines onto a list, clearing what's been bought, duplicating a list to reuse
as a template, and the three ways a batch lands on a list (from Voorraad, a recipe, or planned
days). See docs/adr/0005-listr-module.md.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.listr_list import ListrList
from app.models.listr_recipe import ListrRecipe
from app.repositories import listr_item_repo, listr_list_repo, listr_meal_plan_repo
from app.services.errors import InvalidRequest, NotFound


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
    # The next trip is usually to the same shop.
    source = listr_list_repo.get_list(db, list_id)
    if source is not None:
        new_list.store_id = source.store_id
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


def target_list(db: Session, list_id: int | None, new_list_name: str | None) -> ListrList:
    """The list a batch goes onto: an existing one by id, or a new one by name."""
    if list_id is None and not new_list_name:
        raise InvalidRequest("Provide list_id or new_list_name")
    if list_id is None:
        return listr_list_repo.create_list(db, name=new_list_name)
    found = listr_list_repo.get_list(db, list_id)
    if found is None:
        raise NotFound("List not found")
    return found


def add_items_to_list(db: Session, item_ids: list[int], list_id: int | None, new_list_name: str | None) -> ListrList:
    """Voorraad's "restock these": each product at quantity 1 of its own default unit -- there's no
    computed quantity anywhere in listr, the reader adjusts it on the list."""
    grocery_list = target_list(db, list_id, new_list_name)
    lines = []
    for item_id in item_ids:
        item = listr_item_repo.get_item(db, item_id)
        if item is None:
            raise NotFound(f"Item {item_id} not found")
        lines.append(IngredientLine(item.id, Decimal("1"), item.default_unit))
    add_ingredients_to_list(db, grocery_list.id, lines)
    return grocery_list


def add_recipe_to_list(
    db: Session, recipe: ListrRecipe, ingredient_ids: list[int], list_id: int | None, new_list_name: str | None
) -> ListrList:
    """The ingredients of `recipe` the reader ticked, each as the recipe states it."""
    grocery_list = target_list(db, list_id, new_list_name)
    by_id = {i.id: i for i in recipe.ingredients}
    lines = []
    for ingredient_id in ingredient_ids:
        ingredient = by_id.get(ingredient_id)
        if ingredient is None:
            raise NotFound(f"Ingredient {ingredient_id} not found on this recipe")
        lines.append(IngredientLine(ingredient.grocery_item_id, ingredient.quantity, ingredient.unit))
    add_ingredients_to_list(db, grocery_list.id, lines)
    return grocery_list


def add_planned_days_to_list(
    db: Session, dates: list[date], list_id: int | None, new_list_name: str | None
) -> ListrList:
    """Every ingredient of every planned day's recipe on one list, merged like any other add, so
    two recipes that both need onions give one summed line. Days without a recipe add nothing."""
    grocery_list = target_list(db, list_id, new_list_name)
    lines = []
    for day in dates:
        entry = listr_meal_plan_repo.get_by_date(db, day)
        if entry is None or entry.recipe is None:
            continue
        lines.extend(IngredientLine(i.grocery_item_id, i.quantity, i.unit) for i in entry.recipe.ingredients)
    add_ingredients_to_list(db, grocery_list.id, lines)
    return grocery_list
