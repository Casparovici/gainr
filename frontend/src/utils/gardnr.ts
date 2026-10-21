import { GARDEN_ACTION_LABELS, type GardenActionType } from "../api/gardnrTypes";
import { msg, t } from "../i18n";

/** Today as the backend's `date` string (YYYY-MM-DD) in the browser's own timezone -- not
 * `toISOString()`, which is UTC and turns late evening into tomorrow. */
export function todayLocalISO(now: Date = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function actionLabel(actionType: GardenActionType, customLabel: string | null): string {
  return actionType === "other" && customLabel ? customLabel : t(GARDEN_ACTION_LABELS[actionType]);
}

const NL_WEEKDAYS = [msg("zo"), msg("ma"), msg("di"), msg("wo"), msg("do"), msg("vr"), msg("za")];
const NL_MONTHS = [
  msg("jan"), msg("feb"), msg("mrt"), msg("apr"), msg("mei"), msg("jun"),
  msg("jul"), msg("aug"), msg("sep"), msg("okt"), msg("nov"), msg("dec"),
];

/** A date the way gardnr's (Dutch) screens say it, as in the redesign: a weekday for the past
 * week ("ma"), otherwise "12 sep" -- with the year only when it isn't this year ("3 apr 2027").
 * Spelled out here rather than via Intl, whose Dutch abbreviations vary by platform ("ma."); the
 * names are msg()-marked, so in English they read "Mon" and "12 Sep". */
export function gardnrDate(date: string, today: string = todayLocalISO()): string {
  const [y, m, d] = date.split("-").map(Number);
  const [ty, tm, td] = today.split("-").map(Number);
  const daysAgo = Math.round((Date.UTC(ty, tm - 1, td) - Date.UTC(y, m - 1, d)) / 86_400_000);
  if (daysAgo >= 1 && daysAgo <= 6) return t(NL_WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]);
  return `${d} ${t(NL_MONTHS[m - 1])}${y === ty ? "" : ` ${y}`}`;
}

/** How a due date reads in the UI. `isDue` matches the backend's `is_overdue` ("due today or
 * earlier", garden_care_service.is_overdue) and drives the red emphasis; the wording separates
 * today from genuinely late, so something due today no longer says "te laat sinds <today>". */
export function dueText(date: string, today: string = todayLocalISO()): { text: string; isDue: boolean } {
  if (date < today) return { text: t("te laat sinds {date}", { date: gardnrDate(date, today) }), isDue: true };
  if (date === today) return { text: t("vandaag"), isDue: true };
  return { text: t("op {date}", { date: gardnrDate(date, today) }), isDue: false };
}

/** `date` (YYYY-MM-DD) moved by `days`, computed on the calendar rather than in milliseconds so a
 * daylight-saving change can't shift it by a day. */
export function addDaysISO(date: string, days: number): string {
  const [y, m, d] = date.split("-").map(Number);
  return todayLocalISO(new Date(y, m - 1, d + days));
}

export const SOON_DAYS = 7;

/** Which Vandaag section a due date belongs in, or null if it's further out than "Binnenkort". */
export function dueBucket(date: string, today: string = todayLocalISO()): "late" | "today" | "soon" | null {
  if (date < today) return "late";
  if (date === today) return "today";
  if (date <= addDaysISO(today, SOON_DAYS)) return "soon";
  return null;
}

