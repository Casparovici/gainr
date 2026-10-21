/** A small labelled figure on a tinted tile (Income's totals). */
export function SummaryTile({ label, value, sub, subClass }: { label: string; value: string; sub?: string; subClass?: string }) {
  return (
    <div className="rounded-2xl bg-ui-tile p-3">
      <div className="text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">{label}</div>
      <div className="mt-1 font-display text-xl font-bold tabular-nums tracking-[-0.02em] text-ui-ink">{value}</div>
      {sub && <div className={`mt-0.5 text-xs font-medium tabular-nums ${subClass ?? "text-ui-muted"}`}>{sub}</div>}
    </div>
  );
}
