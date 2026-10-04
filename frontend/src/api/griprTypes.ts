// Same convention as api/types.ts: Decimal fields come back as JSON strings, parsed with
// toNumber for display/math.

export type GriprAccountType = "checking" | "savings" | "investment" | "credit" | "loan" | "asset";

export const GRIPR_ACCOUNT_TYPES: GriprAccountType[] = [
  "checking",
  "savings",
  "investment",
  "credit",
  "loan",
  "asset",
];

export type GriprBalanceMode = "transactional" | "manual";

export interface GriprAccount {
  id: number;
  name: string;
  type: GriprAccountType;
  balance_mode: GriprBalanceMode;
  opening_balance: string;
  manual_balance: string;
  is_archived: boolean;
  balance: string;
  usage_count: number;
  color: string | null;
  bank_logo_key: string | null;
  /** Set when this account is a virtual pot whose money really sits in that account (Onderhoud
   * Auto inside Trade Republic). */
  held_in_account_id: number | null;
}

// A fixed, hand-picked catalog (not editable in the app) -- see gripr_bank_logo_service.py.
export interface GriprBankLogo {
  key: string;
  label: string;
}

export type GriprCategoryKind = "expense" | "income";

export interface GriprSettings {
  /** 1-28. The calendar day a gripr "period" (Budget, Categories, Overview) starts on --
   * default 1, meaning a period is a plain calendar month. See utils/griprPeriod.ts. */
  period_start_day: number;
}

/** One account<->gainr portfolio bridge (see docs/adr/0014, docs/adr/0021). Each side is
 * unique -- an account mirrors at most one portfolio, and vice versa. */
export interface GriprPortfolioLink {
  account_id: number;
  portfolio_id: number;
  balance: string | null;
}

/** One account a bank consent covers and the gripr account its transactions land on (null:
 * skipped). `in_consent` is false when the latest consent didn't include it. See docs/adr/0029. */
export interface GriprBankAccount {
  iban: string;
  product: string;
  holder_name: string;
  gripr_account_id: number | null;
  in_consent: boolean;
}

/** One bank read through Enable Banking (ING, Trade Republic). */
export interface GriprBankConnection {
  id: number;
  name: string;
  /** "consent": connected through Enable Banking and renewed every few months. "api_key": read
   * with a key set on the server (Trading 212) -- there's nothing to connect or renew. */
  kind: "consent" | "api_key";
  /** Sends only date, amount and direction (Trade Republic): its entries are checked against what
   * you entered rather than categorised from. */
  amount_only: boolean;
  connected: boolean;
  /** ISO datetime (UTC) the bank's consent ends -- ING 180 days, Trade Republic 90. */
  valid_until: string | null;
  enabled: boolean;
  /** Nothing dated before this is ever booked. */
  since: string | null;
  last_synced_at: string | null;
  last_error: string | null;
  accounts: GriprBankAccount[];
}

/** A counterparty that is one of the reader's own accounts -- money to or from it is booked as
 * a transfer with `gripr_account_id`. Matches when every set field matches; applies to every bank. */
export interface GriprBankRule {
  id: number;
  iban: string | null;
  text_contains: string | null;
  /** Exactly this amount (decimal string), for a bank that sends amounts only. */
  amount: string | null;
  /** At most this amount (a saveback that varies but has a ceiling); exclusive with `amount`. */
  amount_max: string | null;
  /** Narrows an amount rule to a few days around this day of the month (a savings plan). */
  day_of_month: number | null;
  /** Only money going out of / coming into the synced account; null matches either. */
  direction: "out" | "in" | null;
  gripr_account_id: number;
}

export interface GriprBankStatus {
  /** Whether this server has the Enable Banking app id, key and redirect URL set at all. */
  configured: boolean;
  connections: GriprBankConnection[];
  rules: GriprBankRule[];
}

export interface GriprBankSyncResult {
  booked: number;
  matched: number;
  fulfilled: number;
  counterparts: number;
  /** Bank name -> what went wrong there; the other banks still synced. */
  problems: Record<string, string>;
}

export interface GriprCategory {
  id: number;
  name: string;
  kind: GriprCategoryKind;
  parent_id: number | null;
  is_archived: boolean;
  color: string | null;
  /** Only meaningful on an expense category. When set, an expense filed here automatically
   * nudges this loan account's balance -- see LinkLoanAccountDialog. */
  linked_loan_account_id: number | null;
}

/** "refund" is money coming back for an expense (a friend's half of the bill, a shop refund):
 * it enters an account like income but sits under an expense category and lowers that
 * category's spend instead of counting as earnings. See docs/adr/0023. */
export type GriprTransactionType = "expense" | "income" | "transfer" | "refund";

/** Just enough of a refund's linked expense to say what it was for. */
export interface GriprRefundOf {
  id: number;
  date: string;
  amount: string;
  account_name: string | null;
  notes: string | null;
}

export interface GriprTransaction {
  id: number;
  date: string;
  type: GriprTransactionType;
  amount: string;
  account_id: number;
  counter_account_id: number | null;
  category_id: number | null;
  /** Only on a refund: the expense this money came back for, if linked. */
  refund_of_id: number | null;
  notes: string | null;
  account_name: string | null;
  counter_account_name: string | null;
  category_name: string | null;
  /** Booked automatically by a recurring rule rather than entered by hand. */
  is_recurring: boolean;
  /** On an expense: how much has come back via refunds linked to it. "0" otherwise. */
  refunded_amount: string;
  refund_of: GriprRefundOf | null;
  /** On an expense: the part fronted for others and expected back, and from whom. */
  expected_back: string | null;
  expected_from: string | null;
  /** What's still to come back: expected minus refunds so far. "0" when nothing is expected. */
  outstanding: string;
}

/** An expense with money still to come back (docs/adr/0032). */
export interface GriprReceivable {
  id: number;
  date: string;
  amount: string;
  notes: string | null;
  account_name: string | null;
  category_name: string | null;
  expected_back: string;
  expected_from: string | null;
  received: string;
  outstanding: string;
}

export interface GriprReceivables {
  total: string;
  items: GriprReceivable[];
}

export interface GriprTransactionPage {
  items: GriprTransaction[];
  total: number;
}

export type GriprTransactionInput = Omit<
  GriprTransaction,
  "id" | "account_name" | "counter_account_name" | "category_name" | "is_recurring" | "refunded_amount" | "refund_of" | "outstanding"
>;

export interface GriprBudgetLine {
  category_id: number;
  category_name: string;
  kind: GriprCategoryKind;
  budgeted: string;
  spent: string;
}

/** Three reference figures for filling in a still-empty budget/target/goal -- shared shape
 * behind GriprBudgetSuggestion and GriprSavingsGoalSuggestion so BudgetCell can render either. */
export interface GriprSuggestionFigures {
  previous_month: string;
  year_average: string;
  recurring_monthly: string;
}

export interface GriprBudgetSuggestion extends GriprSuggestionFigures {
  category_id: number;
}

export interface GriprSavingsGoalLine {
  account_id: number;
  account_name: string;
  account_type: GriprAccountType;
  budgeted: string;
  saved: string;
}

export interface GriprSavingsGoalSuggestion extends GriprSuggestionFigures {
  account_id: number;
}

export interface GriprMonthTotal {
  month: string;
  income: string;
  expense: string;
}

export interface GriprCategoryAmount {
  category_id: number;
  name: string;
  amount: string;
}

/** Net money that went into investments, savings and reservations (virtual pots) in a period. */
export interface GriprPutAsidePoint {
  month: string;
  investments: string;
  savings: string;
  reservations: string;
}

export interface GriprOverview {
  net_worth: string;
  money_put_aside: GriprPutAsidePoint[];
  income_vs_expense: GriprMonthTotal[];
  spending_by_category: GriprCategoryAmount[];
  budget_status: GriprBudgetLine[];
}

export interface GriprCategoryTrendPoint {
  month: string;
  amount: string;
}

export type GriprRecurrenceFrequency = "weekly" | "monthly" | "yearly";

export interface GriprRecurring {
  id: number;
  name: string;
  type: GriprTransactionType;
  amount: string;
  account_id: number;
  counter_account_id: number | null;
  category_id: number | null;
  notes: string | null;
  frequency: GriprRecurrenceFrequency;
  interval: number;
  start_date: string;
  end_date: string | null;
  next_due_date: string;
  is_active: boolean;
  account_name: string | null;
  counter_account_name: string | null;
  category_name: string | null;
}

/** A recurring rule's occurrence that isn't booked yet -- a projection, not a transaction. */
export interface GriprPlannedOccurrence {
  recurring_id: number;
  name: string;
  date: string;
  type: GriprTransactionType;
  amount: string;
  account_id: number;
  account_name: string | null;
  counter_account_id: number | null;
  counter_account_name: string | null;
  category_id: number | null;
}

export interface GriprUpcomingRecurring {
  /** The last day of the current period -- the projection runs up to and including it. */
  until: string;
  items: GriprPlannedOccurrence[];
}

export type GriprRecurringInput = Omit<
  GriprRecurring,
  "id" | "next_due_date" | "is_active" | "account_name" | "counter_account_name" | "category_name"
>;
