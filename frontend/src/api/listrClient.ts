import type {
  ListrCategory,
  ListrItem,
  ListrItemInput,
  ListrList,
  ListrListDetail,
  ListrMealPlanEntry,
  ListrMealPlanInput,
  ListrMealieImportResult,
  ListrMealiePreview,
  ListrMealieStatus,
  ListrPicnicCart,
  ListrPicnicCheckout,
  ListrPicnicCheckoutStatus,
  ListrPicnicImportInput,
  ListrPicnicOrderHistory,
  ListrPicnicPriceRefresh,
  ListrPicnicSyncResult,
  ListrPicnicSyncSettings,
  ListrPicnicSyncSettingsInput,
  ListrPicnicProduct,
  ListrPicnicPushResult,
  ListrPicnicRecipePreview,
  ListrPicnicRecipeSummary,
  ListrPicnicPromoSection,
  ListrPicnicSlot,
  ListrPicnicStatus,
  ListrPopularRecipe,
  ListrRecipe,
  ListrRecipeCategory,
  ListrRecipeInput,
} from "./listrTypes";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const listrApi = {
  listCategories: (includeArchived = false) =>
    request<ListrCategory[]>(`/listr/categories?include_archived=${includeArchived}`),
  createCategory: (name: string) =>
    request<ListrCategory>("/listr/categories", { method: "POST", body: JSON.stringify({ name }) }),
  updateCategory: (id: number, input: { color?: string | null; is_archived?: boolean }) =>
    request<ListrCategory>(`/listr/categories/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  reorderCategories: (categoryIds: number[]) =>
    request<void>("/listr/categories/reorder", {
      method: "PUT",
      body: JSON.stringify({ category_ids: categoryIds }),
    }),

  listItems: (params: { includeArchived?: boolean; categoryId?: number } = {}) => {
    const q = new URLSearchParams();
    q.set("include_archived", String(params.includeArchived ?? false));
    if (params.categoryId !== undefined) q.set("category_id", String(params.categoryId));
    return request<ListrItem[]>(`/listr/items?${q.toString()}`);
  },
  createItem: (input: ListrItemInput) =>
    request<ListrItem>("/listr/items", { method: "POST", body: JSON.stringify(input) }),
  updateItem: (id: number, input: Partial<ListrItemInput> & { is_archived?: boolean }) =>
    request<ListrItem>(`/listr/items/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  setItemPicnicMapping: (
    id: number,
    input: {
      picnic_product_id: string;
      picnic_product_name: string;
      display_price: number | null;
      unit_quantity: string | null;
      image_id: string | null;
    },
  ) =>
    request<ListrItem>(`/listr/items/${id}/picnic-mapping`, { method: "PUT", body: JSON.stringify(input) }),

  // -- inventory (see docs/adr/0015-listr-inventory.md) --------------------------------------
  listInventory: () => request<ListrItem[]>("/listr/inventory"),
  setItemInventoryTracking: (id: number, tracked: boolean) =>
    request<ListrItem>(`/listr/items/${id}/inventory`, { method: "PUT", body: JSON.stringify({ tracked }) }),
  adjustInventoryMinimum: (id: number, delta: number) =>
    request<ListrItem>(`/listr/items/${id}/inventory/minimum`, { method: "POST", body: JSON.stringify({ delta }) }),
  adjustInventoryCount: (id: number, delta: number) =>
    request<ListrItem>(`/listr/items/${id}/inventory/count`, { method: "POST", body: JSON.stringify({ delta }) }),
  addInventoryToList: (input: { item_ids: number[]; list_id?: number; new_list_name?: string }) =>
    request<ListrList>("/listr/inventory/add-to-list", { method: "POST", body: JSON.stringify(input) }),

  listLists: (includeArchived = false) =>
    request<ListrList[]>(`/listr/lists?include_archived=${includeArchived}`),
  createList: (name: string) =>
    request<ListrList>("/listr/lists", { method: "POST", body: JSON.stringify({ name }) }),
  getList: (id: number) => request<ListrListDetail>(`/listr/lists/${id}`),
  updateList: (id: number, input: { name?: string; is_archived?: boolean }) =>
    request<ListrList>(`/listr/lists/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteList: (id: number) => request<void>(`/listr/lists/${id}`, { method: "DELETE" }),
  duplicateList: (id: number, name: string) =>
    request<ListrList>(`/listr/lists/${id}/duplicate`, { method: "POST", body: JSON.stringify({ name }) }),
  clearChecked: (id: number) => request<void>(`/listr/lists/${id}/clear-checked`, { method: "POST" }),
  pushListToPicnic: (id: number) =>
    request<ListrPicnicPushResult>(`/listr/lists/${id}/push-to-picnic`, { method: "POST" }),

  addListItem: (listId: number, input: { grocery_item_id: number; quantity?: string; unit?: string | null }) =>
    request(`/listr/lists/${listId}/items`, { method: "POST", body: JSON.stringify(input) }),
  updateListItem: (
    listId: number,
    itemId: number,
    input: { quantity?: string; unit?: string; is_checked?: boolean },
  ) => request(`/listr/lists/${listId}/items/${itemId}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteListItem: (listId: number, itemId: number) =>
    request<void>(`/listr/lists/${listId}/items/${itemId}`, { method: "DELETE" }),

  listRecipes: (params: { includeArchived?: boolean; categoryId?: number } = {}) => {
    const q = new URLSearchParams();
    q.set("include_archived", String(params.includeArchived ?? false));
    if (params.categoryId !== undefined) q.set("category_id", String(params.categoryId));
    return request<ListrRecipe[]>(`/listr/recipes?${q.toString()}`);
  },
  getRecipe: (id: number) => request<ListrRecipe>(`/listr/recipes/${id}`),
  createRecipe: (input: ListrRecipeInput) =>
    request<ListrRecipe>("/listr/recipes", { method: "POST", body: JSON.stringify(input) }),
  updateRecipe: (id: number, input: Partial<ListrRecipeInput> & { is_archived?: boolean }) =>
    request<ListrRecipe>(`/listr/recipes/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteRecipe: (id: number) => request<void>(`/listr/recipes/${id}`, { method: "DELETE" }),
  addRecipeToList: (
    recipeId: number,
    input: { list_id?: number; new_list_name?: string; ingredient_ids: number[] },
  ) => request<ListrList>(`/listr/recipes/${recipeId}/add-to-list`, { method: "POST", body: JSON.stringify(input) }),

  listRecipeCategories: (includeArchived = false) =>
    request<ListrRecipeCategory[]>(`/listr/recipe-categories?include_archived=${includeArchived}`),
  createRecipeCategory: (name: string) =>
    request<ListrRecipeCategory>("/listr/recipe-categories", { method: "POST", body: JSON.stringify({ name }) }),
  updateRecipeCategory: (id: number, input: { color?: string | null; is_archived?: boolean }) =>
    request<ListrRecipeCategory>(`/listr/recipe-categories/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  reorderRecipeCategories: (categoryIds: number[]) =>
    request<void>("/listr/recipe-categories/reorder", {
      method: "PUT",
      body: JSON.stringify({ category_ids: categoryIds }),
    }),

  listMealPlan: (dateFrom: string, dateTo: string) =>
    request<ListrMealPlanEntry[]>(`/listr/meal-plan?date_from=${dateFrom}&date_to=${dateTo}`),
  setMealPlanDay: (date: string, input: ListrMealPlanInput) =>
    request<ListrMealPlanEntry>(`/listr/meal-plan/${date}`, { method: "PUT", body: JSON.stringify(input) }),
  clearMealPlanDay: (date: string) => request<void>(`/listr/meal-plan/${date}`, { method: "DELETE" }),
  getPopularRecipes: (limit = 10) =>
    request<ListrPopularRecipe[]>(`/listr/meal-plan/popular?limit=${limit}`),
  addMealPlanToList: (input: { dates: string[]; list_id?: number; new_list_name?: string }) =>
    request<ListrList>("/listr/meal-plan/add-to-list", { method: "POST", body: JSON.stringify(input) }),

  // -- picnic (see docs/adr/0011-listr-picnic-integration.md) --------------------------------
  // Mealie import (docs/adr/0022): preview reads only; import saves the food picks and upserts.
  mealieStatus: () => request<ListrMealieStatus>("/listr/mealie/status"),
  mealiePreview: () => request<ListrMealiePreview>("/listr/mealie/preview"),
  mealieImport: (mappings: { food_id: string; grocery_item_id: number }[]) =>
    request<ListrMealieImportResult>("/listr/mealie/import", { method: "POST", body: JSON.stringify({ mappings }) }),

  picnicStatus: () => request<ListrPicnicStatus>("/listr/picnic/status"),
  // Credentials are server-side already (env vars) -- this just triggers the attempt.
  picnicLogin: () => request<{ requires_2fa: boolean }>("/listr/picnic/login", { method: "POST" }),
  picnicVerify2FA: (code: string) =>
    request<void>("/listr/picnic/verify-2fa", { method: "POST", body: JSON.stringify({ code }) }),
  picnicSearch: (query: string) =>
    request<ListrPicnicProduct[]>(`/listr/picnic/search?q=${encodeURIComponent(query)}`),
  picnicOrders: () => request<ListrPicnicOrderHistory>("/listr/picnic/orders"),
  picnicSyncSettings: () => request<ListrPicnicSyncSettings>("/listr/picnic/sync-settings"),
  updatePicnicSyncSettings: (input: ListrPicnicSyncSettingsInput) =>
    request<ListrPicnicSyncSettings>("/listr/picnic/sync-settings", { method: "PUT", body: JSON.stringify(input) }),
  runPicnicSync: () => request<ListrPicnicSyncResult>("/listr/picnic/sync", { method: "POST" }),
  picnicCart: () => request<ListrPicnicCart>("/listr/picnic/cart"),
  picnicCartAdd: (productId: string, count = 1) =>
    request<ListrPicnicCart>("/listr/picnic/cart/add", { method: "POST", body: JSON.stringify({ product_id: productId, count }) }),
  picnicCartRemove: (productId: string, count = 1) =>
    request<ListrPicnicCart>("/listr/picnic/cart/remove", { method: "POST", body: JSON.stringify({ product_id: productId, count }) }),
  picnicPromotions: () => request<ListrPicnicPromoSection[]>("/listr/picnic/promotions"),
  picnicSlots: () => request<ListrPicnicSlot[]>("/listr/picnic/slots"),
  setPicnicSlot: (slotId: string) =>
    request<ListrPicnicCart>("/listr/picnic/slot", { method: "PUT", body: JSON.stringify({ slot_id: slotId }) }),
  picnicCheckout: (mts: number, returnUrl: string) =>
    request<ListrPicnicCheckout>("/listr/picnic/checkout", { method: "POST", body: JSON.stringify({ mts, return_url: returnUrl }) }),
  picnicCheckoutStatus: (transactionId: string) =>
    request<ListrPicnicCheckoutStatus>(`/listr/picnic/checkout/${encodeURIComponent(transactionId)}`),
  cancelPicnicCheckout: (transactionId: string) =>
    request<void>(`/listr/picnic/checkout/${encodeURIComponent(transactionId)}/cancel`, { method: "POST" }),
  refreshPicnicPrices: () => request<ListrPicnicPriceRefresh>("/listr/picnic/refresh-prices", { method: "POST" }),
  picnicCookbook: () => request<ListrPicnicRecipeSummary[]>("/listr/picnic/cookbook"),
  picnicRecipePreview: (recipeId: string) =>
    request<ListrPicnicRecipePreview>(`/listr/picnic/cookbook/${recipeId}`),
  picnicImportRecipe: (recipeId: string, input: ListrPicnicImportInput) =>
    request<ListrRecipe>(`/listr/picnic/cookbook/${recipeId}/import`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
};
