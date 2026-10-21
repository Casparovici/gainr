/** Date ranges and Dutch labels for taskr's agenda. Pure and clock-free: every helper takes
 * `today` (YYYY-MM-DD) from its caller, so tests pass a fixed date instead of reading the clock.
 * The grouping itself (overdue vs. per day) comes from the backend (docs/adr/0038). */
import type { AgendaSource } from "../api/taskrTypes";
import { addDays, fromIso } from "./weekCalendar";
import { msg, t } from "../i18n";

/** The agenda's range switch. Every view is a window that starts on the selected day (today by
 * default) and runs forward: a day, 7 days, or 30 days -- so whatever slipped before the window
 * is in the "Achterstallig" list and the days that follow are all still ahead. */
export type AgendaView = "day" | "week" | "month";

export const AGENDA_VIEWS: AgendaView[] = ["day", "week", "month"];
export const AGENDA_VIEW_LABELS: Record<AgendaView, string> = { day: msg("Dag"), week: msg("Week"), month: msg("Maand") };
export const AGENDA_VIEW_DAYS: Record<AgendaView, number> = { day: 1, week: 7, month: 30 };

/** The modules' names as the agenda's badges and links show them. */
export const AGENDA_SOURCE_LABELS: Record<AgendaSource, string> = { gardnr: "gardnr", trainr: "trainr", taskr: "taskr" };

// Marked with msg() and translated where they're used, so they follow the chosen language.
const WEEKDAYS = [msg("zondag"), msg("maandag"), msg("dinsdag"), msg("woensdag"), msg("donderdag"), msg("vrijdag"), msg("zaterdag")];
const WEEKDAYS_SHORT = [msg("zo"), msg("ma"), msg("di"), msg("wo"), msg("do"), msg("vr"), msg("za")];
const MONTHS_SHORT = [
  msg("jan"), msg("feb"), msg("mrt"), msg("apr"), msg("mei"), msg("jun"),
  msg("jul"), msg("aug"), msg("sep"), msg("okt"), msg("nov"), msg("dec"),
];

/** The inclusive date range a view covers when it starts on `start`. */
export function agendaRange(view: AgendaView, start: string): { from: string; to: string } {
  return { from: start, to: addDays(start, AGENDA_VIEW_DAYS[view] - 1) };
}

/** The start of the previous (`-1`) or next (`1`) window: one whole view's length away. */
export function shiftStart(view: AgendaView, start: string, step: -1 | 1): string {
  return addDays(start, step * AGENDA_VIEW_DAYS[view]);
}

/** "14 okt", with the year only when it isn't today's year ("3 jan 2027"). Spelled out rather
 * than via Intl, whose Dutch abbreviations vary by platform ("okt." vs "okt"). */
export function shortDate(iso: string, today: string): string {
  const d = fromIso(iso);
  const year = d.getFullYear() === fromIso(today).getFullYear() ? "" : ` ${d.getFullYear()}`;
  return `${d.getDate()} ${t(MONTHS_SHORT[d.getMonth()])}${year}`;
}

/** "ma 12 okt" -- a due date in a list where the day isn't the heading (the overdue items). */
export function shortDayDate(iso: string, today: string): string {
  return `${t(WEEKDAYS_SHORT[fromIso(iso).getDay()])} ${shortDate(iso, today)}`;
}

/** A day group's heading: "Gisteren", "Vandaag" and "Morgen" by name, any other day as weekday
 * and date ("donderdag 16 okt"). */
export function dayLabel(iso: string, today: string): string {
  if (iso === today) return t("Vandaag");
  if (iso === addDays(today, 1)) return t("Morgen");
  if (iso === addDays(today, -1)) return t("Gisteren");
  return `${t(WEEKDAYS[fromIso(iso).getDay()])} ${shortDate(iso, today)}`;
}

/** The label between the previous/next arrows: the day itself for a one-day view
 * ("Vandaag · woensdag 14 okt"), otherwise the range ("14 okt – 20 okt"). */
export function rangeLabel(view: AgendaView, start: string, today: string): string {
  const { from, to } = agendaRange(view, start);
  if (view === "day") {
    const named = dayLabel(from, today);
    const full = `${t(WEEKDAYS[fromIso(from).getDay()])} ${shortDate(from, today)}`;
    return named === full ? full : `${named} · ${full}`;
  }
  return `${shortDate(from, today)} – ${shortDate(to, today)}`;
}

/** The heading of the backend's `overdue` list. That list is everything still open before the
 * range starts, which is only genuinely late when the range starts today or earlier; for a
 * window further ahead it also holds things that are still to come. */
export function overdueTitle(dateFrom: string, today: string): string {
  return dateFrom <= today ? t("Achterstallig") : t("Vóór deze periode");
}
