"""Writing a recipe: its ingredients (in order, each defaulting to its product's unit), its
categories and its photo, and what deleting one leaves behind."""

import io

from sqlalchemy.orm import Session

from app.models.listr_recipe import ListrRecipe
from app.repositories import (
    listr_item_repo,
    listr_leftover_repo,
    listr_meal_plan_repo,
    listr_recipe_category_repo,
    listr_recipe_repo,
)
from app.services.errors import InvalidRequest, NotFound

# The upload cap only guards against decoding something absurd; the real size control is the
# resize below, since every byte stored lands in the whole-database backups (docs/adr/0013).
MAX_PHOTO_UPLOAD_BYTES = 25 * 1024 * 1024
PHOTO_MAX_DIMENSION = 1600


def resize_photo(raw: bytes) -> bytes:
    """Always a JPEG capped at PHOTO_MAX_DIMENSION on its longest side. exif_transpose bakes in a
    phone photo's rotation, which a re-served plain JPEG would otherwise lose."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((PHOTO_MAX_DIMENSION, PHOTO_MAX_DIMENSION))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82)
        return buffer.getvalue()


def set_photo(db: Session, recipe: ListrRecipe, raw: bytes) -> None:
    if len(raw) > MAX_PHOTO_UPLOAD_BYTES:
        raise InvalidRequest("Photo too large")
    try:
        resized = resize_photo(raw)
    except Exception as exc:
        raise InvalidRequest("Could not read that as an image") from exc
    listr_recipe_repo.update_recipe(db, recipe, photo=resized, photo_content_type="image/jpeg")


def clear_photo(db: Session, recipe: ListrRecipe) -> None:
    listr_recipe_repo.update_recipe(db, recipe, photo=None, photo_content_type=None)


def _add_ingredients(db: Session, recipe: ListrRecipe, ingredients, first_sort_order: int) -> None:
    """`ingredients` are the request's (grocery_item_id, quantity, unit) entries, in order."""
    for position, ingredient in enumerate(ingredients, start=first_sort_order):
        item = listr_item_repo.get_item(db, ingredient.grocery_item_id)
        if item is None:
            raise NotFound(f"Grocery item {ingredient.grocery_item_id} not found")
        listr_recipe_repo.add_ingredient(
            db,
            recipe_id=recipe.id,
            grocery_item_id=item.id,
            quantity=ingredient.quantity,
            unit=ingredient.unit or item.default_unit,
            sort_order=position,
        )


def create_recipe(db: Session, *, ingredients, category_ids: list[int], **fields) -> ListrRecipe:
    categories = listr_recipe_category_repo.get_by_ids(db, category_ids)
    recipe = listr_recipe_repo.create_recipe(db, categories=categories, **fields)
    _add_ingredients(db, recipe, ingredients, listr_recipe_repo.next_ingredient_sort_order(db, recipe.id))
    return recipe


def update_recipe(db: Session, recipe: ListrRecipe, *, ingredients=None, category_ids=None, **fields) -> ListrRecipe:
    """Ingredients, when given, replace the whole set: the form always sends its full, current
    list, so replacing is simpler and safer than diffing against it."""
    if category_ids is not None:
        fields["categories"] = listr_recipe_category_repo.get_by_ids(db, category_ids)
    if fields:
        listr_recipe_repo.update_recipe(db, recipe, **fields)
    if ingredients is not None:
        for existing in list(recipe.ingredients):
            listr_recipe_repo.delete_ingredient(db, existing)
        _add_ingredients(db, recipe, ingredients, 0)
    return recipe


def delete_recipe(db: Session, recipe: ListrRecipe) -> None:
    """The weekplanner days and leftovers it was on stay, unlinked: they record what was eaten,
    the same way gripr keeps a deleted category's transactions."""
    listr_meal_plan_repo.unlink_recipe(db, recipe.id)
    listr_leftover_repo.unlink_recipe(db, recipe.id)
    listr_recipe_repo.delete_recipe(db, recipe)
