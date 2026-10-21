// Mirrors backend/app/schemas/briefr.py. Reports arrive from the agents repository on the server
// (docs/adr/0044); the app only reads and triages them.

/** How much a report asks of the reader -- never calmer than its most urgent finding. */
export type BriefrAttention = "act" | "watch" | "info";

/** An agent's call on one finding. */
export type BriefrVerdict = "act" | "watch" | "ignore";

export interface BriefrVerdictCounts {
  act: number;
  watch: number;
  ignore: number;
}

/** A report in the inbox list: everything but its write-up and findings. */
export interface BriefrReport {
  id: number;
  /** The agent's slug, e.g. "holdings-scan". */
  agent: string;
  /** ISO timestamp, UTC. */
  run_at: string;
  title: string;
  summary: string | null;
  attention: BriefrAttention;
  is_read: boolean;
  is_archived: boolean;
  counts: BriefrVerdictCounts;
}

export interface BriefrIngredient {
  name: string;
  /** A decimal as a string ("1.5"), or null for "zout en peper". */
  quantity: string | null;
  unit: string | null;
  note: string | null;
}

/** A recipe a finding suggests (the home chef's, docs/adr/0054), and where it stands in listr. */
export interface BriefrRecipe {
  /** The page the recipe is from. */
  url: string;
  servings: number | null;
  minutes: number | null;
  ingredients: BriefrIngredient[];
  steps: string[];
  /** The listr recipe it became, matched by its page; null until it's planned once. */
  listr_recipe_id: number | null;
  /** YYYY-MM-DD days it's planned on in the weekplanner, since the report ran. */
  planned_on: string[];
}

export interface BriefrItem {
  id: number;
  /** The ticker the agent wrote, if the finding is about one. */
  symbol: string | null;
  /** The gainr asset `symbol` resolved to, so the finding can link to its position. */
  asset_id: number | null;
  verdict: BriefrVerdict;
  headline: string;
  detail: string | null;
  /** http(s) links the finding rests on. */
  sources: string[];
  /** Set when the finding suggests a recipe that can be planned in listr. */
  recipe: BriefrRecipe | null;
}

export interface BriefrReportDetail extends BriefrReport {
  /** The file in the agents repository, e.g. "reports/holdings-scan/2026-10-19.md". */
  source_path: string;
  /** The write-up, in the journal's Markdown subset. */
  body: string;
  items: BriefrItem[];
}

export interface BriefrAgent {
  agent: string;
  last_run_at: string;
  report_count: number;
  unread_count: number;
}

export interface BriefrReportFilter {
  archived?: boolean;
  agent?: string | null;
  attention?: BriefrAttention | null;
}
