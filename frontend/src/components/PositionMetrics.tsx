import type { PositionMetrics } from "../api/types";
import { formatHistory, formatMetricValue, hasValue } from "../utils/positionMetrics";
import { t } from "../i18n";

/** The position's analyst checklist (the Metrics tab): what decides how this holding is judged,
 * filled in from Yahoo where it has the figure. Anything it doesn't carry stays on the list,
 * marked and with a hint on where to look, so a gap reads as a gap. */
export default function PositionMetricsSection({ data }: { data: PositionMetrics }) {
  const found = data.metrics.filter(hasValue).length;

  return (
    <div>
      <p className="mb-3 text-sm text-slate-600">
        {data.lens && <span className="font-medium text-slate-900">{data.lens}</span>}
        {data.lens && " · "}
        {found}{" "}{t("of {length} from Yahoo", { length: data.metrics.length })}</p>
      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
        {data.metrics.map((metric) => {
          const available = hasValue(metric);
          const history = formatHistory(metric, data.currency);
          return (
            <li key={metric.key} className="flex items-start justify-between gap-3 px-3 py-2.5">
              <div className="min-w-0">
                <div className={`text-sm ${available ? "font-medium text-slate-900" : "text-slate-500"}`}>{metric.label}</div>
                {metric.why && <div className="text-xs text-slate-400">{metric.why}</div>}
                {history && <div className="mt-0.5 text-xs tabular-nums text-slate-500">{history}</div>}
                {metric.detail && <div className="mt-0.5 text-xs text-slate-400">{metric.detail}</div>}
                {!available && metric.source_hint && (
                  <div className="mt-0.5 text-xs text-slate-400">{t("Look in:")}{" "}{metric.source_hint}</div>
                )}
              </div>
              <div className="shrink-0 text-right">
                {available ? (
                  <span
                    className={`text-sm font-semibold ${metric.unit === "text" ? "block max-w-[14rem] text-left text-xs font-medium" : "tabular-nums"} text-slate-900`}
                  >
                    {formatMetricValue(metric, data.currency)}
                  </span>
                ) : (
                  <span className="text-xs text-slate-400">{t("Not on Yahoo")}</span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs leading-relaxed text-slate-400">{t("Amounts")}{data.currency ? ` ${t("are in {currency}", { currency: data.currency })}` : ""}
{" "}{t("as reported, not converted to euros.")}{data.metrics.some((m) => m.history.length > 1) &&
          ` ${t("Yearly trends come from the annual statements; the latest growth and margin figures are Yahoo's snapshot, so they can differ slightly from the last full year.")}`}
      </p>
    </div>
  );
}
