import { uploadAll } from "../utils/attachments";
import type {
  AppNotification,
  AttachmentSource,
  NewsSourceCatalog,
  CalendarEvent,
  PositionCalendar,
  PositionEventInput,
  Asset,
  AssetCreateInput,
  AssetFinancials,
  PositionMetrics,
  PriceChart,
  PriceChartRange,
  AssetNews,
  Benchmark,
  BrokerStatus,
  DividendIncome,
  RebalancePlan,
  BrokerSyncResult,
  Performance,
  PerformanceRange,
  Portfolio,
  Position,
  ClosedPosition,
  Summary,
  SymbolLookup,
  Transaction,
  TransactionAttachment,
  TransactionInput,
  TransactionPage,
  TransactionType,
} from "./types";

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

export const api = {
  listPortfolios: (includeArchived = false) =>
    request<Portfolio[]>(`/portfolios?include_archived=${includeArchived}`),
  createPortfolio: (name: string) => request<Portfolio>("/portfolios", { method: "POST", body: JSON.stringify({ name }) }),
  updatePortfolio: (id: number, input: { name?: string; is_archived?: boolean }) =>
    request<Portfolio>(`/portfolios/${id}`, { method: "PUT", body: JSON.stringify(input) }),

  getSummary: (portfolioId: number) => request<Summary>(`/summary?portfolio_id=${portfolioId}`),
  getPositions: (portfolioId: number) => request<Position[]>(`/positions?portfolio_id=${portfolioId}`),
  getClosedPositions: (portfolioId: number) =>
    request<ClosedPosition[]>(`/positions/closed?portfolio_id=${portfolioId}`),
  getPerformance: (portfolioId: number, range: PerformanceRange, benchmarks: string[] = []) => {
    const q = new URLSearchParams({ portfolio_id: String(portfolioId), range });
    if (benchmarks.length) q.set("benchmarks", benchmarks.join(","));
    return request<Performance>(`/performance?${q.toString()}`);
  },
  listBenchmarks: () => request<Benchmark[]>("/performance/benchmarks"),
  getDividendIncome: (portfolioId: number) => request<DividendIncome>(`/income/dividends?portfolio_id=${portfolioId}`),
  getRebalancePlan: (portfolioId: number, amountEur: string, fromCash: boolean) =>
    request<RebalancePlan>(
      `/positions/rebalance?${new URLSearchParams({ portfolio_id: String(portfolioId), amount_eur: amountEur, from_cash: String(fromCash) })}`,
    ),

  listTransactions: (params: {
    portfolioId: number;
    offset?: number;
    limit?: number;
    sortBy?: string;
    sortDir?: string;
    assetName?: string;
    assetId?: number;
    type?: TransactionType;
    broker?: string;
    dateFrom?: string;
    dateTo?: string;
    cashMovements?: boolean;
  }) => {
    const q = new URLSearchParams({ portfolio_id: String(params.portfolioId) });
    if (params.offset !== undefined) q.set("offset", String(params.offset));
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    if (params.sortBy) q.set("sort_by", params.sortBy);
    if (params.sortDir) q.set("sort_dir", params.sortDir);
    if (params.assetName) q.set("asset_name", params.assetName);
    if (params.assetId !== undefined) q.set("asset_id", String(params.assetId));
    if (params.type) q.set("type", params.type);
    if (params.broker) q.set("broker", params.broker);
    if (params.dateFrom) q.set("date_from", params.dateFrom);
    if (params.dateTo) q.set("date_to", params.dateTo);
    if (params.cashMovements) q.set("cash_movements", "true");
    return request<TransactionPage>(`/transactions?${q.toString()}`);
  },
  listBrokers: (portfolioId: number) => request<string[]>(`/transactions/brokers?portfolio_id=${portfolioId}`),
  createTransaction: (input: TransactionInput) =>
    request<Transaction>("/transactions", { method: "POST", body: JSON.stringify(input) }),
  updateTransaction: (id: number, input: Partial<TransactionInput>) =>
    request<Transaction>(`/transactions/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteTransaction: (id: number) => request<void>(`/transactions/${id}`, { method: "DELETE" }),

  // -- a transaction's attachments (invoices): their own multipart action, not part of the JSON
  // create/update above, like gardnr's log photo.
  transactionAttachments: {
    key: "gainr",
    invalidates: [["transactions"], ["asset-transactions"]],
    list: (transactionId: number) => request<TransactionAttachment[]>(`/transactions/${transactionId}/attachments`),
    upload: (transactionId: number, file: File) => {
      const body = new FormData();
      body.append("file", file);
      return fetch(`/api/transactions/${transactionId}/attachments`, { method: "POST", body }).then(async (res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text().catch(() => "")}`);
        return res.json() as Promise<TransactionAttachment>;
      });
    },
    remove: (transactionId: number, attachmentId: number) =>
      request<void>(`/transactions/${transactionId}/attachments/${attachmentId}`, { method: "DELETE" }),
    url: (transactionId: number, attachmentId: number) => `/api/transactions/${transactionId}/attachments/${attachmentId}`,
  } satisfies AttachmentSource,
  /** A new transaction with the files picked in the form: the transaction first, then each file.
   * A file that's refused doesn't undo the transaction -- it comes back in `failed` for the caller to report. */
  createTransactionWithAttachments: async (input: TransactionInput, files: File[]) => {
    const transaction = await api.createTransaction(input);
    return { transaction, failed: await uploadAll(api.transactionAttachments, transaction.id, files) };
  },

  getAssetNews: (assetId: number) => request<AssetNews>(`/assets/${assetId}/news`),
  updateNewsSources: (assetId: number, sources: string[]) =>
    request<AssetNews>(`/assets/${assetId}/news-sources`, { method: "PUT", body: JSON.stringify({ sources }) }),
  getNewsSourceCatalog: () => request<NewsSourceCatalog>("/news-sources/catalog"),
  getAssetFinancials: (assetId: number) => request<AssetFinancials>(`/assets/${assetId}/financials`),

  getAssetMetrics: (assetId: number) => request<PositionMetrics>(`/assets/${assetId}/metrics`),
  /** A position's own price over a range, in its trading currency (docs/adr/0053). */
  getPriceChart: (assetId: number, range: PriceChartRange) =>
    request<PriceChart>(`/assets/${assetId}/prices?range=${range}`),

  getPositionCalendar: (assetId: number) => request<PositionCalendar>(`/assets/${assetId}/calendar`),
  createPositionEvent: (assetId: number, input: PositionEventInput) =>
    request<CalendarEvent>(`/assets/${assetId}/events`, { method: "POST", body: JSON.stringify(input) }),
  updatePositionEvent: (assetId: number, eventId: number, input: Partial<PositionEventInput>) =>
    request<CalendarEvent>(`/assets/${assetId}/events/${eventId}`, { method: "PUT", body: JSON.stringify(input) }),
  deletePositionEvent: (assetId: number, eventId: number) =>
    request<void>(`/assets/${assetId}/events/${eventId}`, { method: "DELETE" }),

  listAssets: () => request<Asset[]>("/assets"),
  createAsset: (input: AssetCreateInput) => request<Asset>("/assets", { method: "POST", body: JSON.stringify(input) }),
  lookupAsset: (q: string) => request<SymbolLookup>(`/assets/lookup?q=${encodeURIComponent(q)}`),
  updateAsset: (id: number, input: Partial<Asset>) =>
    request<Asset>(`/assets/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  updateAssetTargetWeight: (assetId: number, portfolioId: number, targetWeightPct: string | null) =>
    request<{ portfolio_id: number; target_weight_pct: string | null }>(`/assets/${assetId}/target-weight`, {
      method: "PUT",
      body: JSON.stringify({ portfolio_id: portfolioId, target_weight_pct: targetWeightPct }),
    }),
  listNotifications: (since: string | null) =>
    request<AppNotification[]>(`/brokers/notifications${since ? `?since=${encodeURIComponent(since)}` : ""}`),
  getTrading212: () => request<BrokerStatus>("/brokers/trading212"),
  updateTrading212: (input: { enabled: boolean; since?: string | null; portfolio_id?: number | null; cashback_account_id?: number | null }) =>
    request<BrokerStatus>("/brokers/trading212", { method: "PUT", body: JSON.stringify(input) }),
  syncTrading212: () => request<BrokerSyncResult>("/brokers/trading212/sync", { method: "POST" }),
  updateCashTargetWeight: (portfolioId: number, targetWeightPct: string | null) =>
    request<{ target_weight_pct: string | null }>(`/positions/cash-target-weight?portfolio_id=${portfolioId}`, {
      method: "PUT",
      body: JSON.stringify({ target_weight_pct: targetWeightPct }),
    }),
};
