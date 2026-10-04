import type {
  AppNotification,
  NewsSourceCatalog,
  CalendarEvent,
  PositionCalendar,
  PositionEventInput,
  Asset,
  AssetCreateInput,
  AssetFinancials,
  AssetNews,
  Benchmark,
  BrokerStatus,
  BrokerSyncResult,
  JournalNoteInput,
  Performance,
  PerformanceRange,
  Portfolio,
  Position,
  PositionNote,
  PositionNoteInput,
  PositionNoteLabel,
  ClosedPosition,
  Summary,
  SymbolLookup,
  Transaction,
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
    return request<TransactionPage>(`/transactions?${q.toString()}`);
  },
  listBrokers: (portfolioId: number) => request<string[]>(`/transactions/brokers?portfolio_id=${portfolioId}`),
  createTransaction: (input: TransactionInput) =>
    request<Transaction>("/transactions", { method: "POST", body: JSON.stringify(input) }),
  updateTransaction: (id: number, input: Partial<TransactionInput>) =>
    request<Transaction>(`/transactions/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteTransaction: (id: number) => request<void>(`/transactions/${id}`, { method: "DELETE" }),

  getAssetNews: (assetId: number) => request<AssetNews>(`/assets/${assetId}/news`),
  updateNewsSources: (assetId: number, sources: string[]) =>
    request<AssetNews>(`/assets/${assetId}/news-sources`, { method: "PUT", body: JSON.stringify({ sources }) }),
  getNewsSourceCatalog: () => request<NewsSourceCatalog>("/news-sources/catalog"),
  getAssetFinancials: (assetId: number) => request<AssetFinancials>(`/assets/${assetId}/financials`),

  getPositionCalendar: (assetId: number) => request<PositionCalendar>(`/assets/${assetId}/calendar`),
  createPositionEvent: (assetId: number, input: PositionEventInput) =>
    request<CalendarEvent>(`/assets/${assetId}/events`, { method: "POST", body: JSON.stringify(input) }),
  updatePositionEvent: (assetId: number, eventId: number, input: Partial<PositionEventInput>) =>
    request<CalendarEvent>(`/assets/${assetId}/events/${eventId}`, { method: "PUT", body: JSON.stringify(input) }),
  deletePositionEvent: (assetId: number, eventId: number) =>
    request<void>(`/assets/${assetId}/events/${eventId}`, { method: "DELETE" }),

  listPositionNotes: (assetId: number) => request<PositionNote[]>(`/assets/${assetId}/notes`),
  createPositionNote: (assetId: number, input: PositionNoteInput) =>
    request<PositionNote>(`/assets/${assetId}/notes`, { method: "POST", body: JSON.stringify(input) }),
  updatePositionNote: (assetId: number, noteId: number, input: Partial<PositionNoteInput>) =>
    request<PositionNote>(`/assets/${assetId}/notes/${noteId}`, { method: "PUT", body: JSON.stringify(input) }),
  deletePositionNote: (assetId: number, noteId: number) =>
    request<void>(`/assets/${assetId}/notes/${noteId}`, { method: "DELETE" }),

  // -- journal (cross-position notes + labels; same rows as the position notes above) --------
  listJournalNotes: () => request<PositionNote[]>("/journal/notes"),
  createJournalNote: (input: JournalNoteInput) =>
    request<PositionNote>("/journal/notes", { method: "POST", body: JSON.stringify(input) }),
  updateJournalNote: (noteId: number, input: Partial<JournalNoteInput>) =>
    request<PositionNote>(`/journal/notes/${noteId}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteJournalNote: (noteId: number) => request<void>(`/journal/notes/${noteId}`, { method: "DELETE" }),
  listPositionNoteLabels: (includeArchived = false) =>
    request<PositionNoteLabel[]>(`/journal/labels?include_archived=${includeArchived}`),
  createPositionNoteLabel: (name: string) =>
    request<PositionNoteLabel>("/journal/labels", { method: "POST", body: JSON.stringify({ name }) }),
  updatePositionNoteLabel: (id: number, input: { name?: string; color?: string | null; is_archived?: boolean }) =>
    request<PositionNoteLabel>(`/journal/labels/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  reorderPositionNoteLabels: (labelIds: number[]) =>
    request<void>("/journal/labels/reorder", { method: "PUT", body: JSON.stringify({ label_ids: labelIds }) }),

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
  updateTrading212: (input: { enabled: boolean; since?: string | null; portfolio_id?: number | null }) =>
    request<BrokerStatus>("/brokers/trading212", { method: "PUT", body: JSON.stringify(input) }),
  syncTrading212: () => request<BrokerSyncResult>("/brokers/trading212/sync", { method: "POST" }),
  updateCashTargetWeight: (portfolioId: number, targetWeightPct: string | null) =>
    request<{ target_weight_pct: string | null }>(`/positions/cash-target-weight?portfolio_id=${portfolioId}`, {
      method: "PUT",
      body: JSON.stringify({ target_weight_pct: targetWeightPct }),
    }),
};
