import { dateLocale } from "../../i18n";

/** "20 Oct 2026" -- the day a note was written, from its ISO timestamp. */
export function noteDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(dateLocale("en-IE"), { year: "numeric", month: "short", day: "numeric" });
}
