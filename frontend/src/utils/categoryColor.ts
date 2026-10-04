import type { GriprCategory } from "../api/griprTypes";
import { CATEGORICAL_COLORS } from "./palette";

/** Resolves every category to a display colour: the user's override if they set one, else the
 * fixed palette assigned by position within its kind (categories already arrive sorted by
 * sort_order, so this tracks whatever order Budget currently shows). A subcategory
 * always inherits its parent's resolved colour — only top-level categories are colourable. */
export function buildCategoryColorMap(categories: GriprCategory[]): Map<number, string> {
  const colors = new Map<number, string>();
  for (const kind of ["expense", "income"] as const) {
    const top = categories.filter((c) => c.kind === kind && c.parent_id === null);
    top.forEach((c, i) => colors.set(c.id, c.color ?? CATEGORICAL_COLORS[i % CATEGORICAL_COLORS.length]));
  }
  for (const c of categories) {
    if (c.parent_id !== null && colors.has(c.parent_id)) {
      colors.set(c.id, colors.get(c.parent_id)!);
    }
  }
  return colors;
}
