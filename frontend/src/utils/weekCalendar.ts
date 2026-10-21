/** Date arithmetic on YYYY-MM-DD strings for the week/month planners (listr's Weekplanner, trainr's
 * Planner). Local dates throughout, never UTC, so a day near midnight stays the day it is here. */

// Dutch, as the planners were written; shown through t(), whose English is in trainr's dictionary.
// Not msg()-marked: this shared file doesn't count as Dutch for i18n.test.ts, which would then look
// these up in the English-source dictionaries.
export const WEEKDAY_LABELS = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"];

export function toIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export function fromIso(iso: string): Date {
  return new Date(iso + "T00:00:00");
}
export function addDays(iso: string, days: number): string {
  const d = fromIso(iso);
  d.setDate(d.getDate() + days);
  return toIso(d);
}
export function addMonths(iso: string, months: number): string {
  const d = fromIso(iso);
  d.setMonth(d.getMonth() + months);
  return toIso(d);
}
// Monday-based week start, regardless of what JS's Sunday-first getDay() says.
export function startOfWeek(iso: string): string {
  const day = fromIso(iso).getDay();
  return addDays(iso, day === 0 ? -6 : 1 - day);
}
export function startOfMonth(iso: string): string {
  const d = fromIso(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}
export function endOfMonth(iso: string): string {
  return addDays(addMonths(startOfMonth(iso), 1), -1);
}
export function range(startIso: string, endIso: string): string[] {
  const days: string[] = [];
  let cur = startIso;
  while (cur <= endIso) {
    days.push(cur);
    cur = addDays(cur, 1);
  }
  return days;
}
// ISO 8601 week number (weeks start on Monday; week 1 holds the year's first Thursday).
export function isoWeekNumber(iso: string): number {
  const thursday = fromIso(addDays(startOfWeek(iso), 3));
  const firstThursday = fromIso(addDays(startOfWeek(`${thursday.getFullYear()}-01-04`), 3));
  return Math.round((thursday.getTime() - firstThursday.getTime()) / (7 * 24 * 3600 * 1000)) + 1;
}
