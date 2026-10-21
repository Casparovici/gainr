"""What "Ophalen uit Mealie" means for listr's own data -- mealie_provider.py only knows how to
read Mealie's API. See docs/adr/0022-listr-mealie-import.md.

Mealie is the source of truth for an imported recipe: a recipe that's new there is created in
listr, one changed since its last import is overwritten, and an unchanged one is left alone.
Every ingredient has to land on a catalog product (listr's recipe lines reference ListrItem),
so a Mealie food resolves through, in order: a mapping the reader chose earlier
(grecipe_mealie_foods), then an exact case-insensitive name match. Anything still unresolved is
reported by `preview` and blocks `import_recipes` until the reader has picked a product for it.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app import config
from app.models.listr_item import ListrItem
from app.models.listr_recipe import ListrRecipe
from app.repositories import listr_item_repo, listr_mealie_food_repo, listr_recipe_category_repo, listr_recipe_repo
from app.services.errors import InvalidRequest
from app.services.listr_catalog_service import dutch_plurals
from app.services.listr_recipe_service import set_photo
from app.services.mealie_provider import MealieError, MealieIngredient, MealieProvider, MealieRecipe, MealieRecipeSummary

RecipeStatus = Literal["new", "changed", "unchanged"]


class MealieNotConfigured(Exception):
    """GAINR_MEALIE_URL/GAINR_MEALIE_API_KEY aren't set in the environment."""


@dataclass
class UnmatchedFood:
    food_id: str
    name: str
    recipe_names: list[str] = field(default_factory=list)
    # A best guess the dialog pre-selects ("aardappel" -> Aardappelen); only a proposal --
    # nothing is stored until the reader imports with it.
    suggested_item_id: int | None = None
    suggested_item_name: str | None = None


class UnmappedMealieFoods(Exception):
    """An import was attempted while some Mealie foods still have no catalog product."""

    def __init__(self, foods: list[UnmatchedFood]):
        self.foods = foods
        super().__init__(f"{len(foods)} Mealie food(s) have no catalog product yet")


@dataclass
class RecipeStatusRow:
    mealie_id: str
    name: str
    status: RecipeStatus


@dataclass
class MealiePreview:
    recipes: list[RecipeStatusRow]
    unmatched_foods: list[UnmatchedFood]


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0


def _default_provider() -> MealieProvider:
    if not (config.MEALIE_URL and config.MEALIE_API_KEY):
        raise MealieNotConfigured()
    return MealieProvider(config.MEALIE_URL, config.MEALIE_API_KEY)


class _FoodResolver:
    """Mealie food -> catalog product, per the module docstring's order."""

    def __init__(self, db: Session):
        self._mappings = listr_mealie_food_repo.list_mappings(db)
        self.items = listr_item_repo.list_items(db)
        self._by_name = {item.name.casefold(): item for item in self.items}

    def resolve(self, ingredient: MealieIngredient) -> ListrItem | None:
        if ingredient.food_id is None:
            return None
        mapping = self._mappings.get(ingredient.food_id)
        if mapping is not None:
            return mapping.grocery_item
        return self._by_name.get((ingredient.food_name or "").casefold())


def _suggest(food_name: str, items: list[ListrItem]) -> ListrItem | None:
    food = food_name.casefold().strip()
    if not food:
        return None
    by_name = {item.name.casefold(): item for item in items}
    words = food.split()
    for plural in sorted(dutch_plurals(words[-1])):
        if (item := by_name.get(" ".join([*words[:-1], plural]))) is not None:
            return item

    def rank(item: ListrItem) -> tuple[int, int] | None:
        name = item.name.casefold()
        if food in name.split():
            return (0, len(name))  # "peterselie" -> "Platte peterselie"
        if any(word.startswith(food) for word in name.split()):
            return (1, len(name))  # "kerrie" -> "Kerriepoeder"
        return None

    ranked = sorted((r, item.name) for item in items if (r := rank(item)) is not None)
    return by_name[ranked[0][1].casefold()] if ranked else None


def _instructions_markdown(recipe: MealieRecipe) -> str:
    """Mealie's steps as one numbered list (the markdown subset MarkdownLite renders), with a
    step's own title -- Mealie's "Bereiding", "Saus" -- as a heading above it."""
    lines: list[str] = []
    for number, (title, text) in enumerate(recipe.instructions, start=1):
        if title:
            lines.append(f"### {title}")
        # A list item is one line in MarkdownLite, so a step's own line breaks become spaces.
        lines.append(f"{number}. {' '.join(text.split())}")
    return "\n".join(lines)


def _notes_markdown(recipe: MealieRecipe, resolver: _FoodResolver) -> str | None:
    """Everything in Mealie that has no field of its own in listr, so importing loses nothing:
    the description, Mealie's notes, per-ingredient notes ("uit de vriezer"), and ingredient
    lines Mealie never parsed into a food (which can't become a catalog-backed recipe line)."""
    parts: list[str] = []
    if recipe.description:
        parts.append(recipe.description)
    parts.extend(recipe.notes)

    ingredient_notes = []
    for ingredient in recipe.ingredients:
        if ingredient.food_id and ingredient.note:
            item = resolver.resolve(ingredient)
            ingredient_notes.append(f"- {item.name if item else ingredient.food_name}: {ingredient.note}")
    if ingredient_notes:
        parts.append("**Bij de ingrediënten**\n" + "\n".join(ingredient_notes))

    unparsed = [f"- {i.display}" for i in recipe.ingredients if i.food_id is None]
    if unparsed:
        parts.append("**Ingrediënten zonder product**\n" + "\n".join(unparsed))

    return "\n\n".join(parts) or None


class ListrMealieService:
    def __init__(self, provider_factory: Callable[[], MealieProvider] | None = None):
        self._provider_factory = provider_factory or _default_provider

    def is_configured(self) -> bool:
        return bool(config.MEALIE_URL and config.MEALIE_API_KEY)

    def _pending(
        self, db: Session, provider: MealieProvider
    ) -> tuple[list[RecipeStatusRow], list[tuple[MealieRecipeSummary, MealieRecipe]]]:
        """Every Mealie recipe with its status, plus full details for the new/changed ones only
        -- an unchanged recipe is never fetched beyond the list call."""
        sources = listr_recipe_repo.mealie_sources(db)
        statuses: list[RecipeStatusRow] = []
        pending: list[tuple[MealieRecipeSummary, MealieRecipe]] = []
        for summary in provider.list_recipes():
            if summary.id not in sources:
                status: RecipeStatus = "new"
            # No stamp from Mealie means "can't tell" -- re-import rather than risk going stale.
            elif not summary.updated_at or sources[summary.id] != summary.updated_at:
                status = "changed"
            else:
                status = "unchanged"
            statuses.append(RecipeStatusRow(mealie_id=summary.id, name=summary.name, status=status))
            if status != "unchanged":
                pending.append((summary, provider.get_recipe(summary.slug)))
        return statuses, pending

    @staticmethod
    def _unmatched(pending: list[tuple[MealieRecipeSummary, MealieRecipe]], resolver: _FoodResolver) -> list[UnmatchedFood]:
        unmatched: dict[str, UnmatchedFood] = {}
        for _, recipe in pending:
            for ingredient in recipe.ingredients:
                if ingredient.food_id is None or resolver.resolve(ingredient) is not None:
                    continue
                food = unmatched.setdefault(
                    ingredient.food_id, UnmatchedFood(food_id=ingredient.food_id, name=ingredient.food_name or "?")
                )
                if recipe.name not in food.recipe_names:
                    food.recipe_names.append(recipe.name)
        for food in unmatched.values():
            if (suggestion := _suggest(food.name, resolver.items)) is not None:
                food.suggested_item_id, food.suggested_item_name = suggestion.id, suggestion.name
        return sorted(unmatched.values(), key=lambda f: f.name.casefold())

    def preview(self, db: Session) -> MealiePreview:
        provider = self._provider_factory()
        try:
            statuses, pending = self._pending(db, provider)
        finally:
            provider.close()
        return MealiePreview(recipes=statuses, unmatched_foods=self._unmatched(pending, _FoodResolver(db)))

    def import_recipes(self, db: Session, mappings: dict[str, int]) -> ImportResult:
        """Saves the reader's food -> product picks, then creates/updates every new or changed
        recipe. Re-fetches from Mealie rather than trusting a client-held preview, same as the
        Picnic import. Raises UnmappedMealieFoods (having saved nothing but the picks) if a food
        is still unresolved, e.g. a recipe added in Mealie since the preview was shown."""
        provider = self._provider_factory()
        try:
            statuses, pending = self._pending(db, provider)

            food_names = {i.food_id: i.food_name for _, r in pending for i in r.ingredients if i.food_id}
            for food_id, item_id in mappings.items():
                if listr_item_repo.get_item(db, item_id) is None:
                    raise ValueError(f"Grocery item {item_id} not found")
                listr_mealie_food_repo.set_mapping(db, food_id, food_names.get(food_id) or food_id, item_id)

            resolver = _FoodResolver(db)
            unmatched = self._unmatched(pending, resolver)
            if unmatched:
                raise UnmappedMealieFoods(unmatched)

            result = ImportResult(unchanged=sum(1 for s in statuses if s.status == "unchanged"))
            for summary, recipe in pending:
                created = self._upsert(db, summary, recipe, resolver)
                self._import_photo(db, provider, recipe)
                if created:
                    result.created += 1
                else:
                    result.updated += 1
            return result
        finally:
            provider.close()

    @staticmethod
    def _import_photo(db: Session, provider: MealieProvider, recipe: MealieRecipe) -> None:
        """Mealie's picture replaces the recipe's photo, like the rest of an imported recipe. A
        recipe without one keeps whatever photo it has, and a picture that can't be fetched or
        read never fails the import -- the recipe itself is the point."""
        if not recipe.has_image:
            return
        try:
            raw = provider.get_image(recipe.id)
            target = listr_recipe_repo.get_by_mealie_id(db, recipe.id)
            if raw is not None and target is not None:
                set_photo(db, target, raw)
        except (MealieError, InvalidRequest):
            pass

    def _upsert(self, db: Session, summary: MealieRecipeSummary, recipe: MealieRecipe, resolver: _FoodResolver) -> bool:
        fields = dict(
            title=recipe.name,
            servings=recipe.servings,
            instructions=_instructions_markdown(recipe),
            notes=_notes_markdown(recipe, resolver),
            categories=self._categories(db, recipe.categories),
            # The list call's stamp, since that's what the next preview compares against.
            mealie_updated_at=summary.updated_at or None,
        )
        existing = listr_recipe_repo.get_by_mealie_id(db, recipe.id)
        if existing is None:
            target: ListrRecipe = listr_recipe_repo.create_recipe(db, mealie_id=recipe.id, **fields)
        else:
            target = listr_recipe_repo.update_recipe(db, existing, **fields)
            # Mealie wins: the ingredient list is replaced wholesale, not merged.
            target.ingredients.clear()
            db.flush()

        sort_order = 0
        for ingredient in recipe.ingredients:
            item = resolver.resolve(ingredient)
            if item is None:
                continue  # an unparsed line -- already carried into the notes
            listr_recipe_repo.add_ingredient(
                db,
                recipe_id=target.id,
                grocery_item_id=item.id,
                quantity=ingredient.quantity or Decimal("1"),
                unit=(ingredient.unit or item.default_unit)[:32],
                sort_order=sort_order,
            )
            sort_order += 1
        # add_ingredient writes rows by recipe_id, not through the relationship, so the
        # already-loaded (just cleared) collection would otherwise keep reading as empty.
        db.flush()
        db.expire(target, ["ingredients"])
        return existing is None

    @staticmethod
    def _categories(db: Session, names: list[str]):
        """Mealie's categories and tags as listr recipe categories, matched case-insensitively
        and created when missing -- they're the reader's own labels either way."""
        existing = {c.name.casefold(): c for c in listr_recipe_category_repo.list_categories(db, include_archived=True)}
        categories = []
        for name in names:
            category = existing.get(name.casefold())
            if category is None:
                category = listr_recipe_category_repo.create_category(
                    db, name=name, sort_order=listr_recipe_category_repo.next_sort_order(db)
                )
                existing[name.casefold()] = category
            if category not in categories:
                categories.append(category)
        return categories


listr_mealie_service = ListrMealieService()
