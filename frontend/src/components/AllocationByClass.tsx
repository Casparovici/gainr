import type { Position } from "../api/types";
import { formatWeight, toNumber } from "../utils/format";
import { msg, t } from "../i18n";

// What `asset_class` encodes, in words (it isn't a sector breakdown: see the analyst notes).
const CLASS_LABELS: Record<string, string> = {
  equity: msg("Stocks & ETFs"),
  crypto: msg("Crypto"),
  commodity: msg("Commodities"),
  cash: msg("Cash"),
};
// Tones of the module's brand for the bar, darkest for the biggest slice; meaning is in the
// legend's words and figures, never in the colour alone.
const TONES = ["bg-ui-brand", "bg-ui-brand/60", "bg-ui-brand/35", "bg-ui-brand/20", "bg-ui-ink/25"];

/** The portfolio split by kind of holding -- one stacked bar and its legend, where Home used to
 * show a donut of every holding (each holding's own weight is now on its row). */
export default function AllocationByClass({ positions }: { positions: Position[] | undefined }) {
  const byClass = new Map<string, number>();
  for (const p of positions ?? []) {
    const weight = toNumber(p.weight_pct);
    if (weight === null || weight <= 0) continue;
    byClass.set(p.asset_class, (byClass.get(p.asset_class) ?? 0) + weight);
  }
  const slices = [...byClass.entries()].sort((a, b) => b[1] - a[1]);

  return (
    <section aria-label={t("Allocation")} className="rounded-2xl border border-ui-border bg-ui-surface px-4 py-3.5">
      <h2 className="m-0 mb-3 text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">{t("Allocation")}</h2>
      {positions === undefined ? (
        <div className="h-16 animate-pulse rounded-xl bg-ui-tile" />
      ) : slices.length === 0 ? (
        <p className="m-0 text-sm text-ui-muted">{t("Nothing held yet.")}</p>
      ) : (
        <>
          <div aria-hidden className="flex h-3.5 gap-0.5 overflow-hidden rounded-full">
            {slices.map(([cls, weight], i) => (
              <span key={cls} className={TONES[Math.min(i, TONES.length - 1)]} style={{ width: `${weight}%` }} />
            ))}
          </div>
          <ul className="m-0 mt-3 grid list-none grid-cols-2 gap-x-3 lg:grid-cols-1 gap-y-1.5 p-0 text-[13px]">
            {slices.map(([cls, weight], i) => (
              <li key={cls} className="flex items-center gap-1.5 text-ui-ink">
                <span aria-hidden className={`h-2.5 w-2.5 shrink-0 rounded-sm ${TONES[Math.min(i, TONES.length - 1)]}`} />
                <span className="truncate">{CLASS_LABELS[cls] ? t(CLASS_LABELS[cls]) : cls}
</span>
                <span className="ml-auto tabular-nums text-ui-muted">{formatWeight(weight)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
