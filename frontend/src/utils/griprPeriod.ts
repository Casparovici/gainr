import { dateLocale, t } from "../i18n";

/** JS port of backend/app/services/gripr_period_service.py's `period_bounds` — kept in exact
 * sync with it so the frontend never disagrees with the backend about which period a date
 * falls in. Safe with plain `Date` arithmetic (no day-of-month rollover) precisely because
 * `startDay` is capped 1-28 (enforced server-side, see GriprSettingsUpdate).
 *
 * Dates in and out are plain "YYYY-MM-DD" strings, matching every other date on the wire in
 * this app.
 */

function toDate(iso: string): Date {
  return new Date(iso + "T00:00:00");
}

function toIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function addMonths(iso: string, delta: number): string {
  const d = toDate(iso);
  d.setMonth(d.getMonth() + delta);
  return toIso(d);
}

/** The [start, end] (inclusive, both "YYYY-MM-DD") of the period `referenceIso` falls in. */
export function periodBounds(referenceIso: string, startDay: number): { start: string; end: string } {
  const ref = toDate(referenceIso);
  const day = ref.getDate();
  let start: string;
  if (day >= startDay) {
    start = `${ref.getFullYear()}-${String(ref.getMonth() + 1).padStart(2, "0")}-${String(startDay).padStart(2, "0")}`;
  } else {
    const prevMonthIso = addMonths(`${ref.getFullYear()}-${String(ref.getMonth() + 1).padStart(2, "0")}-01`, -1);
    const [y, m] = prevMonthIso.split("-");
    start = `${y}-${m}-${String(startDay).padStart(2, "0")}`;
  }
  const nextStart = addMonths(start, 1);
  const end = toIso(new Date(toDate(nextStart).getTime() - 24 * 60 * 60 * 1000));
  return { start, end };
}

/** The period containing today, as its start date — the initial state for any page's period
 * picker, replacing what used to be a page-local `currentMonth()` helper. */
export function currentPeriodStart(startDay: number): string {
  const today = toIso(new Date());
  return periodBounds(today, startDay).start;
}

/** One period forward/back from `periodStartIso`, as the new period's start date — what a
 * PeriodSwitcher's prev/next buttons call. */
export function shiftPeriod(periodStartIso: string, delta: number): string {
  return addMonths(periodStartIso, delta);
}

/** A period's number in its year: the month its end falls in, so with periods starting on the 25th,
 * 25 Dec–24 Jan is period 1 and 25 Nov–24 Dec is period 12 (and with calendar months, January is
 * period 1). The year is the end's year too. */
export function periodNumber(periodStartIso: string, startDay: number): { number: number; year: number } {
  const { end } = periodBounds(periodStartIso, startDay);
  const [year, month] = end.split("-").map(Number);
  return { number: month, year };
}

/** "P1" -- the short axis label for a period. */
export function periodLabel(periodStartIso: string, startDay: number): string {
  return `P${periodNumber(periodStartIso, startDay).number}`;
}

/** "Period 1, 2026 · 25 Dec – 24 Jan" -- what a tooltip says about a period. */
export function periodTitle(periodStartIso: string, startDay: number): string {
  const { number, year } = periodNumber(periodStartIso, startDay);
  const { start, end } = periodBounds(periodStartIso, startDay);
  const short = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString(dateLocale("en-IE"), { day: "numeric", month: "short" });
  return t("Period {number}, {year} · {start} – {end}", { number, year, start: short(start), end: short(end) });
}
