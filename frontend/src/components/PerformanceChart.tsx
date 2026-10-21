import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import CollapsibleCard from "./CollapsibleCard";
import type { Benchmark, Performance, PerformanceRange } from "../api/types";
import { useTheme } from "../hooks/useTheme";
import { formatDate, formatEur, formatPct, pnlColorClass, toNumber } from "../utils/format";
import { QueryError } from "./ui/QueryError";
import { headline } from "../utils/performanceHeadline";
import { t } from "../i18n";

const RANGES: PerformanceRange[] = ["1D", "1M", "YTD", "1Y", "Max"];

const PORTFOLIO_COLOR = "#2a78d6"; // categorical slot 1 (blue)
// Fixed per benchmark, never by position — toggling one off must not repaint the others.
const BENCHMARK_COLORS: Record<string, string> = {
  sp500: "#eb6834", // slot 2 (orange)
  nasdaq: "#1baf7a", // slot 3 (aqua)
  iwda: "#eda100", // slot 4 (yellow)
};
const FALLBACK_COLOR = "#4a3aa7"; // slot 7 (violet)

const benchmarkColor = (key: string) => BENCHMARK_COLORS[key] ?? FALLBACK_COLOR;

interface ChartRow {
  date: string;
  portfolio: number | null;
  [benchmarkKey: string]: string | number | null;
}

/** Merges the portfolio series (one point per calendar day) with benchmark series (trading
 * days only), forward-filling each benchmark across the days its market was closed. When
 * benchmarks are shown everything is expressed as % return from the start of the range, so a
 * portfolio in euros and an index in points can share one axis.
 *
 * The portfolio's % comes from the backend's time-weighted series rather than from rebasing
 * `value_eur` — raw value includes deposits, which would overstate performance against an
 * index. Benchmarks have no cash flows, so rebasing their close is the same thing. */
function buildRows(performance: Performance | undefined, indexed: boolean): ChartRow[] {
  if (!performance?.points.length) return [];

  const rows: ChartRow[] = performance.points.map((p) => ({
    date: p.date,
    portfolio: indexed ? toNumber(p.return_pct) : toNumber(p.value_eur),
  }));

  for (const series of performance.benchmarks) {
    const byDate = new Map(series.points.map((p) => [p.date, toNumber(p.value)]));
    let carried: number | null = null;
    for (const row of rows) {
      const value = byDate.get(row.date);
      if (value !== undefined && value !== null) carried = value;
      row[series.key] = carried;
    }
  }

  if (!indexed) return rows;

  // Portfolio is already a % series; only the benchmarks need rebasing to the range start.
  const bases = new Map<string, number>();
  for (const series of performance.benchmarks) {
    const first = rows.find((r) => typeof r[series.key] === "number" && (r[series.key] as number) !== 0);
    if (first) bases.set(series.key, first[series.key] as number);
  }

  return rows.map((row) => {
    const rebased: ChartRow = { date: row.date, portfolio: row.portfolio };
    for (const series of performance.benchmarks) {
      const base = bases.get(series.key);
      const value = row[series.key];
      rebased[series.key] = typeof value === "number" && base ? (value / base - 1) * 100 : null;
    }
    return rebased;
  });
}

function ChartTooltip({
  active,
  payload,
  label,
  indexed,
  labels,
}: {
  active?: boolean;
  payload?: { dataKey: string; value: number; color: string }[];
  label?: string;
  indexed: boolean;
  labels: Record<string, string>;
}) {
  if (!active || !payload?.length || !label) return null;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
      <div className="mb-1 text-slate-500">{formatDate(label)}</div>
      {payload
        .filter((entry) => entry.value !== null && entry.value !== undefined)
        .map((entry) => (
          <div key={entry.dataKey} className="flex items-center gap-2 tabular-nums">
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-slate-600">{labels[entry.dataKey] ?? entry.dataKey}</span>
            <span className="ml-auto font-medium text-slate-900">
              {indexed ? formatPct(entry.value) : formatEur(entry.value)}
            </span>
          </div>
        ))}
    </div>
  );
}

export default function PerformanceChart({
  performance,
  range,
  onRangeChange,
  isLoading,
  isError = false,
  onRetry,
  benchmarks,
  activeBenchmarks,
  onToggleBenchmark,
  onOpenChange,
}: {
  performance: Performance | undefined;
  range: PerformanceRange;
  onRangeChange: (range: PerformanceRange) => void;
  isLoading: boolean;
  isError?: boolean;
  onRetry?: () => void;
  benchmarks: Benchmark[];
  activeBenchmarks: string[];
  onToggleBenchmark: (key: string) => void;
  onOpenChange?: (open: boolean) => void;
}) {
  const { isDark } = useTheme();
  // Recharts takes these as SVG props, not classes, so they can't ride the CSS dark-mode
  // overrides in index.css — they need to switch in JS instead.
  const gridColor = isDark ? "#334155" : "#e2e8f0";
  const tickColor = isDark ? "#94a3b8" : "#64748b";
  const inactiveDotColor = isDark ? "#475569" : "#cbd5e1";

  const indexed = activeBenchmarks.length > 0;
  const rows = buildRows(performance, indexed);
  const activeSeries = performance?.benchmarks ?? [];

  const labels: Record<string, string> = { portfolio: t("Portfolio") };
  for (const b of benchmarks) labels[b.key] = b.label;

  const tickFormatter = (d: string) => formatDate(d, { month: "short", day: "numeric" });
  const yTickFormatter = (v: number) => (indexed ? `${v.toFixed(0)}%` : formatEur(v, true));

  // The headline rides in the card's header rather than the body, so folding the chart away still
  // leaves the number it was illustrating on screen. It is the money-weighted return (per year once
  // the range is a year or longer, since scaling a few weeks up to a year exaggerates it); the
  // time-weighted one sits beside it, and is what the line below plots and benchmarks compare with.
  const lead = headline({
    mwr: performance?.mwr_pct ?? null,
    mwrYearly: performance?.mwr_yearly_pct ?? null,
    twr: performance?.change_pct ?? null,
  });
  const changeSummary =
    performance?.change_eur !== null && performance?.change_eur !== undefined && lead.pct !== null ? (
      <span className="flex flex-col items-end text-right tabular-nums">
        <span className={`font-display text-2xl font-bold leading-none tracking-[-0.01em] ${pnlColorClass(lead.pct)}`}>
          {lead.perYear ? t("{pct}/yr", { pct: formatPct(lead.pct) }) : formatPct(lead.pct)}
        </span>
        <span
          className="mt-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-ui-muted"
          title={lead.moneyWeighted ? t("Money-weighted return (XIRR): includes the timing of your deposits") : undefined}
        >
          {lead.moneyWeighted ? t("money-weighted") : t("time-weighted")}
        </span>
        <span className="mt-0.5 text-[13px] text-ui-muted">
          <span className={pnlColorClass(performance.change_eur)}>{formatEur(performance.change_eur)}</span> {t("over {range}", { range })}
          {lead.moneyWeighted && performance.change_pct !== null && (
            <> · <span title={t("Time-weighted return: leaves your deposits out, so it compares with a benchmark")}>{t("time-weighted {pct}", { pct: formatPct(performance.change_pct) })}</span></>
          )}
        </span>
      </span>
    ) : undefined;

  return (
    <CollapsibleCard
      storageKey="performance-chart"
      cardClassName="rounded-2xl border border-ui-border bg-ui-surface"
      title={indexed ? t("Performance vs benchmarks") : t("Portfolio value")}
      meta={changeSummary}
      onOpenChange={onOpenChange}
      info={
        <>{t("The big number is money-weighted (XIRR): what the portfolio returned on the money actually in it, so a deposit just before a rise lifts it and one just before a fall lowers it. Over a year or longer it's a yearly rate. The time-weighted return leaves your deposits and their timing out, so it compares fairly with a benchmark; the line below is time-weighted too, which is why it can end somewhere other than the big number.")}</>
      }
    >
      <div className="flex justify-end">
        <div className="flex gap-1 rounded-md bg-slate-100 p-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => onRangeChange(r)}
              className={`rounded px-2.5 py-1 text-sm font-medium transition-colors ${
                r === range ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs uppercase tracking-wide text-slate-400">{t("Compare")}</span>
        <span className="flex items-center gap-1.5 rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-600">
          <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: PORTFOLIO_COLOR }} />{t("Portfolio")}</span>
        {benchmarks.map((b) => {
          const on = activeBenchmarks.includes(b.key);
          return (
            <button
              key={b.key}
              onClick={() => onToggleBenchmark(b.key)}
              aria-pressed={on}
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${
                on ? "border-slate-300 bg-slate-50 text-slate-900" : "border-slate-200 text-slate-400 hover:text-slate-600"
              }`}
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: on ? benchmarkColor(b.key) : inactiveDotColor }}
              />
              {b.label}
            </button>
          );
        })}
      </div>

      <div className="mt-3 h-72">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">{t("Loading…")}</div>
        ) : isError ? (
          <div className="flex h-full items-center justify-center text-sm">
            <QueryError message={t("Couldn't load performance for this range.")} onRetry={onRetry} />
          </div>
        ) : rows.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">{t("No data for this range")}</div>
        ) : indexed ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={gridColor} />
              <XAxis
                dataKey="date"
                tickFormatter={tickFormatter}
                tick={{ fill: tickColor, fontSize: 12 }}
                axisLine={{ stroke: gridColor }}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis
                tick={{ fill: tickColor, fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={56}
                tickFormatter={yTickFormatter}
                domain={["auto", "auto"]}
              />
              <Tooltip content={<ChartTooltip indexed={indexed} labels={labels} />} />
              <Line
                type="monotone"
                dataKey="portfolio"
                stroke={PORTFOLIO_COLOR}
                strokeWidth={2}
                dot={false}
                connectNulls
                activeDot={{ r: 4 }}
              />
              {activeSeries.map((series) => (
                <Line
                  key={series.key}
                  type="monotone"
                  dataKey={series.key}
                  stroke={benchmarkColor(series.key)}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  activeDot={{ r: 4 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rows} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="perf-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={PORTFOLIO_COLOR} stopOpacity={0.18} />
                  <stop offset="100%" stopColor={PORTFOLIO_COLOR} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke={gridColor} />
              <XAxis
                dataKey="date"
                tickFormatter={tickFormatter}
                tick={{ fill: tickColor, fontSize: 12 }}
                axisLine={{ stroke: gridColor }}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis
                tick={{ fill: tickColor, fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={64}
                tickFormatter={yTickFormatter}
                domain={["auto", "auto"]}
              />
              <Tooltip content={<ChartTooltip indexed={indexed} labels={labels} />} />
              <Area
                type="monotone"
                dataKey="portfolio"
                stroke={PORTFOLIO_COLOR}
                strokeWidth={2}
                fill="url(#perf-fill)"
                dot={false}
                activeDot={{ r: 4, fill: PORTFOLIO_COLOR }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {indexed && (
        <p className="mt-2 text-xs text-slate-400">{t("Indexed to 0% at the start of the range. Benchmarks are index returns in their own currency, so they exclude EUR exchange-rate effects.")}</p>
      )}
    </CollapsibleCard>
  );
}
