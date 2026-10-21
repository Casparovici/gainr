import { formatWeight, toNumber } from "../utils/format";
import { t } from "../i18n";

/** A holding's weight as a bar, with its target weight as a tick across it -- the allocation the
 * Home donut used to show, read row by row next to the holding it belongs to. `scale` is the
 * weight that fills the bar (the largest weight or target in the list), so bars compare across
 * rows. The figures are always written out next to it; the bar only helps the eye. */
export default function WeightBar({
  weight,
  target,
  scale,
  showTarget = true,
}: {
  weight: string | null;
  target: string | null;
  scale: number;
  showTarget?: boolean;
}) {
  const w = toNumber(weight);
  const tw = toNumber(target);
  const fill = (n: number) => `${Math.max(0, Math.min(100, scale > 0 ? (n / scale) * 100 : 0))}%`;
  const label = w === null ? "—" : `${formatWeight(weight)}${showTarget && tw !== null ? ` · ${t("target {weight}", { weight: formatWeight(target) })}` : ""}`;
  return (
    <span className="flex min-w-0 items-center gap-2.5">
      <span aria-hidden className="relative h-1.5 min-w-12 flex-1 rounded-full bg-ui-tile">
        {w !== null && <span className="absolute inset-y-0 left-0 rounded-full bg-ui-brand" style={{ width: fill(w) }} />}
        {tw !== null && <span className="absolute -inset-y-1 w-0.5 rounded-full bg-ui-ink" style={{ left: fill(tw) }} />}
      </span>
      <span className="shrink-0 whitespace-nowrap text-xs tabular-nums text-ui-muted">{label}</span>
    </span>
  );
}

/** The weight that fills a bar: the largest weight or target among `positions`. */
export function weightScale(positions: { weight_pct: string | null; target_weight_pct: string | null }[]): number {
  let max = 0;
  for (const p of positions) {
    max = Math.max(max, toNumber(p.weight_pct) ?? 0, toNumber(p.target_weight_pct) ?? 0);
  }
  return max;
}
