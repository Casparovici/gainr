import type { Position } from "../api/types";
import { t } from "../i18n";
import { formatDate, formatTime } from "./format";

type Priced = Pick<Position, "price_date" | "price_quoted_at">;

/** The Active positions header's "prices as of …" line, or null when nothing is priced.
 *
 * Holdings legitimately carry different price dates: crypto prices around the clock, and while
 * Amsterdam is trading, New York hasn't opened yet. So the line reports the span, which also makes
 * a holding stuck days behind visible instead of silently blended in. When live quotes are in,
 * the newest one's time is shown, since an hourly quote is only meaningful with its clock time. */
export function pricesAsOfLabel(positions: Priced[], today: string): string | null {
  const dates = positions.map((p) => p.price_date).filter((d): d is string => d !== null);
  if (!dates.length) return null;
  const latest = dates.reduce((a, b) => (a > b ? a : b));
  const oldest = dates.reduce((a, b) => (a < b ? a : b));

  const quotes = positions.map((p) => p.price_quoted_at).filter((q): q is string => q !== null);
  const latestQuote = quotes.length ? quotes.reduce((a, b) => (Date.parse(a) > Date.parse(b) ? a : b)) : null;

  let head: string;
  if (latestQuote) {
    const time = formatTime(latestQuote);
    head = latest === today ? t("prices as of {time}", { time }) : t("prices as of {date}, {time}", { date: formatDate(latest), time });
  } else {
    // "Close" is only true once the day is over; a price dated today is mid-session.
    const date = formatDate(latest);
    head = latest === today || latest !== oldest ? t("prices as of {date}", { date }) : t("prices as of {date} close", { date });
  }
  return latest === oldest ? head : t("{head}, oldest {date}", { head, date: formatDate(oldest) });
}
