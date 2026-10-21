import type { PositionMetric } from "../api/types";
import { formatCompactCurrency, formatPct, formatRatio, toNumber } from "./format";

/** A metric's figure as text, by its unit. Small plain numbers (an ETH/BTC ratio of 0.0316) keep
 * enough decimals to be read; large ones don't need them. */
export function formatMetricValue(metric: PositionMetric, currency: string | null): string {
  if (metric.text) return metric.text;
  const n = toNumber(metric.value);
  if (n === null) return "—";
  switch (metric.unit) {
    case "pct":
      // A fee of 0.35% or a yield of 2.98% needs its second decimal; 34.0% doesn't.
      return formatPct(n, Math.abs(n) < 10 ? 2 : 1, false);
    case "multiple":
      return formatRatio(n, 1);
    case "amount":
      return formatCompactCurrency(n, currency);
    default: {
      const digits = Math.abs(n) < 1 ? 4 : Math.abs(n) < 100 ? 2 : 0;
      return n.toLocaleString("en-IE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
    }
  }
}

/** Whether Yahoo had a figure for it. */
export function hasValue(metric: PositionMetric): boolean {
  return metric.value !== null || metric.text !== null;
}

/** "FY2023 14.6% → FY2024 12.7% → FY2025 11.1%": the trend a single latest figure can't show. */
export function formatHistory(metric: PositionMetric, currency: string | null): string | null {
  if (metric.history.length < 2) return null;
  return metric.history
    .map((point) => `${point.label.replace("FY20", "FY")} ${formatMetricValue({ ...metric, text: null, value: point.value }, currency)}`)
    .join(" → ");
}
