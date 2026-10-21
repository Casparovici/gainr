import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { griprApi } from "../../api/griprClient";
import PeriodSwitcher from "../../components/gripr/PeriodSwitcher";
import { ModuleTopRow, PageTitle } from "../../components/ui/kit";
import SubcategoryBreakdown from "../../components/gripr/SubcategoryBreakdown";
import InfoHeading from "../../components/ui/InfoTip";
import { cappedRange, clampTo, niceTicks } from "../../utils/chartScale";
import { useTheme } from "../../hooks/useTheme";
import { formatDate, formatEur, formatMonths, formatPct, pnlColorClass, toNumber } from "../../utils/format";
import { buildCategoryColorMap } from "../../utils/categoryColor";
import { CATEGORICAL_COLORS, OTHER_COLOR } from "../../utils/palette";
import { completedPeriodAverage, splitInProgress } from "../../utils/griprAverages";
import { currentPeriodStart, periodLabel, periodTitle } from "../../utils/griprPeriod";
import { msg, t } from "../../i18n";

// Fixed palette order (blue, orange, yellow), each line labelled in the legend with its figure.
const PUT_ASIDE_SERIES = [
  { key: "Investments", label: msg("Investments"), color: CATEGORICAL_COLORS[0] },
  { key: "Savings", label: msg("Savings"), color: CATEGORICAL_COLORS[1] },
  { key: "Reservations", label: msg("Reservations"), color: CATEGORICAL_COLORS[3] },
] as const;
const INCOME_COLOR = "#1baf7a"; // aqua — same slot spending-by-category never reassigns
const EXPENSE_COLOR = "#e34948"; // red
const PARTIAL_DASH = "5 4"; // an unfinished period: same colour, dashed
const BALANCE_COLOR = CATEGORICAL_COLORS[0]; // same blue the category-trend chart uses
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
  const entries = (payload ?? [])
    .filter((p) => p.value !== null && p.value !== undefined)
    .filter((p, i, all) => all.findIndex((q) => q.name === p.name) === i);
  if (!active || !entries.length) return null;
  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-high px-3 py-2 text-xs shadow-sm">
      {(entries[0].payload?.title ?? label) && <div className="mb-1 font-medium text-on-surface">{entries[0].payload?.title ?? label}</div>}
      {entries.map((p) => (
        <div key={p.name} className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
          <span className="text-on-surface-variant">{p.name}:</span>
          <span className="font-medium text-on-surface">{formatEur(p.payload?.real?.[p.dataKey ?? ""] ?? p.value)}</span>
        </div>
      ))}
    </div>
  );
}

function ChartEmpty({ children }: { children: ReactNode }) {
  return <div className="flex h-64 items-center justify-center px-4 text-center text-sm text-on-surface-variant">{children}</div>;
}

type OffScaleDotProps = { cx?: number; cy?: number; index?: number; value?: number; payload?: { real?: Record<string, number> } };

/** Nothing for an ordinary point; for one drawn at the edge of a capped scale, a small arrow in the
 * series' colour and its real amount in the axis ink, so the outlier is still read correctly. */
function OffScaleDot({ cx, cy, value, payload, seriesKey, color, textColor, haloColor }: OffScaleDotProps & { seriesKey: string; color: string; textColor: string; haloColor: string }) {
  const real = payload?.real?.[seriesKey];
  if (cx === undefined || cy === undefined || real === undefined || value === undefined || value === null || real === value) return <g />;
  const up = real > value;
  const tip = up ? cy - 2 : cy + 2;
  const base = up ? cy + 6 : cy - 6;
  return (
    <g>
      <polygon points={`${cx},${tip} ${cx - 5},${base} ${cx + 5},${base}`} fill={color} />
      <text x={cx} y={up ? cy + 19 : cy - 11} fontSize={11} textAnchor="middle" fill={textColor} stroke={haloColor} strokeWidth={3} paintOrder="stroke">
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

  const { data: overview, isLoading, isError, refetch } = useQuery({
    queryKey: ["gripr-overview", period],
    queryFn: () => griprApi.getOverview(period as string),
    enabled: period !== null,
  });

  const categoriesQuery = useQuery({ queryKey: ["gripr-categories"], queryFn: () => griprApi.listCategories() });
  const colorOf = useMemo(() => buildCategoryColorMap(categoriesQuery.data ?? []), [categoriesQuery.data]);
  const topExpenseCategories = useMemo(
    () => (categoriesQuery.data ?? []).filter((c) => c.kind === "expense" && c.parent_id === null),
    [categoriesQuery.data],
  );
  // The category whose bar was clicked in "Spending by category": split by subcategory underneath.
  const [drillCategoryId, setDrillCategoryId] = useState<number | null>(null);
  const [trendCategoryId, setTrendCategoryId] = useState<number | null>(null);
  useEffect(() => {
    if (trendCategoryId === null && topExpenseCategories.length > 0) setTrendCategoryId(topExpenseCategories[0].id);
  }, [topExpenseCategories, trendCategoryId]);

  const { data: categoryTrend, isLoading: isTrendLoading, isError: isTrendError } = useQuery({
    queryKey: ["gripr-category-trend", trendCategoryId, period],
    queryFn: () => griprApi.getCategoryTrend(trendCategoryId as number, period as string),
    enabled: trendCategoryId !== null && period !== null,
  });

  // Always the period containing today, regardless of the switcher above -- a forecast only
  // makes sense relative to "now".
  const {
    data: balanceForecast,
    isLoading: isForecastLoading,
    isError: isForecastError,
  } = useQuery({ queryKey: ["gripr-balance-forecast"], queryFn: () => griprApi.getBalanceForecast() });

  if (isError || (period === null && settingsQuery.isError)) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-2xl border border-outline-variant bg-surface px-4 py-6 text-center text-on-surface-variant">{t("Couldn't load the overview.")}<button
          type="button"
          onClick={() => (period === null ? settingsQuery.refetch() : refetch())}
          className="rounded-full border border-outline px-4 py-1.5 text-sm text-on-surface hover:bg-on-surface/10">{t("Try again")}</button>
      </div>
    );
  }
  if (isLoading || !overview || period === null) {
    return (
      <div className="rounded-2xl border border-outline-variant bg-surface px-4 py-6 text-center text-on-surface-variant">{t("Loading…")}</div>
    );
  }

  const incomeExpenseRows = overview.income_vs_expense.map((m) => ({
    month: periodLabel(m.month, startDay),
    title: periodTitle(m.month, startDay),
    Income: toNumber(m.income) ?? 0,
    Expense: toNumber(m.expense) ?? 0,
  }));

  // The selected period is the one in progress: its last point is drawn dashed, and left out of the
  // averages (see completedPeriodAverage).
  const endsInProgress = period === currentPeriodStart(startDay);
  const incomeSplit = splitInProgress(incomeExpenseRows.map((r) => r.Income), endsInProgress);
  const expenseSplit = splitInProgress(incomeExpenseRows.map((r) => r.Expense), endsInProgress);
  const incomeExpenseChartRows = incomeExpenseRows.map((r, i) => ({
    ...r,
    Income: incomeSplit.solid[i],
    IncomePartial: incomeSplit.partial[i],
    Expense: expenseSplit.solid[i],
    ExpensePartial: expenseSplit.partial[i],
  }));

  const categoryTrendRows = (categoryTrend ?? []).map((p) => ({
    month: periodLabel(p.month, startDay),
    title: periodTitle(p.month, startDay),
    Spent: toNumber(p.amount) ?? 0,
  }));
  const spentSplit = splitInProgress(categoryTrendRows.map((r) => r.Spent), endsInProgress);
  const categoryTrendChartRows = categoryTrendRows.map((r, i) => ({ ...r, Spent: spentSplit.solid[i], SpentPartial: spentSplit.partial[i] }));
  const trendColor = (trendCategoryId !== null ? colorOf.get(trendCategoryId) : undefined) ?? CATEGORICAL_COLORS[0];
  const trendCategoryName = topExpenseCategories.find((c) => c.id === trendCategoryId)?.name ?? "";

  // Both charts end at the selected period; when that's the current one it isn't over yet, so
  // it's left out of the averages (see completedPeriodAverage).
  const incomeAverage = completedPeriodAverage(incomeExpenseRows.map((r) => r.Income), endsInProgress);
  const expenseAverage = completedPeriodAverage(incomeExpenseRows.map((r) => r.Expense), endsInProgress);
  const categoryAverage = completedPeriodAverage(categoryTrendRows.map((r) => r.Spent), endsInProgress);
  const averageNote = endsInProgress ? t("The dashed end is the unfinished period; averages leave it out.") : null;

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
  const putAsideValues = putAsideReal.flatMap((r) => PUT_ASIDE_SERIES.map(({ key }) => r[key]));
  const putAsideTicks = niceTicks(
    putAsideRange?.min ?? Math.min(0, ...putAsideValues),
    putAsideRange?.max ?? Math.max(0, ...putAsideValues),
  );
  const hasPutAside = putAsideValues.some((v) => v !== 0);
  const putAsideSplits = Object.fromEntries(
    PUT_ASIDE_SERIES.map(({ key }) => [key, splitInProgress(putAsideReal.map((r) => clampTo(r[key], putAsideRange)), endsInProgress)]),
  );
  const putAsideRows = putAsideReal.map((r, i) => ({
    month: r.month,
    title: r.title,
    Investments: putAsideSplits.Investments.solid[i],
    InvestmentsPartial: putAsideSplits.Investments.partial[i],
    Savings: putAsideSplits.Savings.solid[i],
    SavingsPartial: putAsideSplits.Savings.partial[i],
    Reservations: putAsideSplits.Reservations.solid[i],
    ReservationsPartial: putAsideSplits.Reservations.partial[i],
    real: {
      Investments: r.Investments, InvestmentsPartial: r.Investments,
      Savings: r.Savings, SavingsPartial: r.Savings,
      Reservations: r.Reservations, ReservationsPartial: r.Reservations,
    },
  }));
  // Averages of the real amounts, over completed periods only (like the other charts' averages).
  const putAsideAverages = Object.fromEntries(
    PUT_ASIDE_SERIES.map(({ key }) => [key, completedPeriodAverage(putAsideReal.map((r) => r[key]), endsInProgress)]),
  );

  const categorySorted = [...overview.spending_by_category].sort(
    (a, b) => (toNumber(b.amount) ?? 0) - (toNumber(a.amount) ?? 0),
  );
  const topCategories = categorySorted.slice(0, MAX_CATEGORY_BARS).map((c) => ({
    id: c.category_id,
    name: c.name,
    amount: toNumber(c.amount) ?? 0,
    change: toNumber(c.change_pct ?? null),
  }));
  const otherTotal = categorySorted.slice(MAX_CATEGORY_BARS).reduce((sum, c) => sum + (toNumber(c.amount) ?? 0), 0);
  const categoryRows = otherTotal > 0 ? [...topCategories, { id: null, name: t("Other"), amount: otherTotal, change: null }] : topCategories;

  // Expense categories only: an income target (salary) on the same scale would dwarf every
  // spending line, and "spent" doesn't describe income.
  const budgetRows = overview.budget_status
    .filter((b) => b.kind === "expense")
    .map((b) => ({ id: b.category_id, name: b.category_name, budget: toNumber(b.budgeted) ?? 0, spent: toNumber(b.spent) ?? 0 }))
    .filter((b) => b.budget > 0 || b.spent > 0)
    .sort((a, b) => b.spent / (b.budget || 1) - a.spent / (a.budget || 1) || b.spent - a.spent);
  const hasBudgets = overview.budget_status.some((b) => (toNumber(b.budgeted) ?? 0) > 0);
  const hasIncomeExpense = incomeExpenseRows.some((r) => r.Income !== 0 || r.Expense !== 0);

  // The rightmost bar of "Income vs. expense" below, pulled out as this period's headline
  // figures -- same numbers, just readable without hunting across the chart for them.
  const thisPeriod = incomeExpenseRows[incomeExpenseRows.length - 1];

  // Actual and forecast share one line, split into two dataKeys so the segment up to today
  // draws solid and the rest dashed; the point for today appears in both so they meet without a
  // gap. Forecast.length === 0 means no checking account to forecast at all.
  const balanceRows = (balanceForecast?.points ?? []).map((p) => ({
    date: formatDate(p.date, { day: "numeric", month: "short" }),
    title: formatDate(p.date),
    Actual: p.is_forecast ? null : (toNumber(p.balance) ?? 0),
    Forecast: p.is_forecast ? (toNumber(p.balance) ?? 0) : null,
  }));
  const lastActualIndex = balanceRows.reduce((idx, r, i) => (r.Actual !== null ? i : idx), -1);
  if (lastActualIndex !== -1 && lastActualIndex < balanceRows.length - 1) {
    balanceRows[lastActualIndex].Forecast = balanceRows[lastActualIndex].Actual;
  }
  // What the card answers at a glance (all worked out by the backend): where the period ends,
  // the dip on the way if there is one, and what could be moved out today.
  const endPoint = balanceForecast?.points.at(-1);
  const forecastEnd = endPoint?.is_forecast ? balanceForecast?.expected_end ?? null : null;
  const lowest = balanceForecast?.lowest ?? null;
  const showLowest = forecastEnd !== null && lowest !== null && (toNumber(lowest.balance) ?? 0) < (toNumber(forecastEnd) ?? 0) - 0.5;
  const todayLabel = lastActualIndex !== -1 ? balanceRows[lastActualIndex].date : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="sm:hidden">
        <ModuleTopRow settings={false} />
      </div>
      <div className="flex flex-wrap items-end justify-between gap-x-3 gap-y-2">
        <PageTitle>{t("Overview")}</PageTitle>
        <PeriodSwitcher periodStart={period} startDay={startDay} onChange={setPeriod} />
      </div>

      {thisPeriod && (
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-outline-variant bg-outline-variant sm:grid-cols-4">
          <div className="min-w-0 bg-surface px-4 py-3">
            <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{t("Income")}</span>
            <div className="text-lg font-semibold text-emerald-600">{formatEur(thisPeriod.Income)}</div>
          </div>
          <div className="min-w-0 bg-surface px-4 py-3">
            <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{t("Expenses")}</span>
            <div className="text-lg font-semibold text-red-600">{formatEur(thisPeriod.Expense)}</div>
          </div>
          <div className="min-w-0 bg-surface px-4 py-3">
            <InfoHeading
              label={t("Savings rate")}
              title={<span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{t("Savings rate")}</span>}
            >{t("The share of what came in that was kept: (income - spending) / income, with spending net of refunds.")}{endsInProgress && ` ${t("This period is still running, so it moves as income and spending arrive.")}`}
            </InfoHeading>
            <div className={`text-lg font-semibold ${pnlColorClass(overview.savings_health.savings_rate_pct)}`}>
              {overview.savings_health.savings_rate_pct === null ? "—" : formatPct(overview.savings_health.savings_rate_pct, 0, false)}
            </div>
            {overview.savings_health.trailing_rate_pct !== null && (
              <div className="text-xs text-on-surface-variant">
                {formatPct(overview.savings_health.trailing_rate_pct, 0, false)}{" "}{t("over the 3 periods before")}</div>
            )}
          </div>
          <div className="min-w-0 bg-surface px-4 py-3">
            <InfoHeading
              label={t("Runway")}
              title={<span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{t("Runway")}</span>}
            >{t("How many months your checking and savings (not the reservations, which are earmarked) would cover at a typical month's spending: the median of the last three completed periods, so one large purchase doesn't set it. Always as of today.")}</InfoHeading>
            <div className="text-lg font-semibold text-on-surface">{formatMonths(overview.savings_health.runway_months)}</div>
            <div className="text-xs text-on-surface-variant">{formatEur(overview.savings_health.liquid_savings, true)}{" "}{t("on hand")}</div>
          </div>
        </div>
      )}

      {endsInProgress && (
      <div className="rounded-2xl border border-outline-variant bg-surface p-4">
        <div className="mb-3 flex flex-col gap-1">
          <InfoHeading
            label={t("Balance forecast")}
            title={<h2 className="text-sm font-medium text-on-surface">{t("Balance, this period")}</h2>}
          >{t("Your checking balance day by day: actual up to today, then a forecast for the rest of the period -- known recurring payments and income land on their own dates, and what's left of each category's budget spreads over the remaining days")}{" "}
            {balanceForecast?.weekday_pattern
              ? t("following the weekdays you usually spend on")
              : t("evenly (there isn't enough history yet to learn when you spend)")}{t(". \"Safe to move out today\" is the lowest point the forecast reaches, minus a buffer of a week of everyday spending (recurring payments and purchases over €500 left out, since the forecast already places those); anything up to that could go to savings or investments without the account running short. Savings, investment, credit and loan balances aren't included, since they don't move with everyday spending.")}</InfoHeading>
          {endPoint && forecastEnd !== null && (
            <p className="text-xs text-on-surface-variant">{t("Expected on {date}:", { date: formatDate(endPoint.date, { day: "numeric", month: "short" }) })}{" "}
              <span className="font-medium tabular-nums text-on-surface">{formatEur(forecastEnd)}</span>
              {showLowest && lowest && (
                <>
                  {" · "}{t("lowest")}{" "}<span className="tabular-nums text-on-surface">{formatEur(lowest.balance)}</span>{" "}{t("on")}{" "}
                  {formatDate(lowest.date, { day: "numeric", month: "short" })}
                </>
              )}
            </p>
          )}
          {balanceForecast && balanceForecast.safe_to_move !== null && (
            <p className="text-xs text-on-surface-variant">
              {(toNumber(balanceForecast.safe_to_move) ?? 0) > 0 ? (
                <>{t("Safe to move out today:")}{" "}
                  <span className="font-medium tabular-nums text-on-surface">{formatEur(balanceForecast.safe_to_move)}</span>
                </>
              ) : (
                <>{t("Nothing is safe to move out today")}</>
              )}
              {" · "}{t("keeping {buffer} back", { buffer: formatEur(balanceForecast.buffer) })}</p>
          )}
        </div>
        {isForecastLoading ? (
          <div className="flex h-64 items-center justify-center text-sm text-on-surface-variant">{t("Loading…")}</div>
        ) : isForecastError ? (
          <div className="flex h-64 items-center justify-center text-sm text-on-surface-variant">{t("Couldn't load the balance forecast")}</div>
        ) : balanceRows.length === 0 ? (
          <div className="flex h-64 items-center justify-center text-sm text-on-surface-variant">{t("No checking account yet")}</div>
        ) : (
          <>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={balanceRows} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={gridColor} />
                  <XAxis dataKey="date" tick={{ fill: tickColor, fontSize: 12 }} axisLine={{ stroke: gridColor }} tickLine={false} minTickGap={24} />
                  <YAxis
                    tick={{ fill: tickColor, fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    width={56}
                    tickFormatter={(v) => formatEur(v, true)}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  {todayLabel && (
                    <ReferenceLine
                      x={todayLabel}
                      stroke={tickColor}
                      strokeDasharray="3 3"
                      label={{ value: t("Today"), position: "insideTopRight", fill: tickColor, fontSize: 11 }}
                    />
                  )}
                  <Line type="linear" dataKey="Actual" name={t("Actual")} stroke={BALANCE_COLOR} strokeWidth={2} dot={false} activeDot={activeDot} connectNulls />
                  <Line
                    type="linear"
                    dataKey="Forecast"
                    name={t("Forecast")}
                    stroke={BALANCE_COLOR}
                    strokeWidth={2}
                    strokeDasharray="5 4"
                    dot={false}
                    activeDot={activeDot}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-on-surface-variant">
              <span className="flex items-center gap-1.5">
                <svg width="14" height="2" aria-hidden>
                  <line x1="0" y1="1" x2="14" y2="1" stroke={BALANCE_COLOR} strokeWidth="2" />
                </svg>{t("Actual")}</span>
              <span className="flex items-center gap-1.5">
                <svg width="14" height="2" aria-hidden>
                  <line x1="0" y1="1" x2="14" y2="1" stroke={BALANCE_COLOR} strokeWidth="2" strokeDasharray="3 2" />
                </svg>{t("Forecast")}</span>
            </div>
          </>
        )}
      </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-outline-variant bg-surface p-4">
          <h2 className="mb-3 text-sm font-medium text-on-surface">{t("Income vs. expense, last 12 months")}</h2>
          {!hasIncomeExpense ? (
            <ChartEmpty>{t("No transactions yet. Add some on Transactions.")}</ChartEmpty>
          ) : (
            <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={incomeExpenseChartRows} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
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
                <Line type="linear" dataKey="Income" name={t("Income")} stroke={INCOME_COLOR} strokeWidth={2} dot={false} activeDot={activeDot} />
                <Line type="linear" dataKey="IncomePartial" name={t("Income")} stroke={INCOME_COLOR} strokeWidth={2} strokeDasharray={PARTIAL_DASH} dot={false} activeDot={activeDot} connectNulls />
                <Line type="linear" dataKey="Expense" name={t("Expense")} stroke={EXPENSE_COLOR} strokeWidth={2} dot={false} activeDot={activeDot} />
                <Line type="linear" dataKey="ExpensePartial" name={t("Expense")} stroke={EXPENSE_COLOR} strokeWidth={2} strokeDasharray={PARTIAL_DASH} dot={false} activeDot={activeDot} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-on-surface-variant">
            {/* Each series stays together with its average when the row wraps on a phone. */}
            <span className="flex items-center gap-3">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: INCOME_COLOR }} />{" "}{t("Income")}</span>
              {incomeAverage && <AverageLegend label={t("avg")} value={incomeAverage.average} color={INCOME_COLOR} />}
            </span>
            <span className="flex items-center gap-3">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: EXPENSE_COLOR }} />{" "}{t("Expense")}</span>
              {expenseAverage && <AverageLegend label={t("avg")} value={expenseAverage.average} color={EXPENSE_COLOR} />}
            </span>
          </div>
          {averageNote && <p className="mt-1 text-xs text-on-surface-variant">{averageNote}</p>}
        </div>

        <div className="rounded-2xl border border-outline-variant bg-surface p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-medium text-on-surface">{t("Category spending, last 12 months")}</h2>
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
            <div className="flex h-64 items-center justify-center text-sm text-on-surface-variant">{t("No expense categories yet")}</div>
          ) : isTrendLoading ? (
            <ChartEmpty>{t("Loading…")}</ChartEmpty>
          ) : isTrendError ? (
            <ChartEmpty>{t("Couldn't load this category's spending.")}</ChartEmpty>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={categoryTrendChartRows} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
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
                  {categoryAverage && <ReferenceLine {...averageLineProps(categoryAverage.average, trendColor)} />}
                  <Line
                    type="linear"
                    dataKey="Spent"
                    name={trendCategoryName || t("Spent")}
                    stroke={trendColor}
                    strokeWidth={2}
                    dot={false} activeDot={activeDot}
                  />
                  <Line
                    type="linear"
                    dataKey="SpentPartial"
                    name={trendCategoryName || t("Spent")}
                    stroke={trendColor}
                    strokeWidth={2}
                    strokeDasharray={PARTIAL_DASH}
                    dot={false} activeDot={activeDot}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          {categoryAverage && !isTrendLoading && topExpenseCategories.length > 0 && (
            <>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-on-surface-variant">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: trendColor }} /> {trendCategoryName || t("Spent")}
                </span>
                <AverageLegend label={t("avg")} value={categoryAverage.average} color={trendColor} />
              </div>
              {averageNote && <p className="mt-1 text-xs text-on-surface-variant">{averageNote}</p>}
            </>
          )}
        </div>

        <div className="rounded-2xl border border-outline-variant bg-surface p-4">
          <div className="mb-3 flex flex-col gap-1">
            <InfoHeading
              label={t("Money put aside")}
              title={<h2 className="text-sm font-medium text-on-surface">{t("Money put aside, last 12 months")}</h2>}
            >{t("What went into investments, savings and reservations each period, net: money moved in minus money moved out, plus interest and minus spending paid from them. Moving money from savings into a pot is less savings and more reservations. Investments count only money moved, not market gains.")}</InfoHeading>
          </div>
          {!hasPutAside ? (
            <ChartEmpty>{t("Nothing put aside yet. Transfer money to a savings or investment account.")}</ChartEmpty>
          ) : (
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
                  domain={[putAsideTicks[0], putAsideTicks[putAsideTicks.length - 1]]}
                  ticks={putAsideTicks}
                />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={0} stroke={tickColor} strokeWidth={1} />
                {PUT_ASIDE_SERIES.flatMap(({ key, label, color }) =>
                  [false, true].map((partial) => (
                    <Line
                      key={partial ? `${key}Partial` : key}
                      type="linear"
                      dataKey={partial ? `${key}Partial` : key}
                      name={t(label)}
                      stroke={color}
                      strokeWidth={2}
                      strokeDasharray={partial ? PARTIAL_DASH : undefined}
                      connectNulls={partial}
                      activeDot={activeDot}
                      dot={(props: OffScaleDotProps) => <OffScaleDot key={`${key}-${partial}-${props.index}`} {...props} seriesKey={key} color={color} textColor={tickColor} haloColor={isDark ? "#18120b" : "#ffffff"} />}
                    />
                  )),
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
          )}
          {putAsideRange && (
            <p className="mt-1 text-xs text-on-surface-variant">{t("▲▼ marks a month off the scale; its real amount is shown next to it.")}</p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-on-surface-variant">
            {PUT_ASIDE_SERIES.map(({ key, label, color }) => (
              <span key={key} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} /> {t(label)}
                {putAsideAverages[key] && (
                  <span>{t("avg")}{" "}<span className="tabular-nums text-on-surface">{formatEur(putAsideAverages[key]!.average)}</span>
                  </span>
                )}
              </span>
            ))}
          </div>
          {averageNote && <p className="mt-1 text-xs text-on-surface-variant">{averageNote}</p>}
        </div>

        <div className="rounded-2xl border border-outline-variant bg-surface p-4">
          <h2 className="mb-3 text-sm font-medium text-on-surface">{t("Spending by category, this period")}</h2>
          {categoryRows.length === 0 ? (
            <ChartEmpty>{t("No spending this period yet.")}</ChartEmpty>
          ) : (
            <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryRows} layout="vertical" margin={{ top: 4, right: 104, left: 8, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke={gridColor} />
                <XAxis type="number" tick={{ fill: tickColor, fontSize: 12 }} axisLine={{ stroke: gridColor }} tickLine={false} tickFormatter={(v) => formatEur(v, true)} />
                <YAxis type="category" dataKey="name" tick={{ fill: tickColor, fontSize: 12 }} axisLine={false} tickLine={false} width={130} />
                <Tooltip content={<CustomTooltip />} />
                <Bar
                  dataKey="amount"
                  name={t("Spent")}
                  radius={[0, 2, 2, 0]}
                  cursor="pointer"
                  onClick={(entry) => {
                    const id = (entry.payload as { id: number | null }).id;
                    if (id !== null) setDrillCategoryId((current) => (current === id ? null : id));
                  }}
                >
                  {categoryRows.map((entry) => (
                    <Cell key={entry.name} fill={entry.id === null ? OTHER_COLOR : (colorOf.get(entry.id) ?? OTHER_COLOR)} />
                  ))}
                  <LabelList
                    dataKey="amount"
                    content={(props) => {
                      const { x, y, width, height, value, index } = props as { x?: number; y?: number; width?: number; height?: number; value?: number; index?: number };
                      if (x === undefined || y === undefined || width === undefined || height === undefined || index === undefined) return null;
                      const change = categoryRows[index]?.change ?? null;
                      return (
                        <text x={x + width + 4} y={y + height / 2} dy={4} fontSize={11} fill={tickColor}>
                          {formatEur(value ?? 0, true)}
                          {change !== null && Math.abs(change) >= 1 && (
                            <tspan dx={6} fill={change > 0 ? EXPENSE_COLOR : INCOME_COLOR}>
                              {formatPct(change, 0)}
                            </tspan>
                          )}
                        </text>
                      );
                    }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          )}
          {categoryRows.length > 0 && !drillCategoryId && (
            <p className="mt-1 text-xs text-on-surface-variant">
              {endsInProgress
                ? t("The % compares with what the 3 periods before had spent by this point, on average.")
                : t("The % compares with the category's average over the 3 periods before.")}{" "}{t("Tap a bar to split it by subcategory.")}</p>
          )}
          {drillCategoryId !== null && categoryRows.some((r) => r.id === drillCategoryId) && (
            <div className="mt-3 flex flex-col gap-2 border-t border-outline-variant pt-3">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-medium text-on-surface">
                  {categoryRows.find((r) => r.id === drillCategoryId)?.name}{t(", by subcategory")}</h3>
                <button type="button" onClick={() => setDrillCategoryId(null)} className="text-xs text-on-surface-variant hover:text-on-surface">{t("Close")}</button>
              </div>
              <SubcategoryBreakdown categoryId={drillCategoryId} period={period} color={colorOf.get(drillCategoryId) ?? OTHER_COLOR} />
            </div>
          )}
        </div>

        {hasBudgets && (
          <div className="rounded-2xl border border-outline-variant bg-surface p-4 lg:col-span-2">
            <div className="mb-3 flex flex-col gap-1">
              <InfoHeading
                label={t("Budgets that keep missing")}
                title={<h2 className="text-sm font-medium text-on-surface">{t("Needs attention")}</h2>}
              >{t("Budgets missed the same way in each of the last 3 completed periods: overspent every time, or under 75% every time. A single bad month doesn't count. The suggested budget is the average of those periods, rounded up to a multiple of 5.")}</InfoHeading>
            </div>
            {overview.budget_attention.length === 0 ? (
              <p className="py-4 text-sm text-on-surface-variant">{t("No budget has been missed the same way three periods running.")}</p>
            ) : (
              <ul className="divide-y divide-outline-variant">
                {overview.budget_attention.map((item) => (
                  <li key={item.category_id} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
                    <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: colorOf.get(item.category_id) ?? OTHER_COLOR }} />
                    <div className="min-w-0 text-sm">
                      <div className="font-medium text-on-surface">{item.category_name}</div>
                      <div className="text-xs text-on-surface-variant">
                        {item.kind === "over_streak"
                          ? t("Over budget {n} periods running: averaging", { n: item.periods })
                          : t("Under budget {n} periods running: averaging", { n: item.periods })}{" "}
                        <span className={`tabular-nums ${item.kind === "over_streak" ? "text-red-600" : "text-on-surface"}`}>{formatEur(item.average_spent)}</span>{" "}{t("against {budgeted}. A budget of", { budgeted: formatEur(item.budgeted) })}{" "}
                        <span className="tabular-nums text-on-surface">{formatEur(item.suggested_budget)}</span>{" "}{t("would have fitted.")}</div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="rounded-2xl border border-outline-variant bg-surface p-4 lg:col-span-2">
          <h2 className="mb-3 text-sm font-medium text-on-surface">{t("Budget vs. actual, this period")}</h2>
          {budgetRows.length === 0 ? (
            <ChartEmpty>{t("No budgets set yet. Set them on Budget.")}</ChartEmpty>
          ) : (
            <ul className="grid grid-cols-1 gap-x-8 gap-y-3 lg:grid-cols-2">
              {budgetRows.map((b) => {
                const over = b.budget > 0 && b.spent > b.budget;
                const pct = b.budget > 0 ? Math.min(100, (b.spent / b.budget) * 100) : 0;
                return (
                  <li key={b.name}>
                    <div className="flex items-baseline justify-between gap-2 text-sm">
                      <span className="flex min-w-0 items-center gap-2 text-on-surface">
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: colorOf.get(b.id) ?? OTHER_COLOR }} />
                        <span className="truncate">{b.name}</span>
                      </span>
                      <span className="shrink-0 text-xs tabular-nums text-on-surface-variant">
                        {b.budget > 0 ? (
                          <>
                            <span className={over ? "font-medium text-red-600" : "text-on-surface"}>{formatEur(b.spent)}</span>{` ${t("of")} `}{formatEur(b.budget)}{" · "}
                            {over ? <span className="text-red-600">{formatEur(b.spent - b.budget)}{" "}{t("over")}</span> : <>{formatEur(b.budget - b.spent)}{` ${t("left")}`}</>}
                          </>
                        ) : (
                          <>{formatEur(b.spent)}{t(", no budget")}</>
                        )}
                      </span>
                    </div>
                    <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-container-high" role="progressbar" aria-label={t("{name} budget used", { name: b.name })} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
                      <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: over ? EXPENSE_COLOR : BALANCE_COLOR }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      <div className="rounded-2xl bg-primary-container px-4 py-3.5">
        <span className="text-xs font-medium uppercase tracking-wide text-on-primary-container/70">{t("Net worth today")}</span>
        {/* pnlColorClass, not a Material token -- gain/loss colouring is a cross-app convention
            shared with gainr, deliberately never swapped per module. */}
        <div className={`text-2xl font-semibold ${pnlColorClass(overview.net_worth)}`}>{formatEur(overview.net_worth)}</div>
      </div>
    </div>
  );
}
