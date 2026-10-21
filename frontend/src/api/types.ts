// Decimal fields come back from the backend as JSON strings (pydantic serializes Decimal
// that way) to avoid float precision loss in transit — parse with parseFloat for display/math.

export type TransactionType =
  | "Buy"
  | "Sell"
  | "Dividend"
  | "Interest"
  | "Deposit"
  | "Withdraw"
  | "Broker Fee"
  | "Staking"
  | "Transfer";

export const TRANSACTION_TYPES: TransactionType[] = [
  "Buy",
  "Sell",
  "Dividend",
  "Interest",
  "Deposit",
  "Withdraw",
  "Broker Fee",
  "Staking",
  "Transfer",
];

export interface Portfolio {
  id: number;
  name: string;
  is_archived: boolean;
}

export interface Transaction {
  id: number;
  date: string;
  type: TransactionType;
  portfolio_id: number;
  asset_id: number | null;
  quantity: string | null;
  price: string | null;
  local_value: string | null;
  fx_rate: string | null;
  value_eur: string;
  costs: string;
  total_eur: string;
  broker: string | null;
  to_broker: string | null; // only set for a Transfer -- the destination broker
  notes: string | null;
  ticker: string | null;
  asset_name: string | null;
  native_currency: string | null;
  attachment_count: number;
}

export interface TransactionAttachment {
  id: number;
  transaction_id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

/** Where a transaction's attachments live: gainr and gripr each have their own endpoints, and the
 * attachments UI is the same for both. */
export interface AttachmentSource {
  /** Namespaces the attachment list's cache entry. */
  key: string;
  /** The transaction lists to refresh after a change (they show the paperclip). */
  invalidates: string[][];
  list: (transactionId: number) => Promise<TransactionAttachment[]>;
  upload: (transactionId: number, file: File) => Promise<TransactionAttachment>;
  remove: (transactionId: number, attachmentId: number) => Promise<void>;
  url: (transactionId: number, attachmentId: number) => string;
}

export interface TransactionPage {
  items: Transaction[];
  total: number;
}

export type TransactionInput = Partial<Omit<Transaction, "id" | "ticker" | "asset_name" | "attachment_count">> & {
  date: string;
  type: TransactionType;
  portfolio_id: number;
};

export interface Asset {
  id: number;
  ticker: string;
  name: string;
  asset_class: string;
  native_currency: string;
  yahoo_symbol: string | null;
  /** How a broker's own records (Trading 212's fills and dividends) find this asset. */
  isin: string | null;
  notes: string | null;
  /** Null = no DLT coverage / not checked yet, distinct from an explicit "neutral" call. See
   * the same field on Position for where this is actually read/edited from. */
  dlt_judgment: DltJudgment | null;
}

export interface AssetCreateInput {
  ticker: string;
  name: string;
  asset_class: string;
  native_currency: string;
  yahoo_symbol?: string | null;
  /** Set when the asset is made for a Trading 212 instrument, so its records find it. */
  isin?: string | null;
}

/** One listing the price provider knows for a ticker/ISIN/name search (see AssetSymbolPicker). */
export interface SymbolMatch {
  symbol: string;
  name: string;
  exchange: string;
  quote_type: string;
}

export interface SymbolLookup {
  query: string;
  /** The query is itself a listing -- not necessarily the fund meant, hence every match shown. */
  exact: boolean;
  matches: SymbolMatch[];
}

export type DltJudgment = "attractive" | "neutral" | "critical";

export interface Position {
  asset_id: number;
  ticker: string;
  name: string;
  asset_class: string;
  quantity: string;
  avg_cost_eur: string;
  cost_basis_eur: string;
  current_price_native: string | null;
  price_date: string | null;
  /** Set when the price is the hourly live quote rather than a daily close: when that trade
   * happened (ISO, UTC). Null for a close, a fallback price, and the CASH row. */
  price_quoted_at: string | null;
  /** The move since yesterday's close, in euros (FX included) and as a share of yesterday's
   * value. Null for CASH and for a holding without a close from yesterday or before. */
  day_change_eur: string | null;
  day_change_pct: string | null;
  native_currency: string;
  market_value_eur: string | null;
  unrealized_pnl_eur: string | null;
  unrealized_pnl_pct: string | null;
  realized_pnl_eur: string;
  weight_pct: string | null;
  price_stale: boolean;
  /** De Lange Termijn's buy/hold/avoid call — usually refreshed by hand (see backend/scripts/
   * update_dlt_ratings.py) but editable from the position detail panel too. Null = no DLT
   * coverage / not checked yet, distinct from an explicit "neutral" call -- the two used to
   * always render as "Neutral" (a coalesced default), so components that display this badge
   * should still coalesce null to a neutral look; this field itself now carries the real
   * distinction so an edit control can tell them apart. */
  dlt_judgment: DltJudgment | null;
  /** Null = no target set (including for the synthetic CASH row) — distinct from an explicit
   * 0. Every target across the whole portfolio, cash included, is capped at summing to 100. */
  target_weight_pct: string | null;
  /** weight_pct - target_weight_pct: positive = overweight, negative = underweight. Null
   * whenever either side is null. */
  target_weight_diff_pct: string | null;
  /** The euro amount that difference represents, at the current total portfolio value. */
  target_weight_diff_eur: string | null;
}

export interface ClosedPosition {
  asset_id: number;
  ticker: string;
  name: string;
  asset_class: string;
  total_bought: string;
  total_sold: string;
  realized_pnl_eur: string;
  first_buy_date: string | null;
  last_sell_date: string | null;
}

export interface Summary {
  total_value_eur: string;
  cash_eur: string;
  cash_by_broker_eur: Record<string, string>;
  holdings_value_eur: string;
  ytd_return_eur: string;
  ytd_return_pct: string | null;
  /** Money-weighted (XIRR) over the year so far: the headline, with the timing of deposits in it.
   * Null when there is no such rate (no money moved, one day of history). */
  ytd_mwr_pct: string | null;
  /** Money-weighted over the whole history; `total_mwr_yearly_pct` is the same per year, given once
   * there is a year of history. */
  total_mwr_pct: string | null;
  total_mwr_yearly_pct: string | null;
  total_return_eur: string;
  total_return_pct: string | null;
  unrealized_pnl_eur: string;
  unrealized_pnl_pct: string | null;
  realized_pnl_eur: string;
  total_invested_eur: string;
  /** The portfolio's time-weighted move since yesterday's close (the chart's 1D range). */
  day_change_eur: string | null;
  day_change_pct: string | null;
  as_of: string;
}

export type PerformanceRange = "1D" | "1M" | "YTD" | "1Y" | "Max";

export interface PerformancePoint {
  date: string;
  value_eur: string;
  return_pct: string | null;
}

export interface BenchmarkPoint {
  date: string;
  value: string;
}

export interface BenchmarkSeries {
  key: string;
  label: string;
  points: BenchmarkPoint[];
}

export interface Benchmark {
  key: string;
  label: string;
}

export interface Performance {
  range: PerformanceRange;
  points: PerformancePoint[];
  start_value_eur: string | null;
  end_value_eur: string | null;
  change_eur: string | null;
  /** Time-weighted: the investments' return, deposits and their timing left out. */
  change_pct: string | null;
  /** Money-weighted (XIRR) over the same range: your timing included. Null for 1D. */
  mwr_pct: string | null;
  /** The money-weighted return per year; only for a range of a year or more. */
  mwr_yearly_pct: string | null;
  benchmarks: BenchmarkSeries[];
}

/** The ranges of a position's own price chart (docs/adr/0053). */
export type PriceChartRange = "1D" | "1W" | "1M" | "YTD" | "3Y";

export interface PriceChartPoint {
  /** An ISO date for a daily close, an ISO moment (UTC, "…Z") for an intraday bar. */
  time: string;
  /** In the position's trading currency. */
  price: string;
}

/** A position's price over a range, in the currency it trades in -- not a return. */
export interface PriceChart {
  range: PriceChartRange;
  currency: string;
  interval: "intraday" | "daily";
  points: PriceChartPoint[];
  /** What the change is measured from: yesterday's close for 1D, the first close of the range. */
  start_price: string | null;
  end_price: string | null;
  change: string | null;
  change_pct: string | null;
  /** 1D was asked for but there are no intraday prices: the points are the last week's closes. */
  is_fallback: boolean;
  /** When the last point was traded (ISO, UTC), for a live or intraday price. */
  as_of: string | null;
}

export interface DividendMonth {
  /** YYYY-MM */
  month: string;
  received_eur: string;
  /** Last 12 months' payments per share times the shares held now. */
  expected_eur: string;
}

export interface DividendYear {
  year: number;
  total_eur: string;
  /** January..December */
  months: string[];
}

export interface DividendHolding {
  asset_id: number;
  ticker: string;
  name: string;
  is_held: boolean;
  received_total_eur: string;
  received_12m_eur: string;
  payments_12m: number;
  expected_12m_eur: string;
  last_paid_on: string | null;
  yield_on_cost_pct: string | null;
  current_yield_pct: string | null;
}

export interface DividendIncome {
  as_of: string;
  received_this_year_eur: string;
  received_last_year_eur: string;
  received_12m_eur: string;
  expected_12m_eur: string;
  paying_holdings: number;
  yield_on_cost_pct: string | null;
  current_yield_pct: string | null;
  /** The last 12 months received (this one included), then the next 12 expected. */
  months: DividendMonth[];
  /** Newest first. */
  years: DividendYear[];
  holdings: DividendHolding[];
}

export interface RebalancePurchase {
  /** 0 = cash */
  asset_id: number;
  ticker: string;
  name: string;
  /** Always attractive or neutral (only those are bought); null for cash. */
  dlt_judgment: DltJudgment | null;
  amount_eur: string;
  quantity: string | null;
  weight_before_pct: string;
  weight_after_pct: string;
  target_pct: string;
}

export interface RebalancePlan {
  amount_eur: string;
  from_cash: boolean;
  cash_eur: string;
  purchases: RebalancePurchase[];
  /** Holdings that get none of the amount; they still count towards the total. */
  left_out: RebalanceLeftOut[];
}

export interface RebalanceLeftOut {
  name: string;
  dlt_judgment: DltJudgment | null;
  reason: "critical" | "unrated" | "no_target";
}

export interface NewsItem {
  title: string;
  summary: string;
  publisher: string;
  url: string;
  published_at: string;
  /** Label of the extra news source this came from ("Aerospace & Defense"); null for the
   * position's own news. */
  source: string | null;
}

/** An extra news feed a position pulls in: "sector:<key>", "industry:<key>" or
 * "ticker:<symbol>" (docs/adr/0026). */
export interface NewsSource {
  key: string;
  label: string;
}

export interface AssetNews {
  window_days: number;
  items: NewsItem[];
  sources: NewsSource[];
}

export interface NewsSourceCatalog {
  markets: NewsSource[];
  sectors: NewsSource[];
  industries: (NewsSource & { sector: string })[];
}

export interface FinancialPeriod {
  label: string;
  period_end: string;
  revenue: string | null;
  revenue_growth_pct: string | null;
  free_cash_flow: string | null;
  net_income: string | null;
  net_margin_pct: string | null;
  /** Banks only: operating expenses / total income for the period -- lower is better. */
  cost_income_pct: string | null;
}

/** A point-in-time valuation/quality snapshot — as of whenever the provider last quoted it,
 * never blended with the reported-period figures in AssetFinancials. */
export interface KeyMetrics {
  pe_ratio: string | null;
  forward_pe_ratio: string | null;
  price_to_fcf: string | null;
  ev_to_ebitda: string | null;
  gross_margin_pct: string | null;
  operating_margin_pct: string | null;
  net_margin_pct: string | null;
  return_on_equity_pct: string | null;
  debt_to_equity: string | null;
  /** In AssetFinancials.currency. */
  net_cash: string | null;
  dividend_yield_pct: string | null;
  payout_ratio_pct: string | null;
}

export interface AssetFinancials {
  /** The filer's reporting currency — not converted to EUR, and often not the trading currency. */
  currency: string | null;
  quarter: FinancialPeriod | null;
  annual: FinancialPeriod[];
  key_metrics: KeyMetrics | null;
}

export interface MetricHistoryPoint {
  label: string;
  value: string;
}

/** One line of a position's analyst checklist. No value and no text means Yahoo doesn't carry
 * it: source_hint says where to look instead. */
export interface PositionMetric {
  key: string;
  label: string;
  unit: "pct" | "multiple" | "amount" | "number" | "text";
  /** Why the metric matters for this holding. */
  why: string | null;
  value: string | null;
  /** For a metric that is a list rather than a figure (largest holdings). */
  text: string | null;
  detail: string | null;
  /** Oldest first. */
  history: MetricHistoryPoint[];
  source_hint: string | null;
}

export interface PositionMetrics {
  /** "Growth company"; null when the position has no checklist. */
  lens: string | null;
  /** For the "amount" metrics; never converted to euros. */
  currency: string | null;
  metrics: PositionMetric[];
}

// -- position calendar (docs/adr/0025) --------------------------------------------------------

/** Kinds the user can add by hand -- Yahoo only knows earnings and dividends. */
export type PositionEventKind = "investor_day" | "capital_markets_day" | "agm" | "product_event" | "other";

export type CalendarEventKind = "earnings" | "ex_dividend" | "dividend_payment" | PositionEventKind;

export interface CalendarEvent {
  /** Only on events the user added; Yahoo's dates can't be edited. */
  id: number | null;
  source: "yahoo" | "manual";
  kind: CalendarEventKind;
  date: string;
  /** Set when Yahoo only knows a window, not the day. */
  end_date: string | null;
  title: string;
  is_estimate: boolean;
  time_of_day: "before_open" | "after_close" | null;
  /** Earnings only: consensus for the quarter, in PositionCalendar.currency. */
  eps_estimate: string | null;
  revenue_estimate: string | null;
  notes: string | null;
}

export interface EarningsResult {
  report_date: string;
  eps_estimate: string | null;
  eps_actual: string | null;
  /** Positive = beat, as a percentage of the estimate. */
  surprise_pct: string | null;
}

export interface PositionCalendar {
  /** Of the EPS/revenue figures -- the company's reporting currency, never converted. */
  currency: string | null;
  upcoming: CalendarEvent[];
  past: CalendarEvent[];
  results: EarningsResult[];
}

export interface PositionEventInput {
  date: string;
  kind: PositionEventKind;
  title: string;
  notes: string | null;
}


/** An instrument Trading 212 has records for that no asset has the ISIN of -- held back until one
 * is linked. */
export interface BrokerUnmapped {
  isin: string;
  ticker: string;
  name: string;
  currency: string;
  records: number;
  first_date: string;
}

/** gainr's Trading 212 sync (docs/adr/0031): fills, dividends and a weekly interest/cashback
 * deposit into one portfolio. */
export interface BrokerStatus {
  /** A Trading 212 API key is set on the server. */
  configured: boolean;
  enabled: boolean;
  since: string | null;
  portfolio_id: number | null;
  /** The gripr account Trading 212's cashback is booked into; null = it stays in the weekly deposit. */
  cashback_account_id: number | null;
  last_synced_at: string | null;
  last_error: string | null;
  unmapped: BrokerUnmapped[];
}

export interface BrokerSyncResult {
  booked: number;
  matched: number;
  deposits: number;
  cashbacks: number;
  unmapped: BrokerUnmapped[];
  problems: string[];
}

/** Something worth mentioning since this device last opened a module's bell (gripr's and gainr's
 * share this shape). */
export interface AppNotification {
  key: string;
  kind: "synced" | "money_back" | "still_owed" | "bank" | "broker" | "unmapped";
  /** ISO datetime (UTC) this became news -- after the device's last look means it's new. */
  at: string;
  title: string;
  detail: string | null;
  /** Where to act on it, within the app. */
  link: string;
}
