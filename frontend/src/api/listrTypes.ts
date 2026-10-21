export interface ListrCategory {
  id: number;
  name: string;
  sort_order: number;
  color: string | null;
  is_archived: boolean;
}

export type ListrInventoryStatus = "in_stock" | "low" | "out";

export interface ListrItem {
  id: number;
  name: string;
  category_id: number;
  category_name: string | null;
  default_unit: string;
  is_archived: boolean;
  picnic_product_id: string | null;
  picnic_product_name: string | null;
  /** The linked Picnic product's price per selling unit (EUR) and that unit, as of picnic_price_at. */
  picnic_price: string | null;
  picnic_price_currency: "EUR" | null;
  picnic_unit_quantity: string | null;
  picnic_price_at: string | null;
  picnic_image_url: string | null;
  // Computed server-side from inventory_count vs inventory_minimum -- never set directly. null
  // means the item isn't tracked at all -- see docs/adr/0015's addenda.
  inventory_status: ListrInventoryStatus | null;
  // A bare tally, adjusted with +/-.
  inventory_count: number;
  // The reorder point driving inventory_status above.
  inventory_minimum: number;
}

export interface ListrItemInput {
  name: string;
  category_id: number;
  default_unit: string;
}

export interface ListrList {
  id: number;
  name: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  item_count: number;
  checked_count: number;
  /** The supermarket whose aisle order the list follows; null = the standard order. */
  store_id: number | null;
}

export interface ListrListItem {
  id: number;
  list_id: number;
  grocery_item_id: number;
  grocery_item_name: string;
  category_id: number;
  category_name: string;
  quantity: string;
  unit: string;
  is_checked: boolean;
  sort_order: number;
  picnic_product_id: string | null;
  picnic_product_name: string | null;
  picnic_price: string | null; // EUR, per Picnic selling unit
  picnic_unit_quantity: string | null;
  picnic_image_url: string | null;
}

export interface ListrListDetail extends ListrList {
  items: ListrListItem[];
  /** Every category id in the order this list shows its groups: the store's aisles, then the rest. */
  category_order: number[];
}

/** A supermarket, and the order its aisles come in (docs/adr/0052). */
export interface ListrStore {
  id: number;
  name: string;
  sort_order: number;
  is_archived: boolean;
  /** The aisles the store has been arranged, first to last. */
  category_ids: number[];
  /** Every category in the order a list for this store shows them: those aisles, then the rest. */
  category_order: number[];
}

export interface ListrRecipeIngredient {
  id: number;
  grocery_item_id: number;
  grocery_item_name: string;
  quantity: string;
  unit: string;
  sort_order: number;
}

export interface ListrRecipeIngredientInput {
  grocery_item_id: number;
  quantity: string;
  unit?: string | null;
}

// A recipe's own tags (Italiaans, Aziatisch, ...) -- distinct from ListrCategory above, which
// is the product catalog's one-per-item container. A recipe can carry several of these at once.
export interface ListrRecipeCategory {
  id: number;
  name: string;
  sort_order: number;
  color: string | null;
  is_archived: boolean;
}

export interface ListrRecipe {
  id: number;
  title: string;
  servings: number | null;
  instructions: string;
  notes: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  ingredients: ListrRecipeIngredient[];
  categories: ListrRecipeCategory[];
  has_photo: boolean;
  /** Set when imported from Mealie -- the next import overwrites edits made in listr. */
  mealie_id: string | null;
  /** The page a recipe planned from a briefr suggestion came from. */
  source_url: string | null;
}

export interface ListrRecipeInput {
  title: string;
  servings: number | null;
  instructions: string;
  notes: string | null;
  ingredients: ListrRecipeIngredientInput[];
  category_ids: number[];
}

// -- weekplanner / meal history ------------------------------------------------------------------

export interface ListrMealPlanEntry {
  date: string;
  recipe_id: number | null;
  recipe_title: string | null;
  leftover_id: number | null;
  leftover_name: string | null;
  is_cooked: boolean;
  notes: string | null;
}

export interface ListrMealPlanInput {
  recipe_id: number | null;
  leftover_id: number | null;
  is_cooked: boolean;
  notes: string | null;
}

// -- leftovers (see docs/adr/0036-listr-leftovers.md) --------------------------------------------

export type ListrLeftoverLocation = "freezer" | "fridge";

export interface ListrLeftover {
  id: number;
  name: string;
  recipe_id: number | null;
  meals: number;
  servings_per_meal: number | null;
  location: ListrLeftoverLocation;
  stored_on: string;
  use_by: string;
}

export interface ListrLeftoverInput {
  name: string;
  recipe_id: number | null;
  meals: number;
  servings_per_meal: number | null;
  location: ListrLeftoverLocation;
  /** Blank lets the server pick: 3 days in the fridge, 90 in the freezer. */
  use_by: string | null;
}

export interface ListrPopularRecipe {
  recipe_id: number;
  title: string;
  times_cooked: number;
}

// -- picnic (see docs/adr/0011-listr-picnic-integration.md) ------------------------------------

export interface ListrMealieStatus {
  configured: boolean;
}

export interface ListrMealieRecipeStatus {
  mealie_id: string;
  name: string;
  status: "new" | "changed" | "unchanged";
}

export interface ListrMealieUnmatchedFood {
  food_id: string;
  name: string;
  recipe_names: string[];
  /** A proposed product to pre-select; nothing is stored until an import uses it. */
  suggested_item_id: number | null;
  suggested_item_name: string | null;
}

export interface ListrMealiePreview {
  recipes: ListrMealieRecipeStatus[];
  unmatched_foods: ListrMealieUnmatchedFood[];
}

export interface ListrMealieImportResult {
  created: number;
  updated: number;
  unchanged: number;
}

export interface ListrPicnicDelivery {
  id: string;
  delivered_at: string; // ISO timestamp with offset
  total: string; // groceries after discounts, excluding deposit
  order_count: number;
  /** Set once the delivery has been processed into gripr/Voorraad. */
  processed: { orders_booked: number; orders_matched: number; items_restocked: number } | null;
}

/** Whether -- and where -- completed Picnic deliveries are processed automatically. */
export interface ListrPicnicSyncSettings {
  enabled: boolean;
  gripr_account_id: number | null;
  gripr_category_id: number | null;
  since: string | null;
  last_synced_at: string | null;
}

export type ListrPicnicSyncSettingsInput = Omit<ListrPicnicSyncSettings, "last_synced_at">;

export interface ListrPicnicSyncResult {
  deliveries: number;
  orders_booked: number;
  orders_matched: number;
  items_restocked: number;
}

export interface ListrPicnicPriceRefresh {
  updated: number;
  not_found: string[];
}

export interface ListrPicnicMonth {
  month: string; // first day of the month
  total: string;
  deliveries: number;
}

/** The last 12 months (rolling) of Picnic deliveries, read live from Picnic. */
export interface ListrPicnicOrderHistory {
  since: string;
  currency: string;
  total: string;
  average_per_delivery: string | null;
  deliveries: ListrPicnicDelivery[]; // newest first
  months: ListrPicnicMonth[]; // oldest first; the first and last are partial months
}

export interface ListrPicnicStatus {
  configured: boolean;
  connected: boolean;
}

export interface ListrPicnicProduct {
  id: string;
  name: string;
  unit_quantity: string;
  display_price: number | null;
  image_id: string | null;
  image_url: string | null;
}

/** The live Picnic cart (ADR 0028). Amounts in EUR. */
export interface ListrPicnicCartLine {
  product_id: string;
  name: string;
  image_url: string | null;
  unit_quantity: string;
  count: number;
  price: string; // whole line, after any bundle discount
}

export interface ListrPicnicCart {
  currency: "EUR";
  mts: number; // cart version -- ordering quotes it back
  lines: ListrPicnicCartLine[];
  item_count: number;
  total: string;
  deposit: string;
  checkout_total: string;
  selected_slot_id: string | null;
  slot_chosen: boolean; // false while it's only Picnic's own preselection
}

export interface ListrPicnicSlot {
  id: string;
  window_start: string;
  window_end: string;
  cut_off: string;
  is_available: boolean;
  selected: boolean;
  minimum_order: string | null;
  unavailable_reason: string | null;
}

/** One of this week's Picnic offers (EUR). */
export interface ListrPicnicPromoProduct {
  id: string;
  name: string;
  unit_quantity: string;
  image_url: string | null;
  price: string | null;
  original_price: string | null; // struck-through price, when Picnic shows one
  label: string; // "1+1 gratis", "25% korting", "2 voor €5"
}

export interface ListrPicnicPromoSection {
  title: string;
  products: ListrPicnicPromoProduct[];
}

export interface ListrPicnicCheckout {
  order_id: string;
  transaction_id: string;
  payment_url: string; // the bank's payment page -- nothing is charged before approval there
}

export interface ListrPicnicCheckoutStatus {
  status: string;
  finished: boolean;
}

export interface ListrPicnicPushResult {
  pushed: string[];
  unmapped_item_ids: number[];
}

export interface ListrPicnicRecipeSummary {
  id: string;
  name: string;
  // SAVED_RECIPES / USER_DEFINED_RECIPES / THIS_WEEK_RECIPES / another value Picnic adds later.
  segment: string | null;
}

export interface ListrPicnicIngredientPreview {
  name: string;
  quantity: string;
  unit: string;
  // Set when this already matches an existing catalog item by name -- reused silently on
  // import. Null means importing creates a new ListrItem, which needs a category.
  matched_item_id: number | null;
  matched_item_name: string | null;
}

export interface ListrPicnicRecipePreview {
  servings: number | null;
  instructions: string;
  ingredients: ListrPicnicIngredientPreview[];
}

export interface ListrPicnicImportInput {
  name: string;
  recipe_category_ids: number[];
  // Same length/order as the preview's ingredients; only used for entries without a
  // matched_item_id.
  ingredient_category_ids: (number | null)[];
}
