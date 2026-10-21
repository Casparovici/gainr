import { useState } from "react";

import AssetLogo from "./AssetLogo";
import CollapsibleCard from "./CollapsibleCard";
import SortableHeader from "./SortableHeader";
import { useTableSort, type SortAccessors } from "../hooks/useTableSort";
import type { ClosedPosition } from "../api/types";
import { formatDate, formatEur, pnlColorClass, toNumber } from "../utils/format";
import { QueryError } from "./ui/QueryError";
import { t } from "../i18n";

type SortKey = "name" | "sold_on" | "bought" | "sold" | "realized";

const ACCESSORS: SortAccessors<ClosedPosition, SortKey> = {
  name: (p) => p.name,
  sold_on: (p) => p.last_sell_date,
  bought: (p) => toNumber(p.total_bought),
  sold: (p) => toNumber(p.total_sold),
  realized: (p) => toNumber(p.realized_pnl_eur),
};

export default function ClosedPositions({
  positions,
  isLoading,
  isError = false,
  onRetry,
}: {
  positions: ClosedPosition[] | undefined;
  isLoading: boolean;
  isError?: boolean;
  onRetry?: () => void;
}) {
  const { rows, sort, toggle } = useTableSort(positions, ACCESSORS, { key: "sold_on", direction: "desc" });
  const [scrolled, setScrolled] = useState(false);

  return (
    <CollapsibleCard
      cardClassName="rounded-2xl border border-ui-border bg-ui-surface"
      storageKey="closed-positions"
      title={positions ? t("Closed positions ({n})", { n: positions.length }) : t("Closed positions")}

      defaultOpen={false}
      bodyClassName="border-t border-slate-200"
    >
      <div
        className={`overflow-x-auto ${scrolled ? "pinned-col-scrolled" : ""}`}
        onScroll={(e) => setScrolled(e.currentTarget.scrollLeft > 0)}
      >
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
              <SortableHeader label={t("Name")} sortKey="name" sort={sort} onToggle={toggle} className="pinned-col" />
              <SortableHeader label={t("Held")} sortKey="sold_on" sort={sort} onToggle={toggle} />
              <SortableHeader label={t("Bought")} sortKey="bought" sort={sort} onToggle={toggle} align="right" />
              <SortableHeader label={t("Sold")} sortKey="sold" sort={sort} onToggle={toggle} align="right" />
              <SortableHeader label={t("Realized P&L")} sortKey="realized" sort={sort} onToggle={toggle} align="right" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">{t("Loading…")}</td>
              </tr>
            ) : isError ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center">
                  <QueryError message={t("Couldn't load closed positions.")} onRetry={onRetry} />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">{t("No closed positions")}</td>
              </tr>
            ) : (
              rows.map((p) => (
                <tr key={p.asset_id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                  {/* Pinned and capped at two lines on phones, same as Active positions. */}
                  <td className="pinned-col px-4 py-2.5">
                    <div className="flex items-center gap-2.5 max-sm:w-36" title={p.name}>
                      <AssetLogo assetId={p.asset_id} name={p.name} ticker={p.ticker} />
                      <div className="min-w-0">
                        <div className="font-medium text-slate-900 max-sm:line-clamp-2 max-sm:leading-snug">{p.name}</div>
                        <div className="text-xs text-slate-500 max-sm:truncate">{p.ticker}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">
                    <span className="whitespace-nowrap">{p.first_buy_date && formatDate(p.first_buy_date)} –</span>{" "}
                    <span className="whitespace-nowrap">{p.last_sell_date && formatDate(p.last_sell_date)}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{formatEur(p.total_bought)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{formatEur(p.total_sold)}</td>
                  <td className={`px-4 py-2.5 text-right tabular-nums font-medium ${pnlColorClass(p.realized_pnl_eur)}`}>
                    {formatEur(p.realized_pnl_eur)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </CollapsibleCard>
  );
}
