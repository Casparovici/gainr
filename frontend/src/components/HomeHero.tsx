import type { Position, Summary } from "../api/types";
import { formatEur, formatPct, formatSignedEur, pnlColorClass, todayIsoDate, toNumber } from "../utils/format";
import { pricesAsOfLabel } from "../utils/prices";
import { t } from "../i18n";

/** The top of gainr Home: what the portfolio is worth, how much it moved today, and how fresh
 * the prices behind that are. Today's move is the chart's 1D range (time-weighted, so a deposit
 * made today isn't counted as a gain), at the hourly live quotes while they're current. */
export default function HomeHero({
  summary,
  positions,
  portfolioName,
}: {
  summary: Summary | undefined;
  positions: Position[] | undefined;
  portfolioName: string | null;
}) {
  if (!summary) {
    return (
      <div className="flex flex-col gap-2 pt-1" aria-busy="true">
        <div className="h-4 w-36 animate-pulse rounded bg-ui-tile" />
        <div className="h-11 w-60 animate-pulse rounded-lg bg-ui-tile" />
        <div className="h-5 w-44 animate-pulse rounded bg-ui-tile" />
      </div>
    );
  }
  const dayEur = toNumber(summary.day_change_eur);
  const pricesAsOf = pricesAsOfLabel(positions ?? [], todayIsoDate());
  return (
    <section aria-label={t("Portfolio value")} className="flex flex-col gap-1.5 pt-1">
      <span className="text-sm font-semibold text-ui-ink-soft">{portfolioName ? t("{portfolio} · total value", { portfolio: portfolioName }) : t("Total value")}
</span>
      <span className="font-display text-[40px] font-bold leading-none tracking-[-0.03em] text-ui-ink tabular-nums sm:text-5xl">
        {formatEur(summary.total_value_eur)}
      </span>
      {dayEur === null ? (
        <span className="text-[15px] text-ui-muted">{t("No move today yet")}</span>
      ) : (
        <span className={`text-[17px] font-semibold tabular-nums ${pnlColorClass(dayEur)}`}>
          {formatSignedEur(summary.day_change_eur)} · {formatPct(summary.day_change_pct)}{" "}{t("today")}</span>
      )}
      {pricesAsOf && <span className="text-[13px] text-ui-muted">{pricesAsOf.charAt(0).toUpperCase() + pricesAsOf.slice(1)}</span>}
    </section>
  );
}
