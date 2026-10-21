import { dateLocale } from "../i18n";
/** Items grouped by the calendar month of their date, in the order they came (a list sorted by
 * date stays sorted, months included). `dateOf` returns an ISO date ("2026-09-19"). */
export interface MonthGroup<T> {
  /** "2026-09" */
  key: string;
  /** "September 2026" */
  label: string;
  items: T[];
}

export function groupByMonth<T>(items: T[], dateOf: (item: T) => string): MonthGroup<T>[] {
  const groups: MonthGroup<T>[] = [];
  for (const item of items) {
    const key = dateOf(item).slice(0, 7);
    let group = groups[groups.length - 1];
    if (!group || group.key !== key) {
      group = { key, label: monthLabel(key), items: [] };
      groups.push(group);
    }
    group.items.push(item);
  }
  return groups;
}

function monthLabel(key: string): string {
  const [year, month] = key.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString(dateLocale("en-IE"), { month: "long", year: "numeric" });
}

/** "2 buys · 1 deposit": how many of each kind a group holds, most common first; `phrase` words
 * one kind's count. */
export function countSummary<T, K extends string>(items: T[], kindOf: (item: T) => K, phrase: (kind: K, n: number) => string): string {
  const counts = new Map<K, number>();
  for (const item of items) counts.set(kindOf(item), (counts.get(kindOf(item)) ?? 0) + 1);
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([kind, n]) => phrase(kind, n))
    .join(" · ");
}
