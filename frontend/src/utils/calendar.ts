import { t } from "../i18n";
import { todayIsoDate } from "./format";

/** Whole calendar days from `today` to `iso` (both YYYY-MM-DD), negative for the past. Computed
 * on the dates alone, so a daylight-saving change in between can't knock it off by one. */
export function daysUntil(iso: string, today: string = todayIsoDate()): number {
  const toUtc = (d: string) => {
    const [y, m, day] = d.split("-").map(Number);
    return Date.UTC(y, m - 1, day);
  };
  return Math.round((toUtc(iso) - toUtc(today)) / 86_400_000);
}

/** "today", "tomorrow", "in 5 days", "in 4 weeks", "in 3 months" -- coarser the further out,
 * since nobody plans around "in 47 days". */
export function formatCountdown(days: number): string {
  if (days <= 0) return t("today");
  if (days === 1) return t("tomorrow");
  // Always two or more from here on, so the plural alone.
  if (days < 14) return t("in {n} days", { n: days });
  if (days < 60) return t("in {n} weeks", { n: Math.round(days / 7) });
  return t("in {n} months", { n: Math.round(days / 30) });
}
