import type { Summary } from "../api/types";
import { formatEur, formatPct, formatSignedEur, pnlColorClass } from "../utils/format";
import { headline, type Headline } from "../utils/performanceHeadline";
import { t } from "../i18n";

interface Figure {
  label: string;
  value: string;
  tone?: string;
  hint?: string;
}

function figures(summary: Summary): Figure[] {
  // The performance figures lead with the money-weighted return (docs/adr/0051); where no such rate
  // exists the time-weighted one stands in, and the hint says which it is.
  const year = headline({ mwr: summary.ytd_mwr_pct, twr: summary.ytd_return_pct });
  const start = headline({ mwr: summary.total_mwr_pct, mwrYearly: summary.total_mwr_yearly_pct, twr: summary.total_return_pct });
  const pct = (h: Headline) => (h.perYear ? t("{pct}/yr", { pct: formatPct(h.pct) }) : formatPct(h.pct));
  return [
    {
      label: t("This year"),
      value: `${pct(year)} · ${formatSignedEur(summary.ytd_return_eur, true)}`,
      tone: pnlColorClass(summary.ytd_return_eur),
      hint: year.moneyWeighted
        ? t("Money-weighted: what the portfolio returned on the money in it, with the timing of your deposits. Time-weighted {pct}", { pct: formatPct(summary.ytd_return_pct) })
        : t("Time-weighted: deposits and withdrawals don't count as performance"),
    },
    {
      label: t("Since start"),
      value: `${pct(start)} · ${formatSignedEur(summary.total_return_eur, true)}`,
      tone: pnlColorClass(summary.total_return_eur),
      hint: start.moneyWeighted
        ? t("Money-weighted, per year once there is a year of history. Total value against everything paid in: {pct}", { pct: formatPct(summary.total_return_pct) })
        : t("Total value against everything paid in"),
    },
    // Unrealized and realized split the total return by whether it's been banked yet -- the pair
    // matters more than either number alone, so they share a line.
    {
      label: t("Unrealized · realized"),
      value: `${formatEur(summary.unrealized_pnl_eur, true)} · ${formatEur(summary.realized_pnl_eur, true)}`,
      hint: t("Unrealized {pct} on open positions; realized is banked on sales, excluding dividends", { pct: formatPct(summary.unrealized_pnl_pct) }),

    },
    { label: t("Cash · invested"), value: `${formatEur(summary.cash_eur, true)} · ${formatEur(summary.total_invested_eur, true)}` },
  ];
}

/** The figures behind the headline value. On a phone a strip of four small tiles under the hero;
 * on a wide screen (`layout="list"`) a card in the side column. */
export default function HomeFigures({ summary, layout = "tiles" }: { summary: Summary | undefined; layout?: "tiles" | "list" }) {
  if (layout === "list") {
    return (
      <section aria-label={t("Figures")} className="rounded-2xl border border-ui-border bg-ui-surface px-4 py-3.5">
        <h2 className="m-0 mb-2 text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">{t("Figures")}</h2>
        {summary ? (
          <dl className="m-0 flex flex-col gap-2 text-sm">
            {figures(summary).map((f) => (
              <div key={f.label} className="flex items-baseline justify-between gap-3" title={f.hint}>
                <dt className="text-ui-ink-soft">{f.label}</dt>
                <dd className={`m-0 text-right font-semibold tabular-nums ${f.tone ?? "text-ui-ink"}`}>{f.value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <div className="h-28 animate-pulse rounded-xl bg-ui-tile" />
        )}
      </section>
    );
  }
  return (
    <dl aria-label={t("Figures")} className="m-0 grid grid-cols-2 gap-2 sm:grid-cols-4">
      {summary
        ? figures(summary).map((f) => (
            <div key={f.label} className="flex min-w-0 flex-col gap-0.5 rounded-xl border border-ui-border bg-ui-surface px-3 py-2.5" title={f.hint}>
              <dt className="text-xs text-ui-muted">{f.label}</dt>
              <dd className={`m-0 truncate text-[15px] font-semibold tabular-nums ${f.tone ?? "text-ui-ink"}`}>{f.value}</dd>
            </div>
          ))
        : Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-[60px] animate-pulse rounded-xl bg-ui-tile" />)}
    </dl>
  );
}
