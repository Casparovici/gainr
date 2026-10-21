import { useState } from "react";

/** The groups (by id) folded away on a page, remembered under `storageKey` on this device.
 * Storage can be blocked (private windows), then every group simply starts open. */
export function readCollapsed(storageKey: string): Set<number> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(storageKey) ?? "[]");
    return new Set(Array.isArray(parsed) ? parsed.filter((v): v is number => typeof v === "number") : []);
  } catch {
    return new Set();
  }
}

function writeCollapsed(storageKey: string, collapsed: Set<number>) {
  try {
    if (collapsed.size === 0) localStorage.removeItem(storageKey);
    else localStorage.setItem(storageKey, JSON.stringify([...collapsed]));
  } catch {
    // Nothing to do: the groups still fold, they just won't be remembered.
  }
}

/** Fold and open the groups of a page (listr's list, its products). A new `storageKey` -- another
 * list -- starts from what was remembered for it. */
export function useCollapsedGroups(storageKey: string) {
  const [state, setState] = useState(() => ({ key: storageKey, collapsed: readCollapsed(storageKey) }));
  let current = state;
  if (state.key !== storageKey) {
    current = { key: storageKey, collapsed: readCollapsed(storageKey) };
    setState(current);
  }
  const { collapsed } = current;

  const change = (next: Set<number>) => {
    setState({ key: storageKey, collapsed: next });
    writeCollapsed(storageKey, next);
  };

  return {
    isOpen: (id: number) => !collapsed.has(id),
    toggle: (id: number) => {
      const next = new Set(collapsed);
      if (!next.delete(id)) next.add(id);
      change(next);
    },
    /** True when every one of `ids` is folded (and there is at least one). */
    allCollapsed: (ids: number[]) => ids.length > 0 && ids.every((id) => collapsed.has(id)),
    /** Fold all of `ids`, or open them all. */
    setAll: (ids: number[], fold: boolean) => change(fold ? new Set(ids) : new Set()),
  };
}
