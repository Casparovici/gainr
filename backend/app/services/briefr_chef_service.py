"""briefr: planning the home chef's suggestions in listr (docs/adr/0054-briefr-home-chef.md).

The home chef is a cloud agent that suggests five recipes a week, each written out in its report
(ingredients, steps, the page it's from), since the server never fetches a recipe page itself.
Planning a suggestion makes it a listr recipe, once: the recipe keeps the page as its
`source_url`, so planning the same suggestion again, or the same page from a later week, reuses
it with whatever the reader changed in it. Then the recipe goes on the chosen day of the
weekplanner. An ingredient becomes a recipe line only when its name certainly means a catalog
product; the rest are listed in the recipe's notes, to add by hand."""

from datetime import date as date_
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.briefr_report import BriefrReportItem
from app.models.listr_meal_plan import ListrMealPlan
from app.models.listr_recipe import ListrRecipe
from app.repositories import listr_item_repo, listr_meal_plan_repo, listr_recipe_repo
from app.schemas.briefr import ReportFileIngredient, ReportFileRecipe
from app.services import listr_meal_plan_service
from app.services.briefr_report_service import RecipeStates, item_recipe
from app.services.errors import Conflict, InvalidRequest
from app.services.listr_catalog_service import match_product

TITLE_MAX = 200


def _quantity(value: Decimal) -> str:
    """3.000 -> "3", 0.500 -> "0,5": the way a Dutch recipe writes it."""
    text = format(value.normalize(), "f")
    return text.replace(".", ",")


def _line(ingredient: ReportFileIngredient) -> str:
    """"2 el sojasaus (licht)", as the ingredient reads in a recipe."""
    parts = []
    if ingredient.quantity is not None:
        parts.append(_quantity(ingredient.quantity))
    if ingredient.unit:
        parts.append(ingredient.unit)
    parts.append(ingredient.name)
    text = " ".join(parts)
    return f"{text} ({ingredient.note})" if ingredient.note else text


def _instructions(recipe: ReportFileRecipe) -> str:
    return "\n".join(f"{n}. {step}" for n, step in enumerate(recipe.steps, start=1))


def _notes(item: BriefrReportItem, recipe: ReportFileRecipe, unmatched: list[ReportFileIngredient],
           with_notes: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    if item.detail:
        parts.append(item.detail)
    if recipe.minutes:
        parts.append(f"Bereidingstijd: {recipe.minutes} minuten")
    if with_notes:
        parts.append("**Bij de ingrediënten**\n" + "\n".join(f"- {name}: {note}" for name, note in with_notes))
    if unmatched:
        parts.append("**Ingrediënten zonder product**\n" + "\n".join(f"- {_line(i)}" for i in unmatched))
    parts.append(f"Voorgesteld door de home chef in briefr. Bron: {recipe.url}")
    return "\n\n".join(parts)


def _create_recipe(db: Session, item: BriefrReportItem, recipe: ReportFileRecipe) -> ListrRecipe:
    by_name = {product.name.casefold(): product for product in listr_item_repo.list_items(db)}
    lines = []
    unmatched: list[ReportFileIngredient] = []
    with_notes: list[tuple[str, str]] = []
    for ingredient in recipe.ingredients:
        product = match_product(ingredient.name, by_name)
        if product is None:
            unmatched.append(ingredient)
            continue
        lines.append((product, ingredient))
        if ingredient.note:
            with_notes.append((product.name, ingredient.note))

    title = item.headline if len(item.headline) <= TITLE_MAX else item.headline[: TITLE_MAX - 1].rstrip() + "…"
    target = listr_recipe_repo.create_recipe(
        db,
        title=title,
        servings=recipe.servings,
        instructions=_instructions(recipe),
        notes=_notes(item, recipe, unmatched, with_notes),
        source_url=recipe.url,
    )
    for sort_order, (product, ingredient) in enumerate(lines):
        listr_recipe_repo.add_ingredient(
            db,
            recipe_id=target.id,
            grocery_item_id=product.id,
            quantity=ingredient.quantity if ingredient.quantity else Decimal("1"),
            unit=(ingredient.unit or product.default_unit)[:32],
            sort_order=sort_order,
        )
    db.flush()
    db.expire(target, ["ingredients"])
    return target


def plan_suggestion(db: Session, item: BriefrReportItem, day: date_, *, replace: bool) -> ListrMealPlan:
    """Puts a suggested recipe on `day` in the weekplanner, as a listr recipe made from the
    suggestion the first time (see the module docstring). A day that already has something
    planned is a Conflict unless `replace`; planning a day that already has this recipe is
    a no-op."""
    recipe = item_recipe(item)
    if recipe is None:
        raise InvalidRequest("This finding isn't a recipe suggestion")
    existing_day = listr_meal_plan_repo.get_by_date(db, day)
    target = listr_recipe_repo.get_by_source_urls(db, [recipe.url]).get(recipe.url)
    if existing_day is not None and target is not None and existing_day.recipe_id == target.id:
        return existing_day
    if existing_day is not None and not replace:
        raise Conflict("Something is already planned on that day")
    if target is None:
        target = _create_recipe(db, item, recipe)
    entry = listr_meal_plan_service.set_day(db, day, recipe_id=target.id, leftover_id=None, is_cooked=False, notes=None)
    db.expire(entry, ["recipe"])  # a replaced day's row still has its old recipe loaded
    return entry


def recipe_states(db: Session, items: list[BriefrReportItem], since: date_) -> RecipeStates:
    """For each suggestion among `items`: the listr recipe its page became, if any, and the days
    that recipe is planned on from `since`."""
    urls = {item.id: recipe.url for item in items if (recipe := item_recipe(item)) is not None}
    recipes = listr_recipe_repo.get_by_source_urls(db, sorted(set(urls.values())))
    dates = listr_meal_plan_repo.dates_by_recipe(db, [r.id for r in recipes.values()], since)
    states: RecipeStates = {}
    for item_id, url in urls.items():
        target = recipes.get(url)
        states[item_id] = (target.id, dates.get(target.id, [])) if target else (None, [])
    return states
