import { dateLocale, tp } from "../i18n";

export function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const n = parseFloat(value);
  return Number.isNaN(n) ? null : n;
}

// European number format throughout the UI (period thousands separator, comma decimal —
// e.g. 9.000,00) rather than US-style, matching the user's locale.
const NUMBER_LOCALE = "nl-NL";

const eurFormatter = new Intl.NumberFormat(NUMBER_LOCALE, {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 2,
});

const eurFormatterCompact = new Intl.NumberFormat(NUMBER_LOCALE, {
  style: "currency",
  currency: "EUR",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function formatEur(value: string | number | null | undefined, compact = false): string {
  const n = typeof value === "string" ? toNumber(value) : value;
  if (n === null || n === undefined) return "—";
  return (compact ? eurFormatterCompact : eurFormatter).format(n);
}

const currencyFormatterCache = new Map<string, Intl.NumberFormat>();

/** For values denominated in an asset's native currency (e.g. transaction `price`), which
 * isn't always EUR — unlike formatEur, which is only for fields the backend guarantees are EUR. */
/** "+€ 314,20" / "−€ 12,00": a change in euros, signed both ways so it reads as a move, not a
 * balance. Zero and missing read as plain "€ 0,00" and "—". */
export function formatSignedEur(value: string | number | null | undefined, compact = false): string {
  const n = typeof value === "string" ? toNumber(value) : value;
  if (n === null || n === undefined) return "—";
  const text = formatEur(Math.abs(n), compact);
  return n > 0 ? `+${text}` : n < 0 ? `−${text}` : text;
}

export function formatCurrency(value: string | number | null | undefined, currency: string | null | undefined): string {
  const n = typeof value === "string" ? toNumber(value) : value;
  if (n === null || n === undefined) return "—";
  const code = currency || "EUR";
  let formatter = currencyFormatterCache.get(code);
  if (!formatter) {
    try {
      formatter = new Intl.NumberFormat(NUMBER_LOCALE, { style: "currency", currency: code, maximumFractionDigits: 2 });
    } catch {
      formatter = eurFormatter;
    }
    currencyFormatterCache.set(code, formatter);
  }
  return formatter.format(n);
}

export function formatPct(value: string | number | null | undefined, digits = 2, signed = true): string {
  const n = typeof value === "string" ? toNumber(value) : value;
  if (n === null || n === undefined) return "—";
  const sign = signed && n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString(NUMBER_LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
}

/** For magnitudes like portfolio weight, where a leading "+" would be misleading. */
export function formatWeight(value: string | number | null | undefined, digits = 1): string {
  return formatPct(value, digits, false);
}

/** A valuation multiple (P/E, EV/EBITDA, debt/equity) — "38.1x", not a percentage or currency. */
export function formatRatio(value: string | number | null | undefined, digits = 1): string {
  const n = typeof value === "string" ? toNumber(value) : value;
  if (n === null || n === undefined) return "—";
  return `${n.toLocaleString(NUMBER_LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits })}x`;
}

/** "3,3 months" -- a runway or a duration, one decimal. */
export function formatMonths(value: string | number | null | undefined): string {
  const n = typeof value === "string" ? toNumber(value) : value;
  if (n === null || n === undefined) return "—";
  const text = n.toLocaleString(NUMBER_LOCALE, { maximumFractionDigits: 1 });
  return tp(Math.abs(n), "{text} month", "{text} months", { text });
}

export function formatQuantity(value: string | null | undefined, maximumFractionDigits = 6): string {
  const n = toNumber(value);
  if (n === null) return "—";
  return n.toLocaleString(NUMBER_LOCALE, { maximumFractionDigits });
}

/** Today as a YYYY-MM-DD string in the *local* calendar — toISOString() would answer in UTC
 * and roll the date over at the wrong moment for anyone not on it. */
export function todayIsoDate(): string {
  const now = new Date();
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
}

/** `iso` shifted by `days` (negative to go back), staying a plain local "YYYY-MM-DD" string. */
export function addDaysIso(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
}

export function formatDate(value: string, opts?: Intl.DateTimeFormatOptions): string {
  const d = new Date(value + "T00:00:00");
  return d.toLocaleDateString(dateLocale("en-IE"), opts ?? { year: "numeric", month: "short", day: "numeric" });
}

/** "14:45" -- the local clock time of a full ISO timestamp (one carrying its offset, like a
 * live quote's `price_quoted_at`). */
export function formatTime(value: string): string {
  return new Date(value).toLocaleTimeString(dateLocale("en-IE"), { hour: "2-digit", minute: "2-digit", hour12: false });
}

// -- decimal input handling -------------------------------------------------
// Form fields accept European notation ("1.234,56"), so these convert between what the
// user types and the dot-decimal strings the API expects.

/** Parses a user-typed number, accepting "1.234,56", "1234,56" or "1234.56". */
export function parseDecimalInput(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  // With a comma present it's the decimal separator, so any dots are thousands grouping.
  const normalized = trimmed.includes(",") ? trimmed.replace(/\./g, "").replace(",", ".") : trimmed;
  const n = parseFloat(normalized);
  return Number.isFinite(n) ? n : null;
}

/** Dot-decimal string for the API, from whatever the user typed. */
export function decimalInputToApi(value: string): string | null {
  const n = parseDecimalInput(value);
  return n === null ? null : String(n);
}

/** Renders a computed number back into a form field in comma-decimal notation. */
export function numberToDecimalInput(n: number): string {
  return String(Math.round(n * 1e8) / 1e8).replace(".", ",");
}

/** Existing stored values (dot-decimal, from the API) shown in a form field. */
export function apiToDecimalInput(value: string | null | undefined): string {
  return value === null || value === undefined ? "" : String(value).replace(".", ",");
}

export function pnlColorClass(value: string | number | null | undefined): string {
  const n = typeof value === "string" ? toNumber(value) : value;
  if (n === null || n === undefined || n === 0) return "text-slate-500";
  return n > 0 ? "text-emerald-600" : "text-red-600";
}

const compactCurrencyCache = new Map<string, Intl.NumberFormat>();

/** Big reported figures (revenue, cash flow) in the filer's own currency — "$ 402,8 mld".
 * Falls back to a bare compact number when the currency code is unknown, rather than
 * silently labelling a foreign figure with the wrong symbol. */
export function formatCompactCurrency(value: string | number | null | undefined, currency: string | null): string {
  const n = typeof value === "string" ? toNumber(value) : value;
  if (n === null || n === undefined) return "—";

  const key = currency ?? "";
  let formatter = compactCurrencyCache.get(key);
  if (!formatter) {
    const options: Intl.NumberFormatOptions = { notation: "compact", maximumFractionDigits: 1 };
    try {
      formatter = new Intl.NumberFormat(NUMBER_LOCALE, currency ? { ...options, style: "currency", currency } : options);
    } catch {
      formatter = new Intl.NumberFormat(NUMBER_LOCALE, options);
    }
    compactCurrencyCache.set(key, formatter);
  }
  return formatter.format(n);
}

/** "3 hours ago" for a news timestamp. Coarse on purpose — the exact minute a story landed
 * isn't the point, and a stale relative label is less misleading than a precise wrong one. */
export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const minutes = Math.round((then - Date.now()) / 60000);
  // Made per call: the language can change while the app runs.
  const relativeTimeFormatter = new Intl.RelativeTimeFormat(dateLocale("en"), { numeric: "auto" });

  if (Math.abs(minutes) < 60) return relativeTimeFormatter.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return relativeTimeFormatter.format(hours, "hour");
  return relativeTimeFormatter.format(Math.round(hours / 24), "day");
}
