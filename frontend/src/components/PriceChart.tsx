import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api/client";
import type { PriceChart as PriceChartData, PriceChartRange } from "../api/types";
import { useTheme } from "../hooks/useTheme";
import { formatCurrency, formatDate, formatPct, formatTime, pnlColorClass, toNumber } from "../utils/format";
import { QueryError } from "./ui/QueryError";
import { t } from "../i18n";

const RANGES: PriceChartRange[] = ["1D", "1W", "1M", "YTD", "3Y"];

const UP = "#059669";
const DOWN = "#dc2626";

interface Row {
  time: string;
  price: number;
}

function toRows(chart: PriceChartData): Row[] {
  return chart.points.flatMap((p) => {
    const price = toNumber(p.price);
    return price === null ? [] : [{ time: p.time, price }];
  });
}

/** A position's own price over 1D, 1W, 1M, YTD or 3Y, in the currency it trades in (docs/adr/0053):
 * the price, not a return, so it says what the share cost then and now. The 1D range is the last
 * session through the day and its change is the day's move from the previous close; the rest are
 * daily closes, with today's live quote at the end while there is a current one. */
export default function PriceChart({ assetId, enabled }: { assetId: number; enabled: boolean }) {
  const [range, setRange] = useState<PriceChartRange>("1M");
  const { isDark } = useTheme();
  const query = useQuery({
    queryKey: ["price-chart", assetId, range],
    queryFn: () => api.getPriceChart(assetId, range),
    enabled,
    // A day's bars and a quote barely move within a minute, so flicking between ranges and back is free.
    staleTime: 60_000,
  });
  const chart = query.data;
  const rows = chart ? toRows(chart) : [];
  const intraday = chart?.interval === "intraday";
  const rising = (toNumber(chart?.change ?? null) ?? 0) >= 0;
  const color = rising ? UP : DOWN;
  const gridColor = isDark ? "#334155" : "#e2e8f0";
  const tickColor = isDark ? "#94a3b8" : "#64748b";

  const tick = (time: string) =>
    intraday
      ? formatTime(time)
      : formatDate(time, range === "3Y" ? { month: "short", year: "2-digit" } : { month: "short", day: "numeric" });

  return (
    <section aria-label={t("Price")} className="mt-4 rounded-lg border border-slate-200 bg-white px-3 pb-3 pt-3">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="min-w-0">
          {chart && chart.end_price !== null ? (
            <>
              <div className="text-xl font-semibold tabular-nums text-slate-900">{formatCurrency(chart.end_price, chart.currency)}</div>
              <div className="text-sm tabular-nums">
                <span className={pnlColorClass(chart.change)}>
                  {formatCurrency(chart.change, chart.currency)} ({formatPct(chart.change_pct)})
                </span>{" "}
                <span className="text-slate-500">
                  {chart.range === "1D" && !chart.is_fallback ? t("today") : t("over {range}", { range: chart.is_fallback ? "1W" : chart.range })}
                </span>
              </div>
            </>
          ) : (
            <div className="h-[3.25rem]" />
          )}
        </div>
        <div role="group" aria-label={t("Range")} className="flex shrink-0 rounded-lg bg-slate-100 p-0.5">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={range === r}
              onClick={() => setRange(r)}
              className={`h-8 min-w-[2.5rem] rounded-md px-2 text-[13px] font-semibold ${
                range === r ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-2">
        {query.isLoading ? (
          <div className="h-44 animate-pulse rounded-lg bg-slate-100" />
        ) : query.isError ? (
          <QueryError message={t("Couldn't load the price chart.")} onRetry={() => void query.refetch()} />
        ) : rows.length < 2 ? (
          <p className="m-0 py-10 text-center text-sm text-slate-500">
            {rows.length === 0 ? t("No price history for this position.") : t("Not enough prices to draw this range yet.")}
          </p>
        ) : (
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id={`price-fill-${rising ? "up" : "down"}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={0.22} />
                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={gridColor} vertical={false} />
                <XAxis
                  dataKey="time"
                  tickFormatter={tick}
                  tick={{ fill: tickColor, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={44}
                  interval="preserveStartEnd"
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fill: tickColor, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  width={46}
                  tickFormatter={(v: number) => v.toLocaleString("nl-NL", { maximumFractionDigits: v >= 100 ? 0 : 2 })}
                />
                {intraday && chart?.start_price && toNumber(chart.start_price) !== null && (
                  // Yesterday's close, so the day's move reads against a line.
                  <ReferenceLine y={toNumber(chart.start_price) ?? undefined} stroke={tickColor} strokeDasharray="4 4" />
                )}
                <Tooltip
                  cursor={{ stroke: tickColor, strokeDasharray: "3 3" }}
                  content={({ active, payload }) => {
                    const row = active ? (payload?.[0]?.payload as Row | undefined) : undefined;
                    if (!row || !chart) return null;
                    return (
                      <div className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-sm">
                        <div className="text-slate-500">{intraday ? `${formatTime(row.time)}` : formatDate(row.time)}</div>
                        <div className="font-semibold tabular-nums text-slate-900">{formatCurrency(row.price, chart.currency)}</div>
                      </div>
                    );
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="price"
                  stroke={color}
                  strokeWidth={2}
                  fill={`url(#price-fill-${rising ? "up" : "down"})`}
                  dot={false}
                  activeDot={{ r: 3 }}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {chart?.is_fallback && (
        <p className="m-0 mt-1 text-xs text-slate-500">{t("Intraday prices aren't available right now; showing the last week's closes.")}</p>
      )}
      {chart?.as_of && !query.isLoading && (
        <p className="m-0 mt-1 text-xs text-slate-400">{t("Last price {time}", { time: formatTime(chart.as_of) })}</p>
      )}
    </section>
  );
}
