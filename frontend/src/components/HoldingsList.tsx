import { useState } from "react";

import type { Position } from "../api/types";
import { formatEur, formatPct, formatQuantity, pnlColorClass, toNumber } from "../utils/format";
import AssetLogo from "./AssetLogo";
import WeightBar, { weightScale } from "./WeightBar";
import { QueryError } from "./ui/QueryError";
import { msg, t } from "../i18n";

type SortKey = "value" | "today" | "pnl" | "drift";

const SORTS: { key: SortKey; label: string; value: (p: Position) => number | null }[] = [
  { key: "value", label: msg("Value"), value: (p) => toNumber(p.market_value_eur) },
  // Biggest losers first for the moves: the case worth a look comes up without scrolling.
  { key: "today", label: msg("Today, worst first"), value: (p) => negate(toNumber(p.day_change_pct)) },
  { key: "pnl", label: msg("Unrealized, worst first"), value: (p) => negate(toNumber(p.unrealized_pnl_pct)) },
  { key: "drift", label: msg("Furthest from target"), value: (p) => abs(toNumber(p.target_weight_diff_pct)) },
];

function negate(n: number | null) {
  return n === null ? null : -n;
}
function abs(n: number | null) {
  return n === null ? null : Math.abs(n);
}

/** Active positions on a phone: one row per holding with what it's worth, today's move and its
 * weight against its target -- the table's essentials without sideways scrolling. A tap opens
 * the holding's detail panel, as a table row does on a wider screen. Cash always comes last. */
export default function HoldingsList({
  positions,
  isLoading,
  isError = false,
  onRetry,
  onSelect,
  onRebalance,
}: {
  positions: Position[] | undefined;
  isLoading: boolean;
  isError?: boolean;
  onRetry?: () => void;
  onSelect: (position: Position) => void;
  onRebalance?: () => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("value");
  const sort = SORTS.find((s) => s.key === sortKey) ?? SORTS[0];
  const holdings = (positions ?? []).filter((p) => p.ticker !== "CASH");
  const cash = (positions ?? []).find((p) => p.ticker === "CASH");
  const ordered = [...holdings].sort((a, b) => (sort.value(b) ?? -Infinity) - (sort.value(a) ?? -Infinity));
  const rows = cash ? [...ordered, cash] : ordered;
  const scale = weightScale(positions ?? []);

  return (
    <section aria-label={t("Holdings")} className="overflow-hidden rounded-2xl border border-ui-border bg-ui-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 pb-2 pt-3.5">
        <h2 className="m-0 font-display text-xl font-bold tracking-[-0.01em] text-ui-ink">{t("Holdings")}{positions ? <span className="ml-1.5 text-ui-muted">{holdings.length}</span> : null}
        </h2>
        <div className="flex items-center gap-2">
          {onRebalance && positions?.some((p) => p.target_weight_pct !== null) && (
            <button
              type="button"
              onClick={onRebalance}
              className="h-9 rounded-lg border border-ui-border px-2.5 text-[13px] font-semibold text-ui-ink-soft"
            >{t("Rebalance")}</button>
          )}
          <label className="sr-only" htmlFor="holdings-sort">{t("Sort holdings")}</label>
          <select
            id="holdings-sort"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="h-9 max-w-[11rem] rounded-lg border border-ui-border bg-ui-surface pl-2.5 text-[13px] font-semibold text-ui-ink-soft"
          >
            {SORTS.map((s) => (
              <option key={s.key} value={s.key}>
                {t(s.label)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-px px-4 pb-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="my-1.5 h-12 animate-pulse rounded-xl bg-ui-tile" />
          ))}
        </div>
      ) : isError ? (
        <div className="px-4 pb-4 text-sm">
          <QueryError message={t("Couldn't load positions.")} onRetry={onRetry} />
        </div>
      ) : holdings.length === 0 ? (
        <p className="m-0 px-4 pb-4 text-[15px] text-ui-muted">{t("No holdings yet. Add a buy on Transactions to see it here.")}</p>
      ) : (
        <ul className="m-0 list-none p-0">
          {rows.map((p) => {
            const isCash = p.ticker === "CASH";
            return (
              <li key={p.asset_id} className="border-t border-ui-line/60">
                <button
                  type="button"
                  onClick={() => onSelect(p)}
                  className="flex w-full flex-col gap-2 px-4 py-3 text-left hover:bg-ui-tile/60"
                >
                  <span className="flex w-full items-center gap-3">
                    <AssetLogo assetId={p.asset_id} name={p.name} ticker={p.ticker} size={36} />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-[15px] font-semibold text-ui-ink">{p.name}</span>
                      <span className="truncate text-[13px] text-ui-muted">
                        {isCash ? t("Across your brokers") : `${p.ticker} · ${formatQuantity(p.quantity)}`}
                        {p.price_stale && <span className="text-ui-late">{" "}{t("· last known price")}</span>}
                      </span>
                    </span>
                    <span className="flex shrink-0 flex-col items-end">
                      <span className="text-[15px] font-semibold tabular-nums text-ui-ink">{formatEur(p.market_value_eur)}</span>
                      {!isCash && (
                        <span className={`text-[13px] font-semibold tabular-nums ${pnlColorClass(p.day_change_pct)}`}>
                          {p.day_change_pct === null ? "—" : t("{pct} today", { pct: formatPct(p.day_change_pct) })
}
                        </span>
                      )}
                    </span>
                  </span>
                  <WeightBar weight={p.weight_pct} target={p.target_weight_pct} scale={scale} />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
