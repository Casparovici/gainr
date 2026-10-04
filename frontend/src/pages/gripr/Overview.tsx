import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { griprApi } from "../../api/griprClient";
import PeriodSwitcher from "../../components/gripr/PeriodSwitcher";
import { ModuleTopRow, PageTitle } from "../../components/ui/kit";
import InfoHeading from "../../components/ui/InfoTip";
import { cappedRange, clampTo } from "../../utils/chartScale";
import { useTheme } from "../../hooks/useTheme";
import { formatEur, pnlColorClass, toNumber } from "../../utils/format";
import { CATEGORICAL_COLORS, OTHER_COLOR } from "../../utils/palette";
import { completedPeriodAverage } from "../../utils/griprAverages";
import { currentPeriodStart, periodLabel, periodTitle } from "../../utils/griprPeriod";

// Fixed palette order (blue, orange, aqua), each line labelled in the legend with its figure.
const PUT_ASIDE_SERIES = [
  { key: "Investments", color: CATEGORICAL_COLORS[0] },
  { key: "Savings", color: CATEGORICAL_COLORS[1] },
  { key: "Reservations", color: CATEGORICAL_COLORS[2] },
] as const;
const INCOME_COLOR = "#1baf7a"; // aqua — same slot spending-by-category never reassigns
const EXPENSE_COLOR = "#e34948"; // red
const MAX_CATEGORY_BARS = 7;

const selectClass =
  "rounded-md border border-outline px-2.5 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

/** Props for a series' average as a quiet background reference: a thin dashed line in the
 * series' own colour (dashing marks it as a reference, not data or a gridline). Its value is
 * named in the legend below the chart rather than on the plot, where two averages close together
 * would collide. Props rather than a wrapper component: Recharts only draws chart elements that
 * are its own direct children, so a <ReferenceLine> inside a custom component silently vanishes. */
function averageLineProps(value: number, color: string) {
  return { y: value, stroke: color, strokeWidth: 1, strokeDasharray: "4 4", strokeOpacity: 0.7, ifOverflow: "extendDomain" as const };
}

/** A legend entry for an average line: a short dashed swatch plus its value, in text colours. */
function AverageLegend({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <svg width="14" height="2" aria-hidden>
        <line x1="0" y1="1" x2="14" y2="1" stroke={color} strokeWidth="2" strokeDasharray="3 2" />
      </svg>
      {label} <span className="tabular-nums text-on-surface">{formatEur(value)}</span>
    </span>
  );
}

type TooltipEntry = { name: string; value: number; color: string; dataKey?: string; payload?: { real?: Record<string, number>; title?: string } };

/** Shows each series' real value -- also for a point drawn at the edge of a capped scale. */
function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipEntry[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-high px-3 py-2 text-xs shadow-sm">
      {(payload[0].payload?.title ?? label) && <div className="mb-1 font-medium text-on-surface">{payload[0].payload?.title ?? label}</div>}
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
          <span className="text-on-surface-variant">{p.name}:</span>
          <span className="font-medium text-on-surface">{formatEur(p.payload?.real?.[p.dataKey ?? ""] ?? p.value)}</span>
        </div>
      ))}
    </div>
  );
}

type OffScaleDotProps = { cx?: number; cy?: number; index?: number; value?: number; payload?: { real?: Record<string, number> } };

/** Nothing for an ordinary point; for one drawn at the edge of a capped scale, a small arrow in the
 * series' colour and its real amount in the axis ink, so the outlier is still read correctly. */
function OffScaleDot({ cx, cy, value, payload, seriesKey, color, textColor }: OffScaleDotProps & { seriesKey: string; color: string; textColor: string }) {
  const real = payload?.real?.[seriesKey];
  if (cx === undefined || cy === undefined || real === undefined || value === undefined || real === value) return <g />;
  const up = real > value;
  const tip = up ? cy - 2 : cy + 2;
  const base = up ? cy + 6 : cy - 6;
  return (
    <g>
      <polygon points={`${cx},${tip} ${cx - 5},${base} ${cx + 5},${base}`} fill={color} />
      <text x={cx} y={up ? cy + 19 : cy - 11} fontSize={11} textAnchor="middle" fill={textColor}>
        {formatEur(real, true)}
      </text>
    </g>
  );
}

export default function GriprOverview() {
  const { isDark } = useTheme();
  const gridColor = isDark ? "#334155" : "#e2e8f0";
  const tickColor = isDark ? "#94a3b8" : "#64748b";
  // No dots at rest -- the lines read as trends, not a scatter of points. The one under the
  // pointer (or finger) appears on hover, ringed in the card's own surface colour so it sits
  // cleanly on top of the line.
  const activeDot = { r: 4, strokeWidth: 2, stroke: isDark ? "#18120b" : "#ffffff" };

  const settingsQuery = useQuery({ queryKey: ["gripr-settings"], queryFn: () => griprApi.getSettings() });
  const startDay = settingsQuery.data?.period_start_day ?? 1;
  // Seeded only once settings have loaded -- see PeriodSwitcher/Budget.tsx for why a naive
  // calendar-month guess can send the wrong period to the backend.
  const [period, setPeriod] = useState<string | null>(null);
  useEffect(() => {
    if (settingsQuery.data && period === null) setPeriod(currentPeriodStart(settingsQuery.data.period_start_day));
  }, [settingsQuery.data, period]);

  const { data: overview, isLoading } = useQuery({
    queryKey: ["gripr-overview", period],
    queryFn: () => griprApi.getOverview(period as string),
    enabled: period !== null,
  });

  const categoriesQuery = useQuery({ queryKey: ["gripr-categories"], queryFn: () => griprApi.listCategories() });
  const topExpenseCategories = useMemo(
    () => (categoriesQuery.data ?? []).filter((c) => c.kind === "expense" && c.parent_id === null),
    [categoriesQuery.data],
  );
  const [trendCategoryId, setTrendCategoryId] = useState<number | null>(null);
  useEffect(() => {
    if (trendCategoryId === null && topExpenseCategories.length > 0) setTrendCategoryId(topExpenseCategories[0].id);
  }, [topExpenseCategories, trendCategoryId]);

  const { data: categoryTrend, isLoading: isTrendLoading } = useQuery({
    queryKey: ["gripr-category-trend", trendCategoryId, period],
    queryFn: () => griprApi.getCategoryTrend(trendCategoryId as number, period as string),
    enabled: trendCategoryId !== null && period !== null,
  });

  if (isLoading || !overview || period === null) {
    return (
      <div className="rounded-2xl border border-outline-variant bg-surface px-4 py-6 text-center text-on-surface-variant">
        Loading…
      </div>
    );
  }

  const incomeExpenseRows = overview.income_vs_expense.map((m) => ({
    month: periodLabel(m.month, startDay),
    title: periodTitle(m.month, startDay),
    Income: toNumber(m.income) ?? 0,
    Expense: toNumber(m.expense) ?? 0,
  }));

  const categoryTrendRows = (categoryTrend ?? []).map((p) => ({
    month: periodLabel(p.month, startDay),
    title: periodTitle(p.month, startDay),
    Spent: toNumber(p.amount) ?? 0,
  }));
  const trendCategoryName = topExpenseCategories.find((c) => c.id === trendCategoryId)?.name ?? "";

  // Both charts end at the selected period; when that's the current one it isn't over yet, so
  // it's left out of the averages (see completedPeriodAverage).
  const endsInProgress = period === currentPeriodStart(startDay);
  const incomeAverage = completedPeriodAverage(incomeExpenseRows.map((r) => r.Income), endsInProgress);
  const expenseAverage = completedPeriodAverage(incomeExpenseRows.map((r) => r.Expense), endsInProgress);
  const categoryAverage = completedPeriodAverage(categoryTrendRows.map((r) => r.Spent), endsInProgress);
  const averageNote = endsInProgress ? "Averages leave out this unfinished period." : null;

  const putAsideReal = overview.money_put_aside.map((m) => ({
    month: periodLabel(m.month, startDay),
    title: periodTitle(m.month, startDay),
    Investments: toNumber(m.investments) ?? 0,
    Savings: toNumber(m.savings) ?? 0,
    Reservations: toNumber(m.reservations) ?? 0,
  }));
  // A one-off month (home equity moved into savings) would flatten every other month: the scale
  // leaves it out, and the point is drawn at the edge with its real value (see OffScaleDot).
  const putAsideRange = cappedRange(putAsideReal.flatMap((r) => PUT_ASIDE_SERIES.map(({ key }) => r[key])));
  const putAsideRows = putAsideReal.map((r) => ({
    month: r.month,
    title: r.title,
    Investments: clampTo(r.Investments, putAsideRange),
    Savings: clampTo(r.Savings, putAsideRange),
    Reservations: clampTo(r.Reservations, putAsideRange),
    real: { Investments: r.Investments, Savings: r.Savings, Reservations: r.Reservations },
  }));
  // Averages of the real amounts, over completed periods only (like the other charts' averages).
  const putAsideAverages = Object.fromEntries(
    PUT_ASIDE_SERIES.map(({ key }) => [key, completedPeriodAverage(putAsideReal.map((r) => r[key]), endsInProgress)]),
  );

  const categorySorted = [...overview.spending_by_category].sort(
    (a, b) => (toNumber(b.amount) ?? 0) - (toNumber(a.amount) ?? 0),
  );
  const topCategories = categorySorted.slice(0, MAX_CATEGORY_BARS).map((c) => ({
    name: c.name,
    amount: toNumber(c.amount) ?? 0,
  }));
  const otherTotal = categorySorted.slice(MAX_CATEGORY_BARS).reduce((sum, c) => sum + (toNumber(c.amount) ?? 0), 0);
  const categoryRows = otherTotal > 0 ? [...topCategories, { name: "Other", amount: otherTotal }] : topCategories;

  const budgetRows = overview.budget_status
    .map((b) => ({ name: b.category_name, Budget: toNumber(b.budgeted) ?? 0, Spent: toNumber(b.spent) ?? 0 }))
    .filter((b) => b.Budget > 0 || b.Spent > 0)
    .sort((a, b) => b.Spent - a.Spent);

  // The rightmost bar of "Income vs. expense" below, pulled out as this period's headline
  // figures -- same numbers, just readable without hunting across the chart for them.
  const thisPeriod = incomeExpenseRows[incomeExpenseRows.length - 1];

  return (
    <div className="flex flex-col gap-4">
      <div className="sm:hidden">
        <ModuleTopRow />
      </div>
      <div className="flex flex-wrap items-end justify-between gap-x-3 gap-y-2">
        <PageTitle>Overview</PageTitle>
        <PeriodSwitcher periodStart={period} startDay={startDay} onChange={setPeriod} />
      </div>

      {thisPeriod && (
        <div className="flex divide-x divide-outline-variant rounded-2xl border border-outline-variant bg-surface">
          <div className="min-w-0 flex-1 px-4 py-3">
            <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">Income, this period</span>
            <div className="text-lg font-semibold text-emerald-600">{formatEur(thisPeriod.Income)}</div>
          </div>
          <div className="min-w-0 flex-1 px-4 py-3">
            <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">Expenses, this period</span>
            <div className="text-lg font-semibold text-red-600">{formatEur(thisPeriod.Expense)}</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-outline-variant bg-surface p-4">
          <h2 className="mb-3 text-sm font-medium text-on-surface">Income vs. expense, last 12 months</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={incomeExpenseRows} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={gridColor} />
                <XAxis dataKey="month" tick={{ fill: tickColor, fontSize: 12 }} axisLine={{ stroke: gridColor }} tickLine={false} />
                <YAxis
                  tick={{ fill: tickColor, fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  width={56}
                  tickFormatter={(v) => formatEur(v, true)}
                />
                <Tooltip content={<CustomTooltip />} />
                {incomeAverage && <ReferenceLine {...averageLineProps(incomeAverage.average, INCOME_COLOR)} />}
                {expenseAverage && <ReferenceLine {...averageLineProps(expenseAverage.average, EXPENSE_COLOR)} />}
                <Line type="monotone" dataKey="Income" stroke={INCOME_COLOR} strokeWidth={2} dot={false} activeDot={activeDot} />
                <Line type="monotone" dataKey="Expense" stroke={EXPENSE_COLOR} strokeWidth={2} dot={false} activeDot={activeDot} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-on-surface-variant">
            {/* Each series stays together with its average when the row wraps on a phone. */}
            <span className="flex items-center gap-3">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: INCOME_COLOR }} /> Income
              </span>
              {incomeAverage && <AverageLegend label="avg" value={incomeAverage.average} color={INCOME_COLOR} />}
            </span>
            <span className="flex items-center gap-3">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: EXPENSE_COLOR }} /> Expense
              </span>
              {expenseAverage && <AverageLegend label="avg" value={expenseAverage.average} color={EXPENSE_COLOR} />}
            </span>
          </div>
          {averageNote && <p className="mt-1 text-xs text-on-surface-variant">{averageNote}</p>}
        </div>

        <div className="rounded-2xl border border-outline-variant bg-surface p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-medium text-on-surface">Category spending, last 12 months</h2>
            {topExpenseCategories.length > 0 && (
              <select
                value={trendCategoryId ?? ""}
                onChange={(e) => setTrendCategoryId(Number(e.target.value))}
                className={selectClass}
              >
                {topExpenseCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            )}
          </div>
          {topExpenseCategories.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-sm text-on-surface-variant">
              No expense categories yet
            </div>
          ) : isTrendLoading ? (
            <div className="flex h-64 items-center justify-center text-sm text-on-surface-variant">Loading…</div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={categoryTrendRows} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={gridColor} />
                  <XAxis dataKey="month" tick={{ fill: tickColor, fontSize: 12 }} axisLine={{ stroke: gridColor }} tickLine={false} />
                  <YAxis
                    tick={{ fill: tickColor, fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    width={56}
                    tickFormatter={(v) => formatEur(v, true)}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  {categoryAverage && <ReferenceLine {...averageLineProps(categoryAverage.average, CATEGORICAL_COLORS[0])} />}
                  <Line
                    type="monotone"
                    dataKey="Spent"
                    name={trendCategoryName || "Spent"}
                    stroke={CATEGORICAL_COLORS[0]}
                    strokeWidth={2}
                    dot={false} activeDot={activeDot}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          {categoryAverage && !isTrendLoading && topExpenseCategories.length > 0 && (
            <>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-on-surface-variant">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: CATEGORICAL_COLORS[0] }} /> {trendCategoryName || "Spent"}
                </span>
                <AverageLegend label="avg" value={categoryAverage.average} color={CATEGORICAL_COLORS[0]} />
              </div>
              {averageNote && <p className="mt-1 text-xs text-on-surface-variant">{averageNote}</p>}
            </>
          )}
        </div>

        <div className="rounded-2xl border border-outline-variant bg-surface p-4">
          <div className="mb-3 flex flex-col gap-1">
            <InfoHeading
              label="Money put aside"
              title={<h2 className="text-sm font-medium text-on-surface">Money put aside, last 12 months</h2>}
            >
              What went into investments, savings and reservations each period, net: money moved in minus money moved out,
              plus interest and minus spending paid from them. Moving money from savings into a pot is less savings and more
              reservations. Investments count only money moved, not market gains.
            </InfoHeading>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={putAsideRows} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={gridColor} />
                <XAxis dataKey="month" tick={{ fill: tickColor, fontSize: 12 }} axisLine={{ stroke: gridColor }} tickLine={false} />
                <YAxis
                  tick={{ fill: tickColor, fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  width={56}
                  tickFormatter={(v) => formatEur(v, true)}
                  domain={putAsideRange ? [putAsideRange.min, putAsideRange.max] : ["auto", "auto"]}
                />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={0} stroke={tickColor} strokeWidth={1} />
                {PUT_ASIDE_SERIES.map(({ key, color }) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={color}
                    strokeWidth={2}
                    activeDot={activeDot}
                    dot={(props: OffScaleDotProps) => <OffScaleDot key={`${key}-${props.index}`} {...props} seriesKey={key} color={color} textColor={tickColor} />}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          {putAsideRange && (
            <p className="mt-1 text-xs text-on-surface-variant">
              ▲▼ marks a month off the scale; its real amount is shown next to it.
            </p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-on-surface-variant">
            {PUT_ASIDE_SERIES.map(({ key, color }) => (
              <span key={key} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} /> {key}
                {putAsideAverages[key] && (
                  <span>
                    avg <span className="tabular-nums text-on-surface">{formatEur(putAsideAverages[key]!.average)}</span>
                  </span>
                )}
              </span>
            ))}
          </div>
          {averageNote && <p className="mt-1 text-xs text-on-surface-variant">{averageNote}</p>}
        </div>

        <div className="rounded-2xl border border-outline-variant bg-surface p-4">
          <h2 className="mb-3 text-sm font-medium text-on-surface">Spending by category, this period</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryRows} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke={gridColor} />
                <XAxis type="number" tick={{ fill: tickColor, fontSize: 12 }} axisLine={{ stroke: gridColor }} tickLine={false} tickFormatter={(v) => formatEur(v, true)} />
                <YAxis type="category" dataKey="name" tick={{ fill: tickColor, fontSize: 12 }} axisLine={false} tickLine={false} width={130} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="amount" name="Spent" radius={[0, 2, 2, 0]}>
                  {categoryRows.map((entry, i) => (
                    <Cell key={entry.name} fill={entry.name === "Other" ? OTHER_COLOR : CATEGORICAL_COLORS[i % CATEGORICAL_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-outline-variant bg-surface p-4">
          <h2 className="mb-3 text-sm font-medium text-on-surface">Budget vs. actual, this period</h2>
          {budgetRows.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-sm text-on-surface-variant">No budgets set yet</div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={budgetRows} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
                  <CartesianGrid horizontal={false} stroke={gridColor} />
                  <XAxis type="number" tick={{ fill: tickColor, fontSize: 12 }} axisLine={{ stroke: gridColor }} tickLine={false} tickFormatter={(v) => formatEur(v, true)} />
                  <YAxis type="category" dataKey="name" tick={{ fill: tickColor, fontSize: 12 }} axisLine={false} tickLine={false} width={130} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="Budget" fill={OTHER_COLOR} radius={[0, 2, 2, 0]} />
                  <Bar dataKey="Spent" fill={CATEGORICAL_COLORS[0]} radius={[0, 2, 2, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-2xl bg-primary-container px-4 py-3.5">
        <span className="text-xs font-medium uppercase tracking-wide text-on-primary-container/70">Net worth</span>
        {/* pnlColorClass, not a Material token -- gain/loss colouring is a cross-app convention
            shared with gainr, deliberately never swapped per module. */}
        <div className={`text-2xl font-semibold ${pnlColorClass(overview.net_worth)}`}>{formatEur(overview.net_worth)}</div>
      </div>
    </div>
  );
}
