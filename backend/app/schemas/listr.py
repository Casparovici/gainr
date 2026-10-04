from datetime import date as date_, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# -- categories -----------------------------------------------------------------------------


class ListrCategoryCreate(BaseModel):
    name: str


class ListrCategoryUpdate(BaseModel):
    color: str | None = None
    is_archived: bool | None = None


class ListrCategoryReorder(BaseModel):
    category_ids: list[int]


class ListrCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
    color: str | None = None
    is_archived: bool


# -- items (the catalog) ---------------------------------------------------------------------


class ListrItemCreate(BaseModel):
    name: str
    category_id: int
    default_unit: str


class ListrItemUpdate(BaseModel):
    name: str | None = None
    category_id: int | None = None
    default_unit: str | None = None
    is_archived: bool | None = None


class ListrItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category_id: int
    category_name: str | None = None
    default_unit: str
    is_archived: bool
    # Set once via PUT /items/{id}/picnic-mapping (see the "picnic" section below), never through
    # the general update above -- picking a Picnic product is its own deliberate action.
    picnic_product_id: str | None = None
    picnic_product_name: str | None = None
    # The mapped product's price per selling unit and that unit, as of picnic_price_at -- see
    # ListrItem. Picnic only sells in euros, so the currency is always "EUR" when a price is set.
    picnic_price: Decimal | None = None
    picnic_price_currency: Literal["EUR"] | None = None
    picnic_unit_quantity: str | None = None
    picnic_price_at: datetime | None = None
    picnic_image_url: str | None = None
    # Computed server-side from inventory_count vs inventory_minimum whenever either changes, or
    # tracking starts/stops (PUT /items/{id}/inventory) -- see docs/adr/0015-listr-inventory.md's
    # second addendum. Never set directly by the client. None means the item isn't tracked.
    inventory_status: Literal["in_stock", "low", "out"] | None = None
    # A bare tally, adjusted with +/- via POST /items/{id}/inventory/count. Meaningful only
    # alongside inventory_status, but always present (defaults to 0) rather than nullable, since
    # "not tracked" is already fully expressed by inventory_status.
    inventory_count: int = 0
    # The reorder point driving inventory_status above, adjusted with +/- via
    # POST /items/{id}/inventory/minimum, same shape as inventory_count.
    inventory_minimum: int = 0


class ListrInventoryTrackingIn(BaseModel):
    # Starting tracking computes inventory_status fresh from whatever count/minimum the item
    # already carries (usually 0/0, from an earlier untrack, or brand new); stopping clears it to
    # None. There's no separate "untracked but has a remembered status" state.
    tracked: bool


class ListrInventoryMinimumDeltaIn(BaseModel):
    # A delta, not an absolute value -- same reasoning as ListrInventoryCountDeltaIn: the +/-
    # button click is the whole payload, computed and clamped at 0 server-side against a fresh
    # read, not against whatever the client last happened to have cached.
    delta: int


class ListrInventoryCountDeltaIn(BaseModel):
    # Typically +1/-1 from the Voorraad UI's buttons; the server clamps the result at 0 rather
    # than trusting the client not to send something that would go negative.
    delta: int


class ListrInventoryAddToListIn(BaseModel):
    item_ids: list[int] = Field(min_length=1)
    # Exactly one of these -- an existing list, or a brand-new one created on the spot.
    list_id: int | None = None
    new_list_name: str | None = None


# -- lists ------------------------------------------------------------------------------------


class ListrListCreate(BaseModel):
    name: str


class ListrListUpdate(BaseModel):
    name: str | None = None
    is_archived: bool | None = None


class ListrListDuplicate(BaseModel):
    name: str


class ListrListItemCreate(BaseModel):
    grocery_item_id: int
    quantity: Decimal = Field(default=Decimal(1), gt=0)
    unit: str | None = None  # defaults to the grocery item's default_unit when omitted


class ListrListItemUpdate(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = None
    is_checked: bool | None = None


class ListrListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    list_id: int
    grocery_item_id: int
    grocery_item_name: str
    category_id: int
    category_name: str
    quantity: Decimal
    unit: str
    is_checked: bool
    sort_order: int
    picnic_product_id: str | None = None
    picnic_product_name: str | None = None
    picnic_price: Decimal | None = None  # EUR, per Picnic selling unit
    picnic_unit_quantity: str | None = None
    picnic_image_url: str | None = None


class ListrListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    item_count: int = 0
    checked_count: int = 0


class ListrListDetailOut(ListrListOut):
    items: list[ListrListItemOut] = []


# -- add-ingredients-to-list ------------------------------------------------------------------


class ListrAddIngredientsIn(BaseModel):
    # Exactly one of these -- an existing list, or a brand-new one created on the spot.
    list_id: int | None = None
    new_list_name: str | None = None
    ingredient_ids: list[int] = Field(min_length=1)


# -- recipes ------------------------------------------------------------------------------------


class ListrRecipeIngredientCreate(BaseModel):
    grocery_item_id: int
    quantity: Decimal = Field(default=Decimal(1), gt=0)
    unit: str | None = None  # defaults to the grocery item's default_unit when omitted


class ListrRecipeIngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    grocery_item_id: int
    grocery_item_name: str
    quantity: Decimal
    unit: str
    sort_order: int


class ListrRecipeCategoryCreate(BaseModel):
    name: str


class ListrRecipeCategoryUpdate(BaseModel):
    color: str | None = None
    is_archived: bool | None = None


class ListrRecipeCategoryReorder(BaseModel):
    category_ids: list[int]


class ListrRecipeCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
    color: str | None = None
    is_archived: bool


class ListrRecipeCreate(BaseModel):
    title: str
    servings: int | None = Field(default=None, ge=1)
    instructions: str = ""
    notes: str | None = None
    ingredients: list[ListrRecipeIngredientCreate] = []
    category_ids: list[int] = []


class ListrRecipeUpdate(BaseModel):
    title: str | None = None
    servings: int | None = Field(default=None, ge=1)
    instructions: str | None = None
    notes: str | None = None
    is_archived: bool | None = None
    # When provided, replaces the recipe's whole ingredient list -- simpler and safer than a
    # partial add/remove/reorder diff for a form that always submits the full set it's editing.
    ingredients: list[ListrRecipeIngredientCreate] | None = None
    # Same full-replace semantics as ingredients above.
    category_ids: list[int] | None = None


class ListrRecipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    servings: int | None
    instructions: str
    notes: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    ingredients: list[ListrRecipeIngredientOut] = []
    categories: list[ListrRecipeCategoryOut] = []
    # Set when the recipe was imported from Mealie -- a re-import overwrites edits made here.
    mealie_id: str | None = None


# -- weekplanner / meal history -----------------------------------------------------------------


class ListrMealPlanInput(BaseModel):
    recipe_id: int | None = None
    is_cooked: bool = False
    notes: str | None = None


class ListrMealPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date_
    recipe_id: int | None
    recipe_title: str | None = None
    is_cooked: bool
    notes: str | None


class ListrPopularRecipeOut(BaseModel):
    recipe_id: int
    title: str
    times_cooked: int


class ListrMealPlanAddToListIn(BaseModel):
    # Which planned days to pull ingredients from -- lets the caller drop specific days from an
    # otherwise-full week/month range rather than an all-or-nothing bulk add.
    dates: list[date_] = Field(min_length=1)
    # Exactly one of these -- an existing list, or a brand-new one created on the spot.
    list_id: int | None = None
    new_list_name: str | None = None


# -- picnic (see docs/adr/0011-listr-picnic-integration.md) ----------------------------------


class ListrPicnicDeliveryProcessedOut(BaseModel):
    orders_booked: int
    orders_matched: int
    items_restocked: int


class ListrPicnicDeliveryOut(BaseModel):
    id: str
    delivered_at: datetime
    total: Decimal  # groceries after discounts, excluding deposit
    order_count: int
    # Set once the delivery has been processed into gripr/Voorraad (see picnic_sync_service).
    processed: ListrPicnicDeliveryProcessedOut | None = None


class ListrPicnicMonthOut(BaseModel):
    month: date_  # first day of the month
    total: Decimal
    deliveries: int


class ListrPicnicOrderHistoryOut(BaseModel):
    since: date_  # first day inside the rolling 12-month window
    currency: str
    total: Decimal
    average_per_delivery: Decimal | None
    deliveries: list[ListrPicnicDeliveryOut]  # newest first
    # Oldest first, every calendar month the window touches -- the first and last are partial.
    months: list[ListrPicnicMonthOut]


class ListrPicnicStatusOut(BaseModel):
    configured: bool  # GAINR_PICNIC_EMAIL/PASSWORD are set in the environment
    connected: bool  # a session key is stored and hasn't been rejected yet


class ListrPicnicLoginOut(BaseModel):
    requires_2fa: bool


class ListrPicnicVerify2FAIn(BaseModel):
    code: str


class ListrPicnicProductOut(BaseModel):
    id: str
    name: str
    unit_quantity: str
    display_price: int | None = None  # cents, as Picnic reports it
    image_id: str | None = None
    image_url: str | None = None


class ListrPicnicCartLineOut(BaseModel):
    product_id: str
    name: str
    image_url: str | None
    unit_quantity: str
    count: int
    price: Decimal  # EUR, the whole line after any bundle discount


class ListrPicnicCartOut(BaseModel):
    currency: Literal["EUR"] = "EUR"
    mts: int  # cart version; ordering quotes it back (see ListrPicnicCheckoutIn)
    lines: list[ListrPicnicCartLineOut]
    item_count: int
    total: Decimal
    deposit: Decimal
    checkout_total: Decimal  # what ordering charges
    selected_slot_id: str | None
    slot_chosen: bool  # false while it's only Picnic's own preselection


class ListrPicnicSlotOut(BaseModel):
    id: str
    window_start: datetime
    window_end: datetime
    cut_off: datetime
    is_available: bool
    selected: bool
    minimum_order: Decimal | None
    unavailable_reason: str | None


class ListrPicnicCartChangeIn(BaseModel):
    product_id: str
    count: int = Field(default=1, ge=1, le=50)


class ListrPicnicSlotIn(BaseModel):
    slot_id: str


class ListrPicnicPromoProductOut(BaseModel):
    id: str
    name: str
    unit_quantity: str
    image_url: str | None
    price: Decimal | None  # EUR, per selling unit, as offered
    original_price: Decimal | None  # EUR, the struck-through price when Picnic shows one
    label: str  # "1+1 gratis", "25% korting", "2 voor €5"


class ListrPicnicPromoSectionOut(BaseModel):
    title: str
    products: list[ListrPicnicPromoProductOut]


class ListrPicnicCheckoutIn(BaseModel):
    mts: int  # the cart version shown when "order" was pressed
    # Where the bank sends the reader back after paying -- this app's own cart page.
    return_url: str = Field(max_length=500, pattern=r"^https?://")


class ListrPicnicCheckoutOut(BaseModel):
    order_id: str
    transaction_id: str
    payment_url: str


class ListrPicnicCheckoutStatusOut(BaseModel):
    status: str
    finished: bool


class ListrPicnicMappingIn(BaseModel):
    picnic_product_id: str
    picnic_product_name: str
    # From the search result the product was picked from, so the price shows straight away.
    display_price: int | None = None  # cents
    unit_quantity: str | None = None
    image_id: str | None = None


class ListrPicnicPriceRefreshOut(BaseModel):
    updated: int
    # Linked products Picnic's search no longer returns (discontinued or renamed) -- their last
    # known price is kept, with its date.
    not_found: list[str]


class ListrPicnicSyncSettingsOut(BaseModel):
    enabled: bool
    gripr_account_id: int | None
    gripr_category_id: int | None
    since: date_ | None
    last_synced_at: datetime | None


class ListrPicnicSyncSettingsIn(BaseModel):
    enabled: bool
    gripr_account_id: int | None = None
    gripr_category_id: int | None = None
    since: date_ | None = None


class ListrPicnicSyncResultOut(BaseModel):
    deliveries: int
    orders_booked: int
    orders_matched: int
    items_restocked: int


class ListrPicnicPushResultOut(BaseModel):
    pushed: list[str]  # grocery item names actually added to the Picnic cart
    unmapped_item_ids: list[int]  # list-item ids that still need a Picnic product picked


class ListrPicnicRecipeSummaryOut(BaseModel):
    id: str
    name: str
    segment: str | None = None  # SAVED_RECIPES / USER_DEFINED_RECIPES / THIS_WEEK_RECIPES / ...


class ListrPicnicIngredientPreviewOut(BaseModel):
    name: str
    quantity: Decimal
    unit: str
    # Set when this ingredient already matches a catalog item by name -- reused silently on
    # import. Null means importing creates a new ListrItem, which needs a category (see
    # ListrPicnicImportIn.ingredient_category_ids).
    matched_item_id: int | None
    matched_item_name: str | None


class ListrPicnicRecipePreviewOut(BaseModel):
    servings: int | None
    instructions: str
    ingredients: list[ListrPicnicIngredientPreviewOut]


class ListrPicnicImportIn(BaseModel):
    name: str
    recipe_category_ids: list[int] = []
    # Same length and order as the preview's ingredients -- only used for entries that don't
    # already match an existing catalog item (null is fine for the rest).
    ingredient_category_ids: list[int | None]


# -- mealie (see docs/adr/0022-listr-mealie-import.md) ------------------------------------------


class ListrMealieStatusOut(BaseModel):
    configured: bool


class ListrMealieRecipeStatusOut(BaseModel):
    mealie_id: str
    name: str
    status: Literal["new", "changed", "unchanged"]


class ListrMealieUnmatchedFoodOut(BaseModel):
    food_id: str
    name: str
    recipe_names: list[str]
    # A proposed product the dialog pre-selects; never applied without the reader importing it.
    suggested_item_id: int | None = None
    suggested_item_name: str | None = None


class ListrMealiePreviewOut(BaseModel):
    recipes: list[ListrMealieRecipeStatusOut]
    unmatched_foods: list[ListrMealieUnmatchedFoodOut]


class ListrMealieFoodMappingIn(BaseModel):
    food_id: str = Field(min_length=1, max_length=64)
    grocery_item_id: int


class ListrMealieImportIn(BaseModel):
    mappings: list[ListrMealieFoodMappingIn] = []


class ListrMealieImportOut(BaseModel):
    created: int
    updated: int
    unchanged: int
