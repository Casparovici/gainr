import { useMemo, useState } from "react";

export type SortDirection = "asc" | "desc";

export interface SortState<K extends string> {
  key: K;
  direction: SortDirection;
}

/** Value a column sorts on. `null` always sinks to the bottom, whichever way the column is
 * pointing — an unpriced holding is missing data, not the smallest number in the table. */
export type SortValue = string | number | null;

export type SortAccessors<T, K extends string> = Record<K, (row: T) => SortValue>;

function compare(a: SortValue, b: SortValue, direction: SortDirection): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;

  const sign = direction === "asc" ? 1 : -1;
  if (typeof a === "number" && typeof b === "number") return (a - b) * sign;
  return String(a).localeCompare(String(b)) * sign;
}

/** Text reads naturally A–Z, money reads most-interesting-first, so a column's first click
 * should do the obvious thing rather than always starting ascending. */
function initialDirection(value: SortValue): SortDirection {
  return typeof value === "string" ? "asc" : "desc";
}

export interface TableSort<T, K extends string> {
  rows: T[];
  sort: SortState<K>;
  toggle: (key: K) => void;
  /** For the caller to move the sort itself — e.g. off a column the reader just hid, which
   * would otherwise keep ordering the table by something no longer on screen. */
  setSort: (sort: SortState<K>) => void;
}

/** Client-side sorting for a table that already has all its rows in memory (positions are a
 * few dozen at most). Returns a new array; the input order is left alone. */
export function useTableSort<T, K extends string>(
  rows: T[] | undefined,
  accessors: SortAccessors<T, K>,
  // NoInfer: the column set comes from `accessors`, otherwise a single starting key here
  // would narrow K to that one literal and reject every other column.
  initial: SortState<NoInfer<K>>,
): TableSort<T, K> {
  const [sort, setSort] = useState<SortState<K>>(initial);

  const sorted = useMemo(() => {
    if (!rows) return [];
    const accessor = accessors[sort.key];
    if (!accessor) return [...rows];
    return [...rows].sort((a, b) => compare(accessor(a), accessor(b), sort.direction));
    // `accessors` is rebuilt on every render by callers, so keying on it would defeat the memo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, sort]);

  const toggle = (key: K) =>
    setSort((current) => {
      if (current.key === key) {
        return { key, direction: current.direction === "asc" ? "desc" : "asc" };
      }
      const sample = rows?.length ? accessors[key](rows[0]) : null;
      return { key, direction: initialDirection(sample) };
    });

  return { rows: sorted, sort, toggle, setSort };
}
