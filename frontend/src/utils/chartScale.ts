/** A y-axis range that leaves out one-off outliers, so a single extreme month (€35k of home equity
 * moved into savings) doesn't flatten every other month to a line. Outliers are values beyond
 * Tukey's far fences (3 × the interquartile range past the quartiles); the range covers everything
 * else, padded a little. Null when nothing is that far out: the chart keeps its own scale. */
export function cappedRange(values: number[]): { min: number; max: number } | null {
  const sorted = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (sorted.length < 4) return null;
  const quantile = (q: number) => {
    const pos = (sorted.length - 1) * q;
    const lo = Math.floor(pos);
    return sorted[lo] + (sorted[Math.ceil(pos)] - sorted[lo]) * (pos - lo);
  };
  const q1 = quantile(0.25);
  const q3 = quantile(0.75);
  const iqr = q3 - q1;
  const low = q1 - 3 * iqr;
  const high = q3 + 3 * iqr;
  const inside = sorted.filter((v) => v >= low && v <= high);
  if (inside.length === sorted.length || inside.length === 0) return null;
  const min = Math.min(0, inside[0]);
  const max = Math.max(0, inside[inside.length - 1]);
  const pad = (max - min) * 0.08 || 1;
  return { min: min < 0 ? min - pad : 0, max: max > 0 ? max + pad : 0 };
}

/** `value` pulled inside `range` (unchanged when there's no range). */
export function clampTo(value: number, range: { min: number; max: number } | null): number {
  if (!range) return value;
  return Math.min(range.max, Math.max(range.min, value));
}

/** Round axis ticks spanning [min, max] (which must straddle 0, as the put-aside chart's always do):
 * multiples of a 1/2/5 × 10^n step, so 0 is always one of them and the labels read as plain numbers
 * instead of the padded edges of the data. */
export function niceTicks(min: number, max: number, target = 5): number[] {
  const span = max - min;
  if (!(span > 0)) return [0];
  const raw = span / target;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = ([1, 2, 5, 10].find((m) => m * magnitude >= raw) ?? 10) * magnitude;
  const ticks: number[] = [];
  for (let t = Math.floor(min / step) * step; t <= Math.ceil(max / step) * step + step / 2; t += step) {
    ticks.push(Math.round(t / step) * step);
  }
  return ticks;
}
