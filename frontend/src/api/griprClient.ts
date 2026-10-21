import { uploadAll } from "../utils/attachments";
import type { AppNotification, AttachmentSource, TransactionAttachment } from "./types";
import type {
  GriprAccount,
  GriprBalanceForecast,
  GriprBankStatus,
  GriprBankSyncResult,
  GriprBankLogo,
  GriprBudgetLine,
  GriprBudgetSuggestion,
  GriprCategory,
  GriprBulkAction,
  GriprBulkResult,
  GriprCategoryAmount,
  GriprCategoryComparison,
  GriprCategoryTrendPoint,
  GriprOverview,
  GriprPortfolioLink,
  GriprDepreciationOverview,
  GriprReceivables,
  GriprRecurring,
  GriprRecurringInput,
  GriprUpcomingRecurring,
  GriprSavingsGoalLine,
  GriprSavingsGoalSuggestion,
  GriprSavingsRoom,
  GriprSettings,
  GriprSimilar,
  GriprTransaction,
  GriprTransactionInput,
  GriprTransactionPage,
  GriprTransactionType,
} from "./griprTypes";

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

export const griprApi = {
  getSettings: () => request<GriprSettings>("/gripr/settings"),
  updateSettings: (input: { period_start_day: number }) =>
    request<GriprSettings>("/gripr/settings", { method: "PUT", body: JSON.stringify(input) }),
  listPortfolioLinks: () => request<GriprPortfolioLink[]>("/gripr/portfolio-links"),
  updatePortfolioLink: (accountId: number, portfolioId: number | null) =>
    request<GriprPortfolioLink | null>(`/gripr/portfolio-links/${accountId}`, {
      method: "PUT",
      body: JSON.stringify({ portfolio_id: portfolioId }),
    }),
  syncPortfolioLinks: () => request<GriprPortfolioLink[]>("/gripr/portfolio-links/sync", { method: "POST" }),

  getBanks: () => request<GriprBankStatus>("/gripr/banks"),
  updateBank: (id: number, input: { enabled: boolean; since: string | null }) =>
    request<GriprBankStatus>(`/gripr/banks/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  mapBankAccount: (iban: string, griprAccountId: number | null) =>
    request<GriprBankStatus>(`/gripr/banks/accounts/${encodeURIComponent(iban)}`, {
      method: "PUT",
      body: JSON.stringify({ gripr_account_id: griprAccountId }),
    }),
  createBankRule: (input: {
    iban: string | null;
    text_contains: string | null;
    amount: string | null;
    amount_max: string | null;
    day_of_month: number | null;
    direction: "out" | "in" | null;
    gripr_account_id: number;
  }) =>
    request<GriprBankStatus>("/gripr/banks/rules", { method: "POST", body: JSON.stringify(input) }),
  deleteBankRule: (id: number) => request<GriprBankStatus>(`/gripr/banks/rules/${id}`, { method: "DELETE" }),
  connectBank: (id: number) => request<{ url: string }>(`/gripr/banks/${id}/connect`, { method: "POST" }),
  disconnectBank: (id: number) => request<GriprBankStatus>(`/gripr/banks/${id}/connection`, { method: "DELETE" }),
  syncBanks: () => request<GriprBankSyncResult>("/gripr/banks/sync", { method: "POST" }),
  listAccounts: (includeArchived = false) =>
    request<GriprAccount[]>(`/gripr/accounts?include_archived=${includeArchived}`),
  createAccount: (input: Partial<GriprAccount>) =>
    request<GriprAccount>("/gripr/accounts", { method: "POST", body: JSON.stringify(input) }),
  updateAccount: (id: number, input: Partial<GriprAccount>) =>
    request<GriprAccount>(`/gripr/accounts/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  reorderAccounts: (accountIds: number[]) =>
    request<void>("/gripr/accounts/reorder", { method: "PUT", body: JSON.stringify({ account_ids: accountIds }) }),
  listBankLogos: () => request<GriprBankLogo[]>("/gripr/bank-logos"),

  listCategories: (includeArchived = false) =>
    request<GriprCategory[]>(`/gripr/categories?include_archived=${includeArchived}`),
  createCategory: (input: { name: string; kind: string; parent_id?: number | null }) =>
    request<GriprCategory>("/gripr/categories", { method: "POST", body: JSON.stringify(input) }),
  updateCategory: (
    id: number,
    input: { name?: string; color?: string | null; is_archived?: boolean; linked_loan_account_id?: number | null },
  ) => request<GriprCategory>(`/gripr/categories/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteCategory: (id: number) => request<void>(`/gripr/categories/${id}`, { method: "DELETE" }),
  reorderCategories: (categoryIds: number[]) =>
    request<void>("/gripr/categories/reorder", { method: "PUT", body: JSON.stringify({ category_ids: categoryIds }) }),

  listTransactions: (params: {
    offset?: number;
    limit?: number;
    sortBy?: string;
    sortDir?: string;
    accountId?: number;
    categoryId?: number;
    type?: GriprTransactionType;
    dateFrom?: string;
    dateTo?: string;
    amountMin?: string;
    amountMax?: string;
    /** Only expenses/income/refunds still without a category -- what the bank sync leaves to file. */
    uncategorized?: boolean;
    /** Free text: notes, category or account name, or an amount. */
    search?: string;
  }) => {
    const q = new URLSearchParams();
    if (params.offset !== undefined) q.set("offset", String(params.offset));
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    if (params.sortBy) q.set("sort_by", params.sortBy);
    if (params.sortDir) q.set("sort_dir", params.sortDir);
    if (params.accountId !== undefined) q.set("account_id", String(params.accountId));
    if (params.categoryId !== undefined) q.set("category_id", String(params.categoryId));
    if (params.type) q.set("type", params.type);
    if (params.dateFrom) q.set("date_from", params.dateFrom);
    if (params.dateTo) q.set("date_to", params.dateTo);
    if (params.amountMin) q.set("amount_min", params.amountMin);
    if (params.amountMax) q.set("amount_max", params.amountMax);
    if (params.uncategorized) q.set("uncategorized", "true");
    if (params.search) q.set("q", params.search);
    return request<GriprTransactionPage>(`/gripr/transactions?${q.toString()}`);
  },
  createTransaction: (input: GriprTransactionInput) =>
    request<GriprTransaction>("/gripr/transactions", { method: "POST", body: JSON.stringify(input) }),
  updateTransaction: (id: number, input: Partial<GriprTransactionInput>) =>
    request<GriprTransaction>(`/gripr/transactions/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteTransaction: (id: number) => request<void>(`/gripr/transactions/${id}`, { method: "DELETE" }),
  bulkTransactions: (ids: number[], action: GriprBulkAction, target: { categoryId?: number; accountId?: number } = {}) =>
    request<GriprBulkResult>("/gripr/transactions/bulk", {
      method: "POST",
      body: JSON.stringify({ transaction_ids: ids, action, category_id: target.categoryId, account_id: target.accountId }),
    }),
  similarUncategorised: (id: number) => request<GriprSimilar>(`/gripr/transactions/${id}/similar`),
  applyCategoryToSimilar: (id: number) =>
    request<{ updated: number }>(`/gripr/transactions/${id}/apply-to-similar`, { method: "POST" }),

  // -- a transaction's attachments (invoices, receipts): gainr's twin, see api/client.ts.
  transactionAttachments: {
    key: "gripr",
    invalidates: [["gripr-transactions"]],
    list: (transactionId: number) => request<TransactionAttachment[]>(`/gripr/transactions/${transactionId}/attachments`),
    upload: (transactionId: number, file: File) => {
      const body = new FormData();
      body.append("file", file);
      return fetch(`/api/gripr/transactions/${transactionId}/attachments`, { method: "POST", body }).then(async (res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text().catch(() => "")}`);
        return res.json() as Promise<TransactionAttachment>;
      });
    },
    remove: (transactionId: number, attachmentId: number) =>
      request<void>(`/gripr/transactions/${transactionId}/attachments/${attachmentId}`, { method: "DELETE" }),
    url: (transactionId: number, attachmentId: number) =>
      `/api/gripr/transactions/${transactionId}/attachments/${attachmentId}`,
  } satisfies AttachmentSource,
  createTransactionWithAttachments: async (input: GriprTransactionInput, files: File[]) => {
    const transaction = await griprApi.createTransaction(input);
    return { transaction, failed: await uploadAll(griprApi.transactionAttachments, transaction.id, files) };
  },
  getDepreciation: () => request<GriprDepreciationOverview>("/gripr/depreciation"),
  listReceivables: () => request<GriprReceivables>("/gripr/receivables"),
  listNotifications: (since: string | null) =>
    request<AppNotification[]>(`/gripr/notifications${since ? `?since=${encodeURIComponent(since)}` : ""}`),
  writeOffReceivable: (transactionId: number) =>
    request<GriprReceivables>(`/gripr/receivables/${transactionId}/write-off`, { method: "POST" }),

  getBudgets: (month: string) => request<GriprBudgetLine[]>(`/gripr/budgets?month=${month}`),
  setBudget: (categoryId: number, month: string, amount: string) =>
    request<GriprBudgetLine>("/gripr/budgets", {
      method: "PUT",
      body: JSON.stringify({ category_id: categoryId, month, amount }),
    }),
  getBudgetSuggestions: (month: string) =>
    request<GriprBudgetSuggestion[]>(`/gripr/budgets/suggestions?month=${month}`),

  getSavingsGoals: (month: string) => request<GriprSavingsGoalLine[]>(`/gripr/savings-goals?month=${month}`),
  setSavingsGoal: (accountId: number, month: string, amount: string) =>
    request<GriprSavingsGoalLine>("/gripr/savings-goals", {
      method: "PUT",
      body: JSON.stringify({ account_id: accountId, month, amount }),
    }),
  getSavingsRoom: (month: string) => request<GriprSavingsRoom>(`/gripr/savings-goals/room?month=${month}`),
  getSavingsGoalSuggestions: (month: string) =>
    request<GriprSavingsGoalSuggestion[]>(`/gripr/savings-goals/suggestions?month=${month}`),

  getOverview: (month?: string, months = 12) => {
    const q = new URLSearchParams({ months: String(months) });
    if (month) q.set("month", month);
    return request<GriprOverview>(`/gripr/overview?${q.toString()}`);
  },
  getCategoryTrend: (categoryId: number, month?: string, months = 12) => {
    const q = new URLSearchParams({ category_id: String(categoryId), months: String(months) });
    if (month) q.set("month", month);
    return request<GriprCategoryTrendPoint[]>(`/gripr/overview/category-trend?${q.toString()}`);
  },
  getSubcategoryBreakdown: (categoryId: number, month?: string) => {
    const q = new URLSearchParams({ category_id: String(categoryId) });
    if (month) q.set("month", month);
    return request<GriprCategoryAmount[]>(`/gripr/overview/subcategories?${q.toString()}`);
  },
  getCategoryComparison: (categoryId: number, month?: string) => {
    const q = new URLSearchParams({ category_id: String(categoryId) });
    if (month) q.set("month", month);
    return request<GriprCategoryComparison>(`/gripr/overview/category-comparison?${q.toString()}`);
  },
  getBalanceForecast: () => request<GriprBalanceForecast>("/gripr/overview/balance-forecast"),

  listRecurring: (includeInactive = true) =>
    request<GriprRecurring[]>(`/gripr/recurring?include_inactive=${includeInactive}`),
  upcomingRecurring: () => request<GriprUpcomingRecurring>("/gripr/recurring/upcoming"),
  createRecurring: (input: GriprRecurringInput) =>
    request<GriprRecurring>("/gripr/recurring", { method: "POST", body: JSON.stringify(input) }),
  updateRecurring: (id: number, input: Partial<GriprRecurringInput & { is_active: boolean }>) =>
    request<GriprRecurring>(`/gripr/recurring/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteRecurring: (id: number) => request<void>(`/gripr/recurring/${id}`, { method: "DELETE" }),
};
