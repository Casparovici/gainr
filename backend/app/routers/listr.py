import hmac
from datetime import date as date_, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from icalendar import Calendar, Event
from sqlalchemy.orm import Session

from app import config
from app.db import get_db
from app.repositories import (
    gripr_account_repo,
    gripr_category_repo,
    listr_category_repo,
    listr_item_repo,
    listr_list_repo,
    listr_meal_plan_repo,
    listr_recipe_category_repo,
    listr_recipe_repo,
    picnic_sync_repo,
)
from app.schemas.listr import (
    ListrAddIngredientsIn,
    ListrCategoryCreate,
    ListrCategoryOut,
    ListrCategoryReorder,
    ListrCategoryUpdate,
    ListrInventoryAddToListIn,
    ListrInventoryCountDeltaIn,
    ListrInventoryMinimumDeltaIn,
    ListrInventoryTrackingIn,
    ListrItemCreate,
    ListrItemOut,
    ListrItemUpdate,
    ListrListCreate,
    ListrListDetailOut,
    ListrListDuplicate,
    ListrListItemCreate,
    ListrListItemOut,
    ListrListItemUpdate,
    ListrListOut,
    ListrListUpdate,
    ListrMealPlanInput,
    ListrMealPlanAddToListIn,
    ListrMealPlanOut,
    ListrMealieImportIn,
    ListrMealieImportOut,
    ListrMealiePreviewOut,
    ListrMealieRecipeStatusOut,
    ListrMealieStatusOut,
    ListrMealieUnmatchedFoodOut,
    ListrPicnicImportIn,
    ListrPicnicIngredientPreviewOut,
    ListrPicnicLoginOut,
    ListrPicnicMappingIn,
    ListrPicnicProductOut,
    ListrPicnicPushResultOut,
    ListrPicnicRecipePreviewOut,
    ListrPicnicRecipeSummaryOut,
    ListrPicnicCartChangeIn,
    ListrPicnicCartLineOut,
    ListrPicnicCartOut,
    ListrPicnicCheckoutIn,
    ListrPicnicCheckoutOut,
    ListrPicnicCheckoutStatusOut,
    ListrPicnicDeliveryOut,
    ListrPicnicDeliveryProcessedOut,
    ListrPicnicMonthOut,
    ListrPicnicOrderHistoryOut,
    ListrPicnicPriceRefreshOut,
    ListrPicnicSlotIn,
    ListrPicnicSlotOut,
    ListrPicnicPromoProductOut,
    ListrPicnicPromoSectionOut,
    ListrPicnicStatusOut,
    ListrPicnicSyncResultOut,
    ListrPicnicSyncSettingsIn,
    ListrPicnicSyncSettingsOut,
    ListrPicnicVerify2FAIn,
    ListrPopularRecipeOut,
    ListrRecipeCategoryCreate,
    ListrRecipeCategoryOut,
    ListrRecipeCategoryReorder,
    ListrRecipeCategoryUpdate,
    ListrRecipeCreate,
    ListrRecipeIngredientOut,
    ListrRecipeOut,
    ListrRecipeUpdate,
)
from app.services import listr_inventory_service, listr_list_service, picnic_sync_service
from app.services.listr_mealie_service import MealieNotConfigured, UnmappedMealieFoods, listr_mealie_service
from app.services.listr_picnic_service import (
    MissingIngredientCategory,
    PicnicNotConfigured,
    PicnicNotConnected,
    listr_picnic_service,
)
from app.services.mealie_provider import MealieAuthError, MealieError
from app.services.picnic_provider import PicnicAuthError, PicnicCheckoutError, picnic_image_url

router = APIRouter(prefix="/api/listr", tags=["listr"])


# -- categories -----------------------------------------------------------------------------


@router.get("/categories", response_model=list[ListrCategoryOut])
def list_categories(include_archived: bool = False, db: Session = Depends(get_db)):
    return listr_category_repo.list_categories(db, include_archived=include_archived)


@router.post("/categories", response_model=ListrCategoryOut)
def create_category(payload: ListrCategoryCreate, db: Session = Depends(get_db)):
    sort_order = listr_category_repo.next_sort_order(db)
    category = listr_category_repo.create_category(db, name=payload.name, sort_order=sort_order)
    db.commit()
    return category


@router.put("/categories/reorder", status_code=204)
def reorder_categories(payload: ListrCategoryReorder, db: Session = Depends(get_db)):
    listr_category_repo.reorder(db, payload.category_ids)
    db.commit()


@router.put("/categories/{category_id}", response_model=ListrCategoryOut)
def update_category(category_id: int, payload: ListrCategoryUpdate, db: Session = Depends(get_db)):
    category = listr_category_repo.get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    fields = payload.model_dump(exclude_unset=True)
    if fields:
        listr_category_repo.update_category(db, category, **fields)
    db.commit()
    return category


# -- items (the catalog) ----------------------------------------------------------------------


def _to_item_out(item) -> ListrItemOut:
    return ListrItemOut(
        id=item.id,
        name=item.name,
        category_id=item.category_id,
        category_name=item.category.name if item.category else None,
        default_unit=item.default_unit,
        is_archived=item.is_archived,
        picnic_product_id=item.picnic_product_id,
        picnic_product_name=item.picnic_product_name,
        picnic_price=item.picnic_price,
        picnic_price_currency="EUR" if item.picnic_price is not None else None,
        picnic_unit_quantity=item.picnic_unit_quantity,
        picnic_price_at=item.picnic_price_at,
        picnic_image_url=picnic_image_url(item.picnic_image_id) if item.picnic_image_id else None,
        inventory_status=item.inventory_status,
        inventory_count=item.inventory_count,
        inventory_minimum=item.inventory_minimum,
    )


@router.get("/items", response_model=list[ListrItemOut])
def list_items(include_archived: bool = False, category_id: int | None = None, db: Session = Depends(get_db)):
    items = listr_item_repo.list_items(db, include_archived=include_archived, category_id=category_id)
    return [_to_item_out(i) for i in items]


@router.post("/items", response_model=ListrItemOut)
def create_item(payload: ListrItemCreate, db: Session = Depends(get_db)):
    """Get-or-create by name -- adding a product that already exists in the catalog returns
    that product rather than erroring or duplicating, matching gainr's asset-creation flow."""
    category = listr_category_repo.get_category(db, payload.category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    existing = listr_item_repo.get_by_name(db, payload.name)
    if existing is not None:
        return _to_item_out(existing)
    item = listr_item_repo.create_item(
        db, name=payload.name, category_id=payload.category_id, default_unit=payload.default_unit
    )
    db.commit()
    db.refresh(item)
    return _to_item_out(item)


@router.put("/items/{item_id}", response_model=ListrItemOut)
def update_item(item_id: int, payload: ListrItemUpdate, db: Session = Depends(get_db)):
    item = listr_item_repo.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    fields = payload.model_dump(exclude_unset=True)
    if fields:
        listr_item_repo.update_item(db, item, **fields)
    db.commit()
    db.refresh(item)
    return _to_item_out(item)


@router.put("/items/{item_id}/picnic-mapping", response_model=ListrItemOut)
def set_item_picnic_mapping(item_id: int, payload: ListrPicnicMappingIn, db: Session = Depends(get_db)):
    """Picking which real Picnic product this catalog item means -- its own action, distinct
    from the general update above, since it's a deliberate one-time search-and-confirm step
    (see docs/adr/0011-listr-picnic-integration.md), not a field anyone would type by hand."""
    item = listr_item_repo.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    listr_item_repo.update_item(
        db,
        item,
        picnic_product_id=payload.picnic_product_id,
        picnic_product_name=payload.picnic_product_name,
        # The picked search result's own price, so it shows straight away; cleared when a pick
        # comes without one rather than keeping the previous product's price.
        picnic_price=Decimal(payload.display_price) / 100 if payload.display_price is not None else None,
        picnic_unit_quantity=payload.unit_quantity,
        picnic_price_at=datetime.now() if payload.display_price is not None else None,
        picnic_image_id=payload.image_id,
    )
    db.commit()
    db.refresh(item)
    return _to_item_out(item)


# -- inventory (see docs/adr/0015-listr-inventory.md) ------------------------------------------


@router.get("/inventory", response_model=list[ListrItemOut])
def list_inventory(db: Session = Depends(get_db)):
    return [_to_item_out(i) for i in listr_item_repo.list_inventory(db)]


@router.put("/items/{item_id}/inventory", response_model=ListrItemOut)
def set_item_inventory_tracking(item_id: int, payload: ListrInventoryTrackingIn, db: Session = Depends(get_db)):
    """Starts or stops tracking -- not a status to pick, that's computed (see
    listr_inventory_service.compute_status). Untracking clears inventory_status but leaves count/minimum as
    they were, so re-tracking later picks up where it left off instead of resetting to zero."""
    item = listr_item_repo.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    new_status = listr_inventory_service.compute_status(item.inventory_count, item.inventory_minimum) if payload.tracked else None
    listr_item_repo.update_item(db, item, inventory_status=new_status)
    db.commit()
    db.refresh(item)
    return _to_item_out(item)


@router.post("/items/{item_id}/inventory/minimum", response_model=ListrItemOut)
def adjust_item_inventory_minimum(item_id: int, payload: ListrInventoryMinimumDeltaIn, db: Session = Depends(get_db)):
    """+/- from the Voorraad UI, same shape and reasoning as adjust_item_inventory_count below --
    a delta computed against a fresh read, not an absolute value the client might be sending
    from a stale cache. Adjusting it while untracked is allowed and just remembered for later --
    it only affects inventory_status once the item is tracked."""
    item = listr_item_repo.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    listr_inventory_service.adjust_minimum(db, item, payload.delta)
    db.commit()
    db.refresh(item)
    return _to_item_out(item)


@router.post("/items/{item_id}/inventory/count", response_model=ListrItemOut)
def adjust_item_inventory_count(item_id: int, payload: ListrInventoryCountDeltaIn, db: Session = Depends(get_db)):
    """+/- from the Voorraad UI -- a delta (typically +1/-1), not an absolute value, so the
    button click itself is the whole payload; the client never needs to know or send the
    current count."""
    item = listr_item_repo.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    listr_inventory_service.adjust_count(db, item, payload.delta)
    db.commit()
    db.refresh(item)
    return _to_item_out(item)


@router.post("/inventory/add-to-list", response_model=ListrListOut)
def add_inventory_to_list(payload: ListrInventoryAddToListIn, db: Session = Depends(get_db)):
    """Bulk "restock these" action -- each item lands on the list at quantity 1 of its own
    default unit, same as there's no computed quantity anywhere else in listr; the reader
    adjusts the amount on the list itself, same as a manually added item."""
    if payload.list_id is None and not payload.new_list_name:
        raise HTTPException(status_code=400, detail="Provide list_id or new_list_name")

    if payload.list_id is not None:
        target_list = listr_list_repo.get_list(db, payload.list_id)
        if target_list is None:
            raise HTTPException(status_code=404, detail="List not found")
    else:
        target_list = listr_list_repo.create_list(db, name=payload.new_list_name)

    lines = []
    for item_id in payload.item_ids:
        item = listr_item_repo.get_item(db, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
        lines.append(listr_list_service.IngredientLine(item.id, Decimal("1"), item.default_unit))

    listr_list_service.add_ingredients_to_list(db, target_list.id, lines)
    db.commit()
    counts = listr_list_repo.counts_by_list(db)
    return _to_list_out(target_list, counts)


# -- lists ------------------------------------------------------------------------------------


def _to_list_out(grocery_list, counts: dict[int, tuple[int, int]]) -> ListrListOut:
    item_count, checked_count = counts.get(grocery_list.id, (0, 0))
    return ListrListOut(
        id=grocery_list.id,
        name=grocery_list.name,
        is_archived=grocery_list.is_archived,
        created_at=grocery_list.created_at,
        updated_at=grocery_list.updated_at,
        item_count=item_count,
        checked_count=checked_count,
    )


def _to_list_item_out(item) -> ListrListItemOut:
    return ListrListItemOut(
        id=item.id,
        list_id=item.list_id,
        grocery_item_id=item.grocery_item_id,
        grocery_item_name=item.grocery_item.name,
        category_id=item.grocery_item.category_id,
        category_name=item.grocery_item.category.name if item.grocery_item.category else "",
        quantity=item.quantity,
        unit=item.unit,
        is_checked=item.is_checked,
        sort_order=item.sort_order,
        picnic_product_id=item.grocery_item.picnic_product_id,
        picnic_product_name=item.grocery_item.picnic_product_name,
        picnic_price=item.grocery_item.picnic_price,
        picnic_unit_quantity=item.grocery_item.picnic_unit_quantity,
        picnic_image_url=(
            picnic_image_url(item.grocery_item.picnic_image_id) if item.grocery_item.picnic_image_id else None
        ),
    )


@router.get("/lists", response_model=list[ListrListOut])
def list_lists(include_archived: bool = False, db: Session = Depends(get_db)):
    lists = listr_list_repo.list_lists(db, include_archived=include_archived)
    counts = listr_list_repo.counts_by_list(db)
    return [_to_list_out(l, counts) for l in lists]


@router.post("/lists", response_model=ListrListOut)
def create_list(payload: ListrListCreate, db: Session = Depends(get_db)):
    grocery_list = listr_list_repo.create_list(db, name=payload.name)
    db.commit()
    db.refresh(grocery_list)
    return _to_list_out(grocery_list, {})


@router.get("/lists/{list_id}", response_model=ListrListDetailOut)
def get_list(list_id: int, db: Session = Depends(get_db)):
    grocery_list = listr_list_repo.get_list(db, list_id)
    if grocery_list is None:
        raise HTTPException(status_code=404, detail="List not found")
    items = listr_list_repo.list_items(db, list_id)
    return ListrListDetailOut(
        id=grocery_list.id,
        name=grocery_list.name,
        is_archived=grocery_list.is_archived,
        created_at=grocery_list.created_at,
        updated_at=grocery_list.updated_at,
        item_count=len(items),
        checked_count=sum(1 for i in items if i.is_checked),
        items=[_to_list_item_out(i) for i in items],
    )


@router.put("/lists/{list_id}", response_model=ListrListOut)
def update_list(list_id: int, payload: ListrListUpdate, db: Session = Depends(get_db)):
    grocery_list = listr_list_repo.get_list(db, list_id)
    if grocery_list is None:
        raise HTTPException(status_code=404, detail="List not found")
    fields = payload.model_dump(exclude_unset=True)
    if fields:
        listr_list_repo.update_list(db, grocery_list, **fields)
    db.commit()
    counts = listr_list_repo.counts_by_list(db)
    return _to_list_out(grocery_list, counts)


@router.delete("/lists/{list_id}", status_code=204)
def delete_list(list_id: int, db: Session = Depends(get_db)):
    grocery_list = listr_list_repo.get_list(db, list_id)
    if grocery_list is None:
        raise HTTPException(status_code=404, detail="List not found")
    db.delete(grocery_list)  # cascades to its items via the model relationship
    db.commit()


@router.post("/lists/{list_id}/duplicate", response_model=ListrListOut)
def duplicate_list(list_id: int, payload: ListrListDuplicate, db: Session = Depends(get_db)):
    if listr_list_repo.get_list(db, list_id) is None:
        raise HTTPException(status_code=404, detail="List not found")
    new_list = listr_list_service.duplicate_list(db, list_id, payload.name)
    db.commit()
    counts = listr_list_repo.counts_by_list(db)
    return _to_list_out(new_list, counts)


@router.post("/lists/{list_id}/clear-checked", status_code=204)
def clear_checked(list_id: int, db: Session = Depends(get_db)):
    if listr_list_repo.get_list(db, list_id) is None:
        raise HTTPException(status_code=404, detail="List not found")
    listr_list_service.clear_checked(db, list_id)
    db.commit()


@router.post("/lists/{list_id}/push-to-picnic", response_model=ListrPicnicPushResultOut)
def push_list_to_picnic(list_id: int, db: Session = Depends(get_db)):
    if listr_list_repo.get_list(db, list_id) is None:
        raise HTTPException(status_code=404, detail="List not found")
    try:
        result = listr_picnic_service.push_list_to_cart(db, list_id)
    except PicnicNotConnected as exc:
        # An expired session gets cleared (and already flushed) by the service before this
        # raises -- commit that now, or get_db's rollback-on-exception would silently undo it
        # and leave the same dead session to keep failing on every future attempt.
        db.commit()
        raise HTTPException(status_code=409, detail="Not connected to Picnic") from exc
    db.commit()
    return ListrPicnicPushResultOut(pushed=result.pushed, unmapped_item_ids=result.unmapped_item_ids)


@router.post("/lists/{list_id}/items", response_model=ListrListItemOut)
def add_list_item(list_id: int, payload: ListrListItemCreate, db: Session = Depends(get_db)):
    if listr_list_repo.get_list(db, list_id) is None:
        raise HTTPException(status_code=404, detail="List not found")
    item = listr_item_repo.get_item(db, payload.grocery_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Grocery item not found")
    unit = payload.unit or item.default_unit
    listr_list_service.add_ingredients_to_list(
        db, list_id, [listr_list_service.IngredientLine(item.id, payload.quantity, unit)]
    )
    db.commit()
    line = listr_list_repo.get_item_for_grocery_item(db, list_id, item.id, unit)
    return _to_list_item_out(line)


@router.put("/lists/{list_id}/items/{item_id}", response_model=ListrListItemOut)
def update_list_item(list_id: int, item_id: int, payload: ListrListItemUpdate, db: Session = Depends(get_db)):
    line = listr_list_repo.get_list_item(db, item_id)
    if line is None or line.list_id != list_id:
        raise HTTPException(status_code=404, detail="List item not found")
    fields = payload.model_dump(exclude_unset=True)
    if fields:
        listr_list_repo.update_list_item(db, line, **fields)
    db.commit()
    db.refresh(line)
    return _to_list_item_out(line)


@router.delete("/lists/{list_id}/items/{item_id}", status_code=204)
def delete_list_item(list_id: int, item_id: int, db: Session = Depends(get_db)):
    line = listr_list_repo.get_list_item(db, item_id)
    if line is None or line.list_id != list_id:
        raise HTTPException(status_code=404, detail="List item not found")
    listr_list_repo.delete_list_item(db, line)
    db.commit()


# -- recipe categories (a recipe's own tags -- Italiaans, Aziatisch, ... -- distinct from the
# product catalog's /categories above: a recipe can carry several at once) ----------------------


@router.get("/recipe-categories", response_model=list[ListrRecipeCategoryOut])
def list_recipe_categories(include_archived: bool = False, db: Session = Depends(get_db)):
    return listr_recipe_category_repo.list_categories(db, include_archived=include_archived)


@router.post("/recipe-categories", response_model=ListrRecipeCategoryOut)
def create_recipe_category(payload: ListrRecipeCategoryCreate, db: Session = Depends(get_db)):
    sort_order = listr_recipe_category_repo.next_sort_order(db)
    category = listr_recipe_category_repo.create_category(db, name=payload.name, sort_order=sort_order)
    db.commit()
    return category


@router.put("/recipe-categories/reorder", status_code=204)
def reorder_recipe_categories(payload: ListrRecipeCategoryReorder, db: Session = Depends(get_db)):
    listr_recipe_category_repo.reorder(db, payload.category_ids)
    db.commit()


@router.put("/recipe-categories/{category_id}", response_model=ListrRecipeCategoryOut)
def update_recipe_category(category_id: int, payload: ListrRecipeCategoryUpdate, db: Session = Depends(get_db)):
    category = listr_recipe_category_repo.get_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Recipe category not found")
    fields = payload.model_dump(exclude_unset=True)
    if fields:
        listr_recipe_category_repo.update_category(db, category, **fields)
    db.commit()
    return category


# -- recipes ------------------------------------------------------------------------------------


def _to_ingredient_out(ingredient) -> ListrRecipeIngredientOut:
    return ListrRecipeIngredientOut(
        id=ingredient.id,
        grocery_item_id=ingredient.grocery_item_id,
        grocery_item_name=ingredient.grocery_item.name,
        quantity=ingredient.quantity,
        unit=ingredient.unit,
        sort_order=ingredient.sort_order,
    )


def _to_recipe_out(recipe, include_ingredients: bool = True) -> ListrRecipeOut:
    return ListrRecipeOut(
        id=recipe.id,
        title=recipe.title,
        servings=recipe.servings,
        instructions=recipe.instructions,
        notes=recipe.notes,
        is_archived=recipe.is_archived,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
        ingredients=[_to_ingredient_out(i) for i in recipe.ingredients] if include_ingredients else [],
        categories=list(recipe.categories),
        mealie_id=recipe.mealie_id,
    )


@router.get("/recipes", response_model=list[ListrRecipeOut])
def list_recipes(include_archived: bool = False, category_id: int | None = None, db: Session = Depends(get_db)):
    # The recipe tile grid only needs title/servings -- ingredients aren't eager-loaded here,
    # so this stays lean rather than lazy-loading them per recipe for a list that won't show them.
    recipes = listr_recipe_repo.list_recipes(db, include_archived=include_archived, category_id=category_id)
    return [_to_recipe_out(r, include_ingredients=False) for r in recipes]


@router.post("/recipes", response_model=ListrRecipeOut)
def create_recipe(payload: ListrRecipeCreate, db: Session = Depends(get_db)):
    categories = listr_recipe_category_repo.get_by_ids(db, payload.category_ids)
    recipe = listr_recipe_repo.create_recipe(
        db,
        title=payload.title,
        servings=payload.servings,
        instructions=payload.instructions,
        notes=payload.notes,
        categories=categories,
    )
    for ingredient in payload.ingredients:
        item = listr_item_repo.get_item(db, ingredient.grocery_item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Grocery item {ingredient.grocery_item_id} not found")
        sort_order = listr_recipe_repo.next_ingredient_sort_order(db, recipe.id)
        listr_recipe_repo.add_ingredient(
            db,
            recipe_id=recipe.id,
            grocery_item_id=item.id,
            quantity=ingredient.quantity,
            unit=ingredient.unit or item.default_unit,
            sort_order=sort_order,
        )
    db.commit()
    recipe = listr_recipe_repo.get_recipe(db, recipe.id)
    return _to_recipe_out(recipe)


@router.get("/recipes/{recipe_id}", response_model=ListrRecipeOut)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = listr_recipe_repo.get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _to_recipe_out(recipe)


@router.put("/recipes/{recipe_id}", response_model=ListrRecipeOut)
def update_recipe(recipe_id: int, payload: ListrRecipeUpdate, db: Session = Depends(get_db)):
    recipe = listr_recipe_repo.get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    fields = payload.model_dump(exclude_unset=True, exclude={"ingredients", "category_ids"})
    if payload.category_ids is not None:
        fields["categories"] = listr_recipe_category_repo.get_by_ids(db, payload.category_ids)
    if fields:
        listr_recipe_repo.update_recipe(db, recipe, **fields)
    if payload.ingredients is not None:
        # Replace the whole set -- simpler and safer than diffing against a form that always
        # submits its full, current ingredient list.
        for existing in list(recipe.ingredients):
            listr_recipe_repo.delete_ingredient(db, existing)
        for position, ingredient in enumerate(payload.ingredients):
            item = listr_item_repo.get_item(db, ingredient.grocery_item_id)
            if item is None:
                raise HTTPException(status_code=404, detail=f"Grocery item {ingredient.grocery_item_id} not found")
            listr_recipe_repo.add_ingredient(
                db,
                recipe_id=recipe.id,
                grocery_item_id=item.id,
                quantity=ingredient.quantity,
                unit=ingredient.unit or item.default_unit,
                sort_order=position,
            )
    db.commit()
    recipe = listr_recipe_repo.get_recipe(db, recipe_id)
    return _to_recipe_out(recipe)


@router.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = listr_recipe_repo.get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    # The weekplanner history survives the delete -- unlinked, not removed -- same convention
    # gripr uses when a category is deleted out from under its transactions.
    listr_meal_plan_repo.unlink_recipe(db, recipe_id)
    db.delete(recipe)
    db.commit()


@router.post("/recipes/{recipe_id}/add-to-list", response_model=ListrListOut)
def add_recipe_to_list(recipe_id: int, payload: ListrAddIngredientsIn, db: Session = Depends(get_db)):
    recipe = listr_recipe_repo.get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if payload.list_id is None and not payload.new_list_name:
        raise HTTPException(status_code=400, detail="Provide list_id or new_list_name")

    if payload.list_id is not None:
        target_list = listr_list_repo.get_list(db, payload.list_id)
        if target_list is None:
            raise HTTPException(status_code=404, detail="List not found")
    else:
        target_list = listr_list_repo.create_list(db, name=payload.new_list_name)

    ingredients_by_id = {i.id: i for i in recipe.ingredients}
    lines = []
    for ingredient_id in payload.ingredient_ids:
        ingredient = ingredients_by_id.get(ingredient_id)
        if ingredient is None:
            raise HTTPException(status_code=404, detail=f"Ingredient {ingredient_id} not found on this recipe")
        lines.append(
            listr_list_service.IngredientLine(ingredient.grocery_item_id, ingredient.quantity, ingredient.unit)
        )

    listr_list_service.add_ingredients_to_list(db, target_list.id, lines)
    db.commit()
    counts = listr_list_repo.counts_by_list(db)
    return _to_list_out(target_list, counts)


# -- weekplanner / meal history -----------------------------------------------------------------


def _to_meal_plan_out(entry) -> ListrMealPlanOut:
    return ListrMealPlanOut(
        date=entry.date,
        recipe_id=entry.recipe_id,
        recipe_title=entry.recipe.title if entry.recipe else None,
        is_cooked=entry.is_cooked,
        notes=entry.notes,
    )


@router.get("/meal-plan", response_model=list[ListrMealPlanOut])
def list_meal_plan(date_from: date_, date_to: date_, db: Session = Depends(get_db)):
    entries = listr_meal_plan_repo.list_range(db, date_from, date_to)
    return [_to_meal_plan_out(e) for e in entries]


@router.get("/meal-plan/popular", response_model=list[ListrPopularRecipeOut])
def get_popular_recipes(limit: int = 10, db: Session = Depends(get_db)):
    rows = listr_meal_plan_repo.popular_recipes(db, limit=limit)
    return [ListrPopularRecipeOut(recipe_id=r[0], title=r[1], times_cooked=r[2]) for r in rows]


@router.post("/meal-plan/add-to-list", response_model=ListrListOut)
def add_meal_plan_to_list(payload: ListrMealPlanAddToListIn, db: Session = Depends(get_db)):
    """Bulk sibling of a single recipe's "add to list" -- merges every ingredient from every
    planned day's recipe (across possibly several different recipes) into one list, using the
    same same-item-and-unit merge `add_ingredients_to_list` already does, so e.g. two different
    recipes both needing onions land as one summed line rather than two."""
    if payload.list_id is None and not payload.new_list_name:
        raise HTTPException(status_code=400, detail="Provide list_id or new_list_name")

    if payload.list_id is not None:
        target_list = listr_list_repo.get_list(db, payload.list_id)
        if target_list is None:
            raise HTTPException(status_code=404, detail="List not found")
    else:
        target_list = listr_list_repo.create_list(db, name=payload.new_list_name)

    lines = []
    for day in payload.dates:
        entry = listr_meal_plan_repo.get_by_date(db, day)
        if entry is None or entry.recipe is None:
            continue
        for ingredient in entry.recipe.ingredients:
            lines.append(
                listr_list_service.IngredientLine(ingredient.grocery_item_id, ingredient.quantity, ingredient.unit)
            )

    listr_list_service.add_ingredients_to_list(db, target_list.id, lines)
    db.commit()
    counts = listr_list_repo.counts_by_list(db)
    return _to_list_out(target_list, counts)


@router.put("/meal-plan/{date}", response_model=ListrMealPlanOut)
def set_meal_plan_day(date: date_, payload: ListrMealPlanInput, db: Session = Depends(get_db)):
    if payload.recipe_id is not None and listr_recipe_repo.get_recipe(db, payload.recipe_id) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    entry = listr_meal_plan_repo.upsert(
        db, date, recipe_id=payload.recipe_id, is_cooked=payload.is_cooked, notes=payload.notes
    )
    db.commit()
    entry = listr_meal_plan_repo.get_by_date(db, date)
    return _to_meal_plan_out(entry)


@router.delete("/meal-plan/{date}", status_code=204)
def clear_meal_plan_day(date: date_, db: Session = Depends(get_db)):
    listr_meal_plan_repo.clear(db, date)
    db.commit()


# -- picnic (see docs/adr/0011-listr-picnic-integration.md) ----------------------------------


@router.get("/picnic/status", response_model=ListrPicnicStatusOut)
def picnic_status(db: Session = Depends(get_db)):
    return ListrPicnicStatusOut(
        configured=bool(config.PICNIC_EMAIL and config.PICNIC_PASSWORD),
        connected=listr_picnic_service.is_connected(db),
    )


@router.post("/picnic/login", response_model=ListrPicnicLoginOut)
def picnic_login(db: Session = Depends(get_db)):
    """Credentials are server-side already (GAINR_PICNIC_EMAIL/PASSWORD) -- this just triggers
    the attempt. requires_2fa=true means Picnic just texted a code; call verify-2fa next."""
    try:
        requires_2fa = listr_picnic_service.start_login(db)
    except PicnicNotConfigured as exc:
        raise HTTPException(status_code=409, detail="Picnic credentials aren't configured") from exc
    except PicnicAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    db.commit()
    return ListrPicnicLoginOut(requires_2fa=requires_2fa)


@router.post("/picnic/verify-2fa", status_code=204)
def picnic_verify_2fa(payload: ListrPicnicVerify2FAIn, db: Session = Depends(get_db)):
    try:
        listr_picnic_service.complete_login(db, payload.code)
    except PicnicNotConnected as exc:
        raise HTTPException(status_code=409, detail="Start login again first") from exc
    except PicnicAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    db.commit()


@router.get("/picnic/search", response_model=list[ListrPicnicProductOut])
def picnic_search(q: str, db: Session = Depends(get_db)):
    try:
        products = listr_picnic_service.search_products(db, q)
    except PicnicNotConnected as exc:
        db.commit()  # persists a session cleared mid-call (see push-to-picnic for why)
        raise HTTPException(status_code=409, detail="Not connected to Picnic") from exc
    return [
        ListrPicnicProductOut(
            id=p.id, name=p.name, unit_quantity=p.unit_quantity, display_price=p.display_price,
            image_id=p.image_id, image_url=picnic_image_url(p.image_id) if p.image_id else None,
        )
        for p in products
    ]


@router.get("/picnic/orders", response_model=ListrPicnicOrderHistoryOut)
def picnic_orders(db: Session = Depends(get_db)):
    """The last 12 months of Picnic deliveries and what they cost, read live. When processing
    deliveries is switched on, any new ones are processed first (see picnic_sync_service), so
    the list already shows them as processed."""
    try:
        deliveries = listr_picnic_service.fetch_deliveries(db)
        picnic_sync_service.sync(db, deliveries=deliveries)
    except (PicnicNotConnected, picnic_sync_service.PicnicSyncNotConnected) as exc:
        db.commit()  # persists a session cleared mid-call (see push-to-picnic for why)
        raise HTTPException(status_code=409, detail="Not connected to Picnic") from exc
    history = listr_picnic_service.order_history(db, deliveries=deliveries)
    processed = picnic_sync_repo.synced_by_id(db, [d.id for d in history.deliveries])
    return ListrPicnicOrderHistoryOut(
        since=history.since,
        currency=history.currency,
        total=history.total,
        average_per_delivery=history.average_per_delivery,
        deliveries=[
            ListrPicnicDeliveryOut(
                id=d.id,
                delivered_at=d.delivered_at,
                total=Decimal(d.total_cents) / 100,
                order_count=d.order_count,
                processed=(
                    ListrPicnicDeliveryProcessedOut(
                        orders_booked=processed[d.id].orders_booked,
                        orders_matched=processed[d.id].orders_matched,
                        items_restocked=processed[d.id].items_restocked,
                    )
                    if d.id in processed
                    else None
                ),
            )
            for d in history.deliveries
        ],
        months=[ListrPicnicMonthOut(month=m.month, total=m.total, deliveries=m.deliveries) for m in history.months],
    )


def _sync_settings_out(settings) -> ListrPicnicSyncSettingsOut:
    return ListrPicnicSyncSettingsOut(
        enabled=settings.enabled,
        gripr_account_id=settings.gripr_account_id,
        gripr_category_id=settings.gripr_category_id,
        since=settings.since,
        last_synced_at=settings.last_synced_at,
    )


@router.get("/picnic/sync-settings", response_model=ListrPicnicSyncSettingsOut)
def get_picnic_sync_settings(db: Session = Depends(get_db)):
    return _sync_settings_out(picnic_sync_repo.get_settings(db))


@router.put("/picnic/sync-settings", response_model=ListrPicnicSyncSettingsOut)
def update_picnic_sync_settings(payload: ListrPicnicSyncSettingsIn, db: Session = Depends(get_db)):
    """Switching on without an account and category still restocks Voorraad; gripr booking
    needs both. `since` defaults to today, so switching on never reaches back into history
    unless the reader picks an earlier date on purpose."""
    if payload.gripr_account_id is not None and gripr_account_repo.get_account(db, payload.gripr_account_id) is None:
        raise HTTPException(status_code=400, detail="Unknown gripr account")
    if payload.gripr_category_id is not None and gripr_category_repo.get_category(db, payload.gripr_category_id) is None:
        raise HTTPException(status_code=400, detail="Unknown gripr category")
    settings = picnic_sync_repo.update_settings(
        db,
        enabled=payload.enabled,
        gripr_account_id=payload.gripr_account_id,
        gripr_category_id=payload.gripr_category_id,
        since=payload.since or (date_.today() if payload.enabled else None),
    )
    db.commit()
    return _sync_settings_out(settings)


@router.post("/picnic/sync", response_model=ListrPicnicSyncResultOut)
def run_picnic_sync(db: Session = Depends(get_db)):
    try:
        result = picnic_sync_service.sync(db)
    except picnic_sync_service.PicnicSyncNotConnected as exc:
        db.commit()
        raise HTTPException(status_code=409, detail="Not connected to Picnic") from exc
    db.commit()
    return ListrPicnicSyncResultOut(
        deliveries=result.deliveries,
        orders_booked=result.orders_booked,
        orders_matched=result.orders_matched,
        items_restocked=result.items_restocked,
    )


@router.post("/picnic/refresh-prices", response_model=ListrPicnicPriceRefreshOut)
def refresh_picnic_prices(db: Session = Depends(get_db)):
    """One Picnic search per linked product -- slow-ish (well under a second each), so it's an
    explicit action here and a daily job on the homecloud (scripts/sync_picnic.py)."""
    try:
        updated, not_found = listr_picnic_service.refresh_prices(db)
    except PicnicNotConnected as exc:
        db.commit()
        raise HTTPException(status_code=409, detail="Not connected to Picnic") from exc
    db.commit()
    return ListrPicnicPriceRefreshOut(updated=updated, not_found=not_found)


# -- picnic cart, delivery slot and ordering (docs/adr/0028-picnic-ordering-from-listr.md) ---------


def _cents(value: int | None) -> Decimal | None:
    return Decimal(value) / 100 if value is not None else None


def _cart_out(cart) -> ListrPicnicCartOut:
    return ListrPicnicCartOut(
        mts=cart.mts,
        lines=[
            ListrPicnicCartLineOut(
                product_id=line.product_id,
                name=line.name,
                image_url=picnic_image_url(line.image_id) if line.image_id else None,
                unit_quantity=line.unit_quantity,
                count=line.count,
                price=_cents(line.price_cents),
            )
            for line in cart.lines
        ],
        item_count=sum(line.count for line in cart.lines),
        total=_cents(cart.total_cents),
        deposit=_cents(cart.deposit_cents),
        checkout_total=_cents(cart.checkout_total_cents),
        selected_slot_id=cart.selected_slot_id,
        slot_chosen=cart.selected_slot_state not in (None, "IMPLICIT"),
    )


def _picnic(db: Session, fn):
    """Runs a Picnic cart/order call, turning "not connected" into 409 and a refused checkout
    into 400 with Picnic's own explanation."""
    try:
        return fn()
    except PicnicNotConnected as exc:
        db.commit()  # persists a session cleared mid-call (see push-to-picnic for why)
        raise HTTPException(status_code=409, detail="Not connected to Picnic") from exc
    except PicnicCheckoutError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/picnic/cart", response_model=ListrPicnicCartOut)
def picnic_cart(db: Session = Depends(get_db)):
    return _cart_out(_picnic(db, lambda: listr_picnic_service.get_cart(db)))


@router.post("/picnic/cart/add", response_model=ListrPicnicCartOut)
def picnic_cart_add(payload: ListrPicnicCartChangeIn, db: Session = Depends(get_db)):
    return _cart_out(_picnic(db, lambda: listr_picnic_service.add_to_cart(db, payload.product_id, payload.count)))


@router.post("/picnic/cart/remove", response_model=ListrPicnicCartOut)
def picnic_cart_remove(payload: ListrPicnicCartChangeIn, db: Session = Depends(get_db)):
    return _cart_out(_picnic(db, lambda: listr_picnic_service.remove_from_cart(db, payload.product_id, payload.count)))


@router.get("/picnic/slots", response_model=list[ListrPicnicSlotOut])
def picnic_slots(db: Session = Depends(get_db)):
    slots = _picnic(db, lambda: listr_picnic_service.delivery_slots(db))
    return [
        ListrPicnicSlotOut(
            id=slot.id, window_start=slot.window_start, window_end=slot.window_end, cut_off=slot.cut_off,
            is_available=slot.is_available, selected=slot.selected,
            minimum_order=_cents(slot.minimum_order_cents), unavailable_reason=slot.unavailable_reason,
        )
        for slot in slots
    ]


@router.put("/picnic/slot", response_model=ListrPicnicCartOut)
def picnic_set_slot(payload: ListrPicnicSlotIn, db: Session = Depends(get_db)):
    return _cart_out(_picnic(db, lambda: listr_picnic_service.set_delivery_slot(db, payload.slot_id)))


@router.get("/picnic/promotions", response_model=list[ListrPicnicPromoSectionOut])
def picnic_promotions(db: Session = Depends(get_db)):
    """This week's offers, by Picnic's own sections. Read from Picnic's Aanbiedingen page
    (fetched once per day); adding one goes through POST /picnic/cart/add like any product."""
    sections = _picnic(db, lambda: listr_picnic_service.promotions(db))
    return [
        ListrPicnicPromoSectionOut(
            title=section.title,
            products=[
                ListrPicnicPromoProductOut(
                    id=promo.product.id,
                    name=promo.product.name,
                    unit_quantity=promo.product.unit_quantity,
                    image_url=picnic_image_url(promo.product.image_id) if promo.product.image_id else None,
                    price=_cents(promo.product.display_price),
                    original_price=_cents(promo.original_price),
                    label=promo.label,
                )
                for promo in section.products
            ],
        )
        for section in sections
    ]


@router.post("/picnic/checkout", response_model=ListrPicnicCheckoutOut)
def picnic_checkout(payload: ListrPicnicCheckoutIn, db: Session = Depends(get_db)):
    """Starts the order and its payment. Nothing is charged here: the response's payment_url is
    the bank's page, and the order is only placed once the reader approves it there."""
    checkout = _picnic(db, lambda: listr_picnic_service.checkout(db, payload.mts, payload.return_url))
    return ListrPicnicCheckoutOut(order_id=checkout.order_id, transaction_id=checkout.transaction_id, payment_url=checkout.payment_url)


@router.get("/picnic/checkout/{transaction_id}", response_model=ListrPicnicCheckoutStatusOut)
def picnic_checkout_status(transaction_id: str, db: Session = Depends(get_db)):
    status = _picnic(db, lambda: listr_picnic_service.checkout_status(db, transaction_id))
    return ListrPicnicCheckoutStatusOut(status=status, finished=status == "FINISHED")


@router.post("/picnic/checkout/{transaction_id}/cancel", status_code=204)
def picnic_checkout_cancel(transaction_id: str, db: Session = Depends(get_db)):
    _picnic(db, lambda: listr_picnic_service.cancel_checkout(db, transaction_id))


@router.get("/picnic/cookbook", response_model=list[ListrPicnicRecipeSummaryOut])
def picnic_cookbook(db: Session = Depends(get_db)):
    """Every recipe tile Picnic's cookbook page shows -- saved, self-created, and its own
    weekly featured suggestions alike. There's no keyword search for recipes, only this list."""
    try:
        recipes = listr_picnic_service.list_cookbook(db)
    except PicnicNotConnected as exc:
        db.commit()  # persists a session cleared mid-call (see push-to-picnic for why)
        raise HTTPException(status_code=409, detail="Not connected to Picnic") from exc
    return [ListrPicnicRecipeSummaryOut(id=r.id, name=r.name, segment=r.segment) for r in recipes]


@router.get("/picnic/cookbook/{recipe_id}", response_model=ListrPicnicRecipePreviewOut)
def picnic_recipe_preview(recipe_id: str, db: Session = Depends(get_db)):
    try:
        preview = listr_picnic_service.get_recipe_preview(db, recipe_id)
    except PicnicNotConnected as exc:
        db.commit()
        raise HTTPException(status_code=409, detail="Not connected to Picnic") from exc
    return ListrPicnicRecipePreviewOut(
        servings=preview.servings,
        instructions=preview.instructions,
        ingredients=[
            ListrPicnicIngredientPreviewOut(
                name=i.name, quantity=i.quantity, unit=i.unit,
                matched_item_id=i.matched_item_id, matched_item_name=i.matched_item_name,
            )
            for i in preview.ingredients
        ],
    )


@router.post("/picnic/cookbook/{recipe_id}/import", response_model=ListrRecipeOut)
def picnic_import_recipe(recipe_id: str, payload: ListrPicnicImportIn, db: Session = Depends(get_db)):
    try:
        recipe = listr_picnic_service.import_recipe(
            db, recipe_id, payload.name, payload.recipe_category_ids, payload.ingredient_category_ids,
        )
    except PicnicNotConnected as exc:
        db.commit()
        raise HTTPException(status_code=409, detail="Not connected to Picnic") from exc
    except MissingIngredientCategory as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    recipe = listr_recipe_repo.get_recipe(db, recipe.id)
    return _to_recipe_out(recipe)


# -- mealie (see docs/adr/0022-listr-mealie-import.md) ------------------------------------------


def _unmatched_out(foods) -> list[ListrMealieUnmatchedFoodOut]:
    return [
        ListrMealieUnmatchedFoodOut(
            food_id=f.food_id, name=f.name, recipe_names=f.recipe_names,
            suggested_item_id=f.suggested_item_id, suggested_item_name=f.suggested_item_name,
        )
        for f in foods
    ]


def _mealie_http_error(exc: Exception) -> HTTPException:
    """Mealie's own failures, as messages the dialog can show as-is. Never includes the key."""
    if isinstance(exc, MealieNotConfigured):
        return HTTPException(status_code=409, detail="Mealie is niet ingesteld op de server")
    if isinstance(exc, MealieAuthError):
        return HTTPException(status_code=502, detail="Mealie weigerde de API-sleutel — maak een nieuwe aan in Mealie")
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/mealie/status", response_model=ListrMealieStatusOut)
def mealie_status():
    return ListrMealieStatusOut(configured=listr_mealie_service.is_configured())


@router.get("/mealie/preview", response_model=ListrMealiePreviewOut)
def mealie_preview(db: Session = Depends(get_db)):
    """Which Mealie recipes are new / changed / unchanged since the last import, and which of
    their ingredients still need a catalog product picked -- reads only, changes nothing."""
    try:
        preview = listr_mealie_service.preview(db)
    except (MealieNotConfigured, MealieError) as exc:
        raise _mealie_http_error(exc) from exc
    return ListrMealiePreviewOut(
        recipes=[ListrMealieRecipeStatusOut(mealie_id=r.mealie_id, name=r.name, status=r.status) for r in preview.recipes],
        unmatched_foods=_unmatched_out(preview.unmatched_foods),
    )


@router.post("/mealie/import", response_model=ListrMealieImportOut)
def mealie_import(payload: ListrMealieImportIn, db: Session = Depends(get_db)):
    try:
        result = listr_mealie_service.import_recipes(db, {m.food_id: m.grocery_item_id for m in payload.mappings})
    except (MealieNotConfigured, MealieError) as exc:
        raise _mealie_http_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnmappedMealieFoods as exc:
        # Keep the picks already made (they're correct), so the dialog only has to ask about
        # the foods that are still missing.
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={"message": "Nog niet elk ingrediënt heeft een product", "unmatched_foods": [f.model_dump() for f in _unmatched_out(exc.foods)]},
        ) from exc
    db.commit()
    return ListrMealieImportOut(created=result.created, updated=result.updated, unchanged=result.unchanged)


def _build_meal_plan_ics(entries) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//gainr//listr weekplanner//NL")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Weekplanner")
    # Generated fresh on every request, so "now" is the correct DTSTAMP -- RFC 5545 requires
    # every VEVENT to carry one, and Google Calendar silently drops any event missing it while
    # still accepting the VCALENDAR wrapper itself (which is why the calendar showed up empty
    # rather than failing outright).
    now = datetime.now(timezone.utc)
    for entry in entries:
        title = entry.recipe.title if entry.recipe else entry.notes
        if not title:
            continue  # defensive -- upsert never leaves a row with neither recipe nor notes
        event = Event()
        event.add("summary", f"✓ {title}" if entry.is_cooked else title)
        if entry.recipe and entry.notes:
            event.add("description", entry.notes)
        event.add("dtstart", entry.date)
        event.add("dtend", entry.date + timedelta(days=1))
        event.add("dtstamp", now)
        event.add("uid", f"grecipe-meal-{entry.date.isoformat()}@ipper")
        cal.add_component(event)
    return cal.to_ical()


@router.get("/meal-plan.ics")
def meal_plan_ics(token: str, db: Session = Depends(get_db)):
    """Read-only feed for subscribing the weekplanner into an external calendar (e.g. Google
    Calendar's "From URL"). Gated by a shared-secret token rather than a login, since this is a
    single-user app with none -- 404 (not 401/403) on a bad or missing token, so the endpoint's
    existence isn't confirmed to an unauthenticated caller. See docs/adr/0007."""
    # compare_digest, not ==: this is the one endpoint deliberately reachable from the public
    # internet (Tailscale Funnel on :8443), so its token check is the one place where a
    # short-circuiting comparison's timing could leak the secret a character at a time.
    if not config.LISTR_ICS_TOKEN or not hmac.compare_digest(token, config.LISTR_ICS_TOKEN):
        raise HTTPException(status_code=404)
    entries = listr_meal_plan_repo.list_all(db)
    return Response(content=_build_meal_plan_ics(entries), media_type="text/calendar; charset=utf-8")
