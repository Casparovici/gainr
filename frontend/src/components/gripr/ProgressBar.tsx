import { t } from "../../i18n";
/** Spend-vs-budget (or received-vs-target, for an income category) bar on every Budget tile,
 * a category's or a savings goal's. Which direction counts as "bad" flips by kind: spending
 * past a cap is bad, receiving less than a target is bad — receiving *more* than an income
 * target is a good thing, not an overrun. */
export default function ProgressBar({
  spent,
  budgeted,
  kind = "expense",
}: {
  spent: number;
  budgeted: number;
  kind?: "expense" | "income";
}) {
  if (budgeted <= 0) {
    // Wrapped in the same flex row the filled state uses (rather than a bare inline span) so
    // both states compute height the same way -- a lone inline span sits in a plain inline
    // formatting context, whose line-box height doesn't quite match a flex row's, which is what
    // made a tile with no budget set render a hair taller than one with a budget.
    return (
      <div className="flex items-center">
        <span className="text-xs text-on-surface-variant">{kind === "income" ? t("no target set") : t("no budget set")}</span>
      </div>
    );
  }
  const pct = Math.min(100, (spent / budgeted) * 100);
  const bad = kind === "income" ? spent < budgeted : spent > budgeted;
  // Material's linear progress indicator -- primary fill on a surface-variant track, switching
  // to the error role instead of a raw red when the direction that counts as "bad" is hit.
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-variant">
        <div className={`h-full rounded-full ${bad ? "bg-error" : "bg-primary"}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`shrink-0 text-xs tabular-nums ${bad ? "text-error" : "text-on-surface-variant"}`}>
        {Math.round(pct)}%
      </span>
    </div>
  );
}
