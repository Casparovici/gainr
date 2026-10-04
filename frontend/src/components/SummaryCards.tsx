import type { Summary } from "../api/types";
import { formatEur, formatPct, pnlColorClass } from "../utils/format";
import CollapsibleCard from "./CollapsibleCard";

function Card({ label, value, sub, subClass }: { label: string; value: string; sub?: string; subClass?: string }) {
  return (
    <div className="rounded-2xl bg-ui-tile p-3">
      <div className="text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">{label}</div>
      <div className="mt-1 font-display text-xl font-bold tabular-nums tracking-[-0.02em] text-ui-ink">{value}</div>
      {sub && <div className={`mt-0.5 text-xs font-medium tabular-nums ${subClass ?? "text-ui-muted"}`}>{sub}</div>}
    </div>
  );
}

export default function SummaryCards({ summary }: { summary: Summary }) {
  return (
    <CollapsibleCard
      storageKey="summary-cards"
      title="Summary"
      meta={
        <span className="text-[15px] font-semibold tabular-nums text-ui-ink">{formatEur(summary.total_value_eur)}</span>
      }
      bodyClassName="px-4 pb-4"
    >
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Card label="Total value" value={formatEur(summary.total_value_eur)} sub={`as of ${summary.as_of}`} />
        <Card
          label="YTD performance"
          value={formatPct(summary.ytd_return_pct)}
          sub={formatEur(summary.ytd_return_eur)}
          subClass={pnlColorClass(summary.ytd_return_eur)}
        />
        <Card
          label="Total return"
          value={formatPct(summary.total_return_pct)}
          sub={formatEur(summary.total_return_eur)}
          subClass={pnlColorClass(summary.total_return_eur)}
        />
        {/* Unrealized and realized split the total return by whether it's been banked yet —
            the pair matters more than either number alone, so they sit side by side. */}
        <Card
          label="Unrealized gains"
          value={formatEur(summary.unrealized_pnl_eur)}
          sub={`${formatPct(summary.unrealized_pnl_pct)} on open positions`}
          subClass={pnlColorClass(summary.unrealized_pnl_eur)}
        />
        <Card
          label="Realized gains"
          value={formatEur(summary.realized_pnl_eur)}
          sub="banked on sales, excl. dividends"
          subClass={pnlColorClass(summary.realized_pnl_eur)}
        />
        <Card label="Cash" value={formatEur(summary.cash_eur)} sub={`invested ${formatEur(summary.total_invested_eur)}`} />
      </div>
    </CollapsibleCard>
  );
}
