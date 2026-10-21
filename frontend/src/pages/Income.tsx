import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api/client";
import type { DividendHolding, DividendIncome, DividendMonth } from "../api/types";
import CollapsibleCard from "../components/CollapsibleCard";
import GainrTopRow from "../components/GainrTopRow";
import { SummaryTile } from "../components/SummaryTile";
import { PageTitle } from "../components/ui/kit";
import { usePortfolio } from "../hooks/usePortfolio";
import { formatDate, formatEur, formatPct, toNumber } from "../utils/format";
import { dateLocale, t } from "../i18n";

const cardClass = "rounded-2xl border border-ui-border bg-ui-surface px-4 py-6 text-center text-sm text-ui-muted";

function monthLabel(month: string, long = false): string {
  const [year, m] = month.split("-").map(Number);
  const d = new Date(year, m - 1, 1);
  if (long) return d.toLocaleDateString(dateLocale("en-GB"), { month: "long", year: "numeric" });
  // January carries its year, so the axis says where one year turns into the next.
  return m === 1 ? t("Jan '{yy}", { yy: String(year).slice(2) }) : d.toLocaleDateString(dateLocale("en-GB"), { month: "short" });
}

function MonthTooltip({ active, payload }: { active?: boolean; payload?: { payload: DividendMonth }[] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const received = toNumber(row.received_eur) ?? 0;
  const expected = toNumber(row.expected_eur) ?? 0;
  return (
    <div className="rounded-lg border border-ui-border bg-ui-surface px-3 py-2 text-xs shadow-sm">
      <div className="mb-0.5 font-semibold text-ui-ink">{monthLabel(row.month, true)}</div>
      {received > 0 && <div className="text-ui-ink-soft">{t("Received")}{" "}{formatEur(received)}</div>}
      {expected > 0 && <div className="text-ui-ink-soft">{t("Expected")}{" "}{formatEur(expected)}</div>}
      {received === 0 && expected === 0 && <div className="text-ui-ink-soft">{t("Nothing")}</div>}
    </div>
  );
}

/** Received bars in the brand colour, expected ones in its soft tint with a dashed outline: one
 * measure in two states, told apart by the legend and the tooltip too, never by colour alone. */
function MonthChart({ months }: { months: DividendMonth[] }) {
  const rows = months.map((m) => ({ ...m, received: toNumber(m.received_eur) ?? 0, expected: toNumber(m.expected_eur) ?? 0 }));
  return (
    <div className="kit-income h-60">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="month" tickFormatter={(m: string) => monthLabel(m)} tick={{ fontSize: 12 }} tickLine={false} interval="preserveStartEnd" minTickGap={6} />
          <YAxis tick={{ fontSize: 12 }} axisLine={false} tickLine={false} width={48} tickFormatter={(v: number) => formatEur(v, true)} />
          <Tooltip content={<MonthTooltip />} />
          <Legend verticalAlign="top" align="right" height={28} iconType="square" iconSize={10} wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="received" name={t("Received")} stackId="m" className="received" maxBarSize={22} isAnimationActive={false} />
          <Bar dataKey="expected" name={t("Expected")} stackId="m" className="expected" radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function HoldingRow({ holding: h }: { holding: DividendHolding }) {
  const lastPaid = h.last_paid_on && t("last {date}", { date: formatDate(h.last_paid_on, { day: "numeric", month: "short", year: "numeric" }) });
  const details = h.is_held
    ? [
        t("{n}× in 12 months", { n: h.payments_12m }),
        lastPaid,
        h.current_yield_pct !== null && t("{pct} yield", { pct: formatPct(h.current_yield_pct, 2, false) }),
        h.yield_on_cost_pct !== null && t("{pct} on cost", { pct: formatPct(h.yield_on_cost_pct, 2, false) }),
      ]
    : [t("received in total"), lastPaid];
  return (
    <li className="flex flex-col gap-0.5 border-b border-ui-border py-2.5 last:border-0">
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 truncate text-[15px] font-semibold text-ui-ink">{h.name}</span>
        <span className="shrink-0 text-[15px] font-semibold tabular-nums text-ui-ink">
          {formatEur(h.is_held ? h.expected_12m_eur : h.received_total_eur)}
          {h.is_held && <span className="font-normal text-ui-muted">{" "}{t("expected")}</span>}
        </span>
      </div>
      <span className="text-xs tabular-nums text-ui-muted">{details.filter(Boolean).join(" · ")}</span>
    </li>
  );
}

/** What the coming year rests on, then -- folded away -- holdings sold since they paid. */
function HoldingsList({ income }: { income: DividendIncome }) {
  const held = income.holdings.filter((h) => h.is_held);
  const sold = income.holdings.filter((h) => !h.is_held);
  return (
    <div className="flex flex-col gap-2">
      {held.length > 0 ? (
        <ul className="m-0 flex list-none flex-col p-0" aria-label={t("Dividends by holding")}>
          {held.map((h) => (
            <HoldingRow key={h.asset_id} holding={h} />
          ))}
        </ul>
      ) : (
        <p className="m-0 text-sm text-ui-muted">{t("None of the holdings you have now has paid a dividend yet.")}</p>
      )}
      {sold.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer py-1 font-semibold text-ui-ink-soft">{t("Sold holdings ({length})", { length: sold.length })}</summary>
          <ul className="m-0 flex list-none flex-col p-0 opacity-75" aria-label={t("Sold holdings")}>
            {sold.map((h) => (
              <HoldingRow key={h.asset_id} holding={h} />
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function YearsList({ income }: { income: DividendIncome }) {
  return (
    <ul className="m-0 flex list-none flex-col p-0" aria-label={t("Dividends per year")}>
      {income.years.map((y, i) => {
        const previous = income.years[i + 1];
        const growth =
          previous && (toNumber(previous.total_eur) ?? 0) > 0
            ? ((toNumber(y.total_eur) ?? 0) / (toNumber(previous.total_eur) ?? 1) - 1) * 100
            : null;
        return (
          <li key={y.year} className="flex items-center justify-between gap-3 border-b border-ui-border py-2.5 last:border-0">
            <span className="text-[15px] font-semibold text-ui-ink">
              {y.year}
              {y.year === new Date(income.as_of).getFullYear() && <span className="font-normal text-ui-muted">{" "}{t("· so far")}</span>}
            </span>
            <span className="flex items-baseline gap-2 tabular-nums">
              {growth !== null && <span className="text-xs text-ui-muted">{formatPct(growth, 0)}{" "}{t("vs")}{" "}{previous.year}</span>}
              <span className="text-[15px] font-semibold text-ui-ink">{formatEur(y.total_eur)}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** gainr's Income page: dividends received per month, year and holding, and what the current
 * holdings are expected to pay over the next 12 months -- all derived from the ledger by the
 * backend (docs/adr/0041). */
export default function Income() {
  const { portfolioId, portfolios } = usePortfolio();
  const portfolioName = portfolios.find((p) => p.id === portfolioId)?.name;
  const incomeQuery = useQuery({
    queryKey: ["dividend-income", portfolioId],
    queryFn: () => api.getDividendIncome(portfolioId!),
    enabled: portfolioId !== null,
  });
  const income = incomeQuery.data;

  return (
    <div className="flex flex-col gap-4 sm:gap-6">
      <div className="flex flex-col gap-4">
        <div className="sm:hidden">
          <GainrTopRow />
        </div>
        <PageTitle>{t("Income")}{portfolioName && <span className="text-ui-ink-soft"> ({portfolioName})</span>}
        </PageTitle>
      </div>

      {incomeQuery.isPending ? (
        <div className={cardClass} role="status">{t("Loading dividends…")}</div>
      ) : incomeQuery.isError ? (
        <div className={cardClass} role="alert">{t("Could not load the dividends.")}{" "}
          <button type="button" onClick={() => incomeQuery.refetch()} className="font-semibold text-ui-ink underline">{t("Try again")}</button>
        </div>
      ) : income && income.years.length === 0 ? (
        <div className={cardClass}>
          <p className="m-0 font-display text-lg font-bold text-ui-ink">{t("No dividends yet")}</p>
          <p className="m-0 mt-1">{t("Dividends you book on Transactions, or that a broker sync books, show up here per month and per holding.")}</p>
        </div>
      ) : (
        income && (
          <>
            <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
              <SummaryTile label={t("Last 12 months")} value={formatEur(income.received_12m_eur)} sub={t("received")} />
              <SummaryTile label={t("Next 12 months")} value={formatEur(income.expected_12m_eur)} sub={t("expected from {n} holdings", { n: income.paying_holdings })} />
              <SummaryTile
                label={t("{year} so far", { year: new Date(income.as_of).getFullYear() })}
                value={formatEur(income.received_this_year_eur)}
                sub={t("{amount} in {year}", { amount: formatEur(income.received_last_year_eur), year: new Date(income.as_of).getFullYear() - 1 })}
              />
              <SummaryTile
                label={t("Yield")}
                value={formatPct(income.current_yield_pct, 2, false)}
                sub={income.yield_on_cost_pct !== null ? t("{pct} on cost", { pct: formatPct(income.yield_on_cost_pct, 2, false) }) : undefined}

              />
            </div>

            <CollapsibleCard
              storageKey="income-months"
              title={t("Dividends per month")}
              info={
                <>{t("The last 12 months as received, then the next 12 as expected. The expectation repeats the last 12 months: each payment per share, times the shares you hold now, in the same month a year later. A holding bought since then expects nothing yet, and a cut or raise only shows after its next payment. Amounts are what was booked in euros, after withholding tax.")}</>
              }
            >
              <MonthChart months={income.months} />
            </CollapsibleCard>

            <CollapsibleCard storageKey="income-holdings" title={t("By holding")} meta={<span className="text-sm text-ui-muted">{income.holdings.filter((h) => h.is_held).length}{" "}{t("held")}</span>}>
              <HoldingsList income={income} />
            </CollapsibleCard>

            <CollapsibleCard storageKey="income-years" title={t("Per year")}>
              <YearsList income={income} />
            </CollapsibleCard>
          </>
        )
      )}
    </div>
  );
}
