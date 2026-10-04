import { useEffect, useState } from "react";

const STORAGE_PREFIX = "gainr.columns.";

function read(storageKey: string): string[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + storageKey);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((k): k is string => typeof k === "string") : null;
  } catch {
    // Blocked site data, or something else wrote nonsense under this key — fall back to
    // "everything visible" rather than failing to render the table.
    return null;
  }
}

/** Remembers which of a table's columns the reader has switched off.
 *
 * Stores the *hidden* keys, not the visible ones: a column added to the table in a later
 * version is then shown by default, instead of being silently absent for everyone who had
 * saved a preference before it existed — unless it's listed in `defaultHidden` (a niche column
 * that would otherwise clutter the table for every reader who hasn't touched their column
 * choices), in which case a first-ever visit starts with it off instead of on. Once any
 * preference is saved, it's the whole hidden set from then on — toggling the column back on
 * remembers that choice exactly like any other. */
export function useColumnVisibility<K extends string>(
  storageKey: string,
  alwaysOn: readonly K[] = [],
  defaultHidden: readonly K[] = [],
) {
  const [hidden, setHidden] = useState<Set<K>>(() => new Set((read(storageKey) ?? defaultHidden) as K[]));

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_PREFIX + storageKey, JSON.stringify([...hidden]));
    } catch {
      // Nothing to do — the table still works, the choice just won't be remembered.
    }
  }, [storageKey, hidden]);

  const isHidden = (key: K) => !alwaysOn.includes(key) && hidden.has(key);

  const toggle = (key: K) => {
    if (alwaysOn.includes(key)) return;
    setHidden((current) => {
      const next = new Set(current);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  };

  const showAll = () => setHidden(new Set());

  return { isHidden, toggle, showAll, hiddenCount: hidden.size };
}
