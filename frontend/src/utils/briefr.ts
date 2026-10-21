/** Labels for briefr's inbox. Pure and clock-free: helpers that depend on the date take `now`
 * from their caller, so tests pass a fixed moment. Times show in the browser's own time zone. */
import type { BriefrAttention, BriefrIngredient, BriefrVerdict } from "../api/briefrTypes";
import { msg, t } from "../i18n";

export const ATTENTION_LABELS: Record<BriefrAttention, string> = { act: msg("Act"), watch: msg("Watch"), info: msg("Info") };
export const VERDICT_LABELS: Record<BriefrVerdict, string> = { act: msg("Act"), watch: msg("Watch"), ignore: msg("Ignore") };
export const ATTENTIONS: BriefrAttention[] = ["act", "watch", "info"];

/** Chip colours per level: act in the late/red tone, watch in the due-today amber, the rest neutral. */
export const LEVEL_CHIP: Record<BriefrAttention | BriefrVerdict, string> = {
  act: "bg-ui-late-soft text-ui-late",
  watch: "bg-ui-today-soft text-ui-today",
  info: "bg-ui-tile text-ui-muted",
  ignore: "bg-ui-tile text-ui-muted",
};

/** "holdings-scan" -> "Holdings scan". */
export function agentLabel(agent: string): string {
  const words = agent.split("-").filter(Boolean).join(" ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const WEEKDAYS = [msg("Sun"), msg("Mon"), msg("Tue"), msg("Wed"), msg("Thu"), msg("Fri"), msg("Sat")];
const MONTHS = [msg("Jan"), msg("Feb"), msg("Mar"), msg("Apr"), msg("May"), msg("Jun"), msg("Jul"), msg("Aug"), msg("Sep"), msg("Oct"), msg("Nov"), msg("Dec")];

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/** When a report ran: "Today 02:14", "Yesterday 02:14", "Mon 13 Oct" within the week, "13 Oct"
 * this year, "13 Oct 2025" before. */
export function runLabel(iso: string, now: Date): string {
  const at = new Date(iso);
  const days = Math.round((startOfDay(now) - startOfDay(at)) / 86_400_000);
  const time = `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
  if (days === 0) return t("Today {time}", { time });
  if (days === 1) return t("Yesterday {time}", { time });
  const date = `${at.getDate()} ${t(MONTHS[at.getMonth()])}`;
  if (days > 1 && days < 7) return `${t(WEEKDAYS[at.getDay()])} ${date}`;
  return at.getFullYear() === now.getFullYear() ? date : `${date} ${at.getFullYear()}`;
}

/** A source link's site, for its label: "https://www.reuters.com/x" -> "reuters.com". */
export function sourceLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** "1 act · 2 watch", leaving out what's zero; "No findings" when all are. */
export function countsLabel(counts: Record<BriefrVerdict, number>): string {
  const parts = (["act", "watch", "ignore"] as BriefrVerdict[])
    .filter((v) => counts[v] > 0)
    .map((v) => `${counts[v]} ${t(VERDICT_LABELS[v]).toLowerCase()}`);
  return parts.length ? parts.join(" · ") : t("No findings");
}

/** A day to plan on, from today's YYYY-MM-DD: "Today", "Tomorrow", else "Mon 26 Oct". */
export function planDayLabel(iso: string, todayIso: string): string {
  const at = new Date(`${iso}T00:00:00`);
  const days = Math.round((at.getTime() - new Date(`${todayIso}T00:00:00`).getTime()) / 86_400_000);
  if (days === 0) return t("Today");
  if (days === 1) return t("Tomorrow");
  return `${t(WEEKDAYS[at.getDay()])} ${at.getDate()} ${t(MONTHS[at.getMonth()])}`;
}

/** "1,5 el sojasaus (licht)": an ingredient as a recipe writes it, with a decimal comma. */
export function ingredientLabel(ingredient: BriefrIngredient): string {
  const parts: string[] = [];
  if (ingredient.quantity !== null) parts.push(String(Number(ingredient.quantity)).replace(".", ","));
  if (ingredient.unit) parts.push(ingredient.unit);
  parts.push(ingredient.name);
  const text = parts.join(" ");
  return ingredient.note ? `${text} (${ingredient.note})` : text;
}
