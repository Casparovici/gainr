from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.listr_recipe import ListrRecipe, ListrRecipeIngredient
from app.models.listr_recipe_category import ListrRecipeCategory


def list_recipes(
    db: Session, include_archived: bool = False, category_id: int | None = None
) -> list[ListrRecipe]:
    query = select(ListrRecipe).order_by(ListrRecipe.title)
    if not include_archived:
        query = query.where(ListrRecipe.is_archived.is_(False))
    if category_id is not None:
        query = query.where(ListrRecipe.categories.any(ListrRecipeCategory.id == category_id))
    return list(db.execute(query).scalars().all())


def get_recipe(db: Session, recipe_id: int) -> ListrRecipe | None:
    query = (
        select(ListrRecipe)
        .options(joinedload(ListrRecipe.ingredients).joinedload(ListrRecipeIngredient.grocery_item))
        .where(ListrRecipe.id == recipe_id)
    )
    return db.execute(query).unique().scalar_one_or_none()


def get_by_mealie_id(db: Session, mealie_id: str) -> ListrRecipe | None:
    return db.execute(select(ListrRecipe).where(ListrRecipe.mealie_id == mealie_id)).scalar_one_or_none()


def get_by_source_urls(db: Session, urls: list[str]) -> dict[str, ListrRecipe]:
    """source_url -> recipe, for the recipes planned from briefr suggestions with these pages."""
    if not urls:
        return {}
    rows = db.execute(select(ListrRecipe).where(ListrRecipe.source_url.in_(urls))).scalars().all()
    return {recipe.source_url: recipe for recipe in rows if recipe.source_url is not None}


def mealie_sources(db: Session) -> dict[str, str | None]:
    """mealie_id -> the Mealie last-changed stamp stored at import, for every imported recipe
    (archived ones included -- archiving in listr doesn't make it a new recipe in Mealie)."""
    rows = db.execute(
        select(ListrRecipe.mealie_id, ListrRecipe.mealie_updated_at).where(ListrRecipe.mealie_id.is_not(None))
    ).all()
    return {mealie_id: updated_at for mealie_id, updated_at in rows}


def create_recipe(db: Session, **fields) -> ListrRecipe:
    recipe = ListrRecipe(**fields)
    db.add(recipe)
    db.flush()
    return recipe


def update_recipe(db: Session, recipe: ListrRecipe, **fields) -> ListrRecipe:
    for key, value in fields.items():
        setattr(recipe, key, value)
    db.flush()
    return recipe


def delete_recipe(db: Session, recipe: ListrRecipe) -> None:
    db.delete(recipe)  # its ingredients and category links go with it (model relationships)
    db.flush()


# -- ingredients ----------------------------------------------------------------------------


def next_ingredient_sort_order(db: Session, recipe_id: int) -> int:
    current_max = db.execute(
        select(func.max(ListrRecipeIngredient.sort_order)).where(
            ListrRecipeIngredient.recipe_id == recipe_id
        )
    ).scalar_one_or_none()
    return (current_max or 0) + 1


def add_ingredient(db: Session, **fields) -> ListrRecipeIngredient:
    ingredient = ListrRecipeIngredient(**fields)
    db.add(ingredient)
    db.flush()
    return ingredient


def delete_ingredient(db: Session, ingredient: ListrRecipeIngredient) -> None:
    db.delete(ingredient)
    db.flush()
