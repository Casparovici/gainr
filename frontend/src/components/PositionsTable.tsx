import { useState, type ReactNode } from "react";

import AssetLogo from "./AssetLogo";
import ColumnPicker from "./ColumnPicker";
import SortableHeader from "./SortableHeader";
import TargetWeightInput from "./TargetWeightInput";
import { useColumnVisibility } from "../hooks/useColumnVisibility";
import { useTableSort, type SortAccessors, type SortValue } from "../hooks/useTableSort";
import type { Position } from "../api/types";
import {
  formatCurrency,
  formatEur,
  formatPct,
  formatQuantity,
  formatSignedEur,
  formatWeight,
  pnlColorClass,
  toNumber,
} from "../utils/format";
import DltBadge from "./DltBadge";
import WeightBar, { weightScale } from "./WeightBar";
import { QueryError } from "./ui/QueryError";
import { msg, t } from "../i18n";

type ColumnKey =
  | "name"
  | "quantity"
  | "price"
  | "value"
  | "today"
  | "unrealized"
  | "realized"
  | "weight"
  | "targetWeight"
  | "targetDrift"
  | "dlt";

// New, niche columns default to off rather than adding clutter every reader has to notice and
// dismiss — someone who actually wants it opts in once via the column picker, same as turning
// any other column back on.
const DEFAULT_HIDDEN: readonly ColumnKey[] = ["targetDrift"];

interface Column {
  key: ColumnKey;
  label: string;
  align: "left" | "right";
  /** The name carries the row's identity and is the control that opens its card, so it stays. */
  fixed?: boolean;
  sortValue: (p: Position) => SortValue;
  className?: (p: Position, isCash: boolean) => string;
  /** `scale` is the weight that fills a weight bar (see WeightBar), shared by every row. */
  render: (p: Position, isCash: boolean, onSelect: (p: Position) => void, scale: number) => ReactNode;
}

const COLUMNS: readonly Column[] = [
  {
    key: "name",
    label: msg("Name"),
    align: "left",
    fixed: true,
    sortValue: (p) => p.name,
    // On phones the name is pinned (see `.pinned-col`) and capped at two lines in a fixed width,
    // so a long fund name can't swallow the screen -- the full name is one tap away in its card.
    render: (p, _isCash, onSelect) => (
      <div className="flex items-center gap-2.5 max-sm:w-36 sm:min-w-[12rem]" title={p.name}>
        <AssetLogo assetId={p.asset_id} name={p.name} ticker={p.ticker} />
        <div className="min-w-0">
          {/* The whole row is clickable for convenience, but the name is the real control —
              a <tr> can't be tabbed to or announced as one. Cash opens the same detail panel
              as any other row (its per-broker breakdown and the Transfer action live there). */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onSelect(p);
            }}
            className="text-left font-medium text-slate-900 hover:text-blue-700 hover:underline max-sm:line-clamp-2 max-sm:leading-snug"
          >
            {p.name}
          </button>
          {p.price_stale && (
            <div className="text-xs text-amber-600 max-sm:truncate">{t("price unavailable, using last known")}</div>
          )}
        </div>
      </div>
    ),
  },
  {
    key: "quantity",
    label: msg("Quantity"),
    align: "right",
    sortValue: (p) => toNumber(p.quantity),
    render: (p, isCash) => (isCash ? "—" : formatQuantity(p.quantity)),
  },
  {
    key: "price",
    label: msg("Price"),
    align: "right",
    sortValue: (p) => toNumber(p.current_price_native),
    className: () => "text-slate-600",
    render: (p, isCash) => (isCash ? "—" : formatCurrency(p.current_price_native, p.native_currency)),
  },
  {
    key: "value",
    label: msg("Value"),
    align: "right",
    sortValue: (p) => toNumber(p.market_value_eur),
    className: () => "font-medium",
    render: (p) => formatEur(p.market_value_eur),
  },
  {
    key: "today",
    label: msg("Today"),
    align: "right",
    // On the percentage, like Unrealized: it ranks holdings regardless of size.
    sortValue: (p) => toNumber(p.day_change_pct),
    className: (p, isCash) => `whitespace-nowrap ${isCash ? "text-slate-400" : `font-medium ${pnlColorClass(p.day_change_pct)}`}`,
    render: (p, isCash) =>
      isCash || p.day_change_pct === null ? (
        "—"
      ) : (
        <>
          {formatPct(p.day_change_pct)}
          <span className="ml-1 text-xs font-normal">({formatSignedEur(p.day_change_eur)})</span>
        </>
      ),
  },
  {
    key: "unrealized",
    label: msg("Unrealized P&L"),
    align: "right",
    // Sorted on the percentage rather than the euro amount: it's the one that ranks holdings
    // against each other regardless of position size.
    sortValue: (p) => toNumber(p.unrealized_pnl_pct),
    className: (p, isCash) => (isCash ? "text-slate-400" : pnlColorClass(p.unrealized_pnl_eur)),
    render: (p, isCash) =>
      isCash ? (
        "—"
      ) : (
        <>
          {formatEur(p.unrealized_pnl_eur)}
          <span className="ml-1 text-xs">({formatPct(p.unrealized_pnl_pct)})</span>
        </>
      ),
  },
  {
    key: "realized",
    label: msg("Realized P&L"),
    align: "right",
    sortValue: (p) => toNumber(p.realized_pnl_eur),
    // Most open positions have never been sold out of, and a column of €0,00 would drown the
    // handful that carry a real banked gain.
    className: (p, isCash) =>
      isCash || (toNumber(p.realized_pnl_eur) ?? 0) === 0 ? "text-slate-300" : pnlColorClass(p.realized_pnl_eur),
    render: (p, isCash) => (isCash || (toNumber(p.realized_pnl_eur) ?? 0) === 0 ? "—" : formatEur(p.realized_pnl_eur)),
  },
  {
    key: "weight",
    label: msg("Weight · target"),
    align: "left",
    sortValue: (p) => toNumber(p.weight_pct),
    className: () => "min-w-[9rem]",
    render: (p, _isCash, _onSelect, scale) => <WeightBar weight={p.weight_pct} target={p.target_weight_pct} scale={scale} showTarget={false} />,
  },
  {
    key: "targetWeight",
    label: msg("Target"),
    align: "right",
    sortValue: (p) => toNumber(p.target_weight_pct),
    className: () => "text-slate-500",
    render: (p, isCash) =>
      // Cash has no position detail card to redirect edits to (it's a derived row, not a real
      // asset), so its target stays editable right here -- shown as the same plain text as every
      // other row until clicked. Every real holding's target is edited from its own detail card
      // instead, so a stray click in this table can't change it.
      isCash ? <TargetWeightInput position={p} asText /> : formatWeight(p.target_weight_pct),
  },
  {
    key: "targetDrift",
    label: msg("Drift"),
    align: "right",
    // By percentage points, not the euro amount: it's the reading that ranks holdings against
    // each other regardless of position size, the same reason "unrealized" sorts on its % too.
    sortValue: (p) => toNumber(p.target_weight_diff_pct),
    className: () => "text-slate-500",
    render: (p) =>
      p.target_weight_diff_pct === null ? (
        "—"
      ) : (
        <>
          {formatPct(p.target_weight_diff_pct, 1)}
          <span className="ml-1 text-xs text-slate-400">({formatEur(p.target_weight_diff_eur)})</span>
        </>
      ),
  },
  {
    key: "dlt",
    label: msg("DLT Rating"),
    align: "left",
    // Best first when sorted ascending, rather than alphabetical ("attractive" < "critical" <
    // "neutral"), which would bury the calls that actually matter in the middle of the table.
    // No coverage sorts alongside an explicit "neutral" call -- same badge, same rank.
    sortValue: (p) => ({ attractive: 0, neutral: 1, critical: 2 })[p.dlt_judgment ?? "neutral"],
    // Cash isn't a security DLT rates, so it gets no badge rather than a "Neutral" look.
    render: (p, isCash) => (isCash ? <span className="text-slate-300">—</span> : <DltBadge judgment={p.dlt_judgment} />),
  },
] as const;

const ACCESSORS = Object.fromEntries(COLUMNS.map((c) => [c.key, c.sortValue])) as SortAccessors<Position, ColumnKey>;
const ALWAYS_ON = COLUMNS.filter((c) => c.fixed).map((c) => c.key);

export default function PositionsTable({
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
  /** Opens the rebalance helper; the button only shows once a holding has a target. */
  onRebalance?: () => void;
}) {
  const { isHidden, toggle: toggleColumn, showAll, hiddenCount } = useColumnVisibility<ColumnKey>(
    "positions",
    ALWAYS_ON,
    DEFAULT_HIDDEN,
  );

  const visible = COLUMNS.filter((c) => !isHidden(c.key));
  // Drives the fade on the pinned name column's edge -- only once there's something behind it.
  const [scrolled, setScrolled] = useState(false);

  // Column choices are remembered but the sort isn't, so a reader who hid Value last visit
  // comes back to a table whose default sort is on a column that isn't rendered — ordered by
  // something invisible, with no header carrying the indicator. Only read on first render,
  // which is the one that matters; later hides are handled in onToggleColumn below.
  const defaultSort = COLUMNS.find((c) => c.key === "value" && !isHidden(c.key)) ?? visible[0] ?? COLUMNS[0];
  const { rows, sort, toggle, setSort } = useTableSort(positions, ACCESSORS, {
    key: defaultSort.key,
    direction: defaultSort.align === "left" ? "asc" : "desc",
  });

  const onToggleColumn = (key: ColumnKey) => {
    // Hiding the column the table is sorted by would leave it ordered by something the reader
    // can no longer see, so the sort moves to the first column still on screen.
    if (!isHidden(key) && sort.key === key) {
      const fallback = COLUMNS.find((c) => c.key !== key && !isHidden(c.key));
      if (fallback) setSort({ key: fallback.key, direction: fallback.align === "left" ? "asc" : "desc" });
    }
    toggleColumn(key);
  };

  const scale = weightScale(positions ?? []);
  const holdingCount = positions?.filter((p) => p.ticker !== "CASH").length;

  return (
    <section aria-label={t("Holdings")} className="overflow-hidden rounded-2xl border border-ui-border bg-ui-surface">
      <div className="flex items-center justify-between gap-3 px-4 py-3.5">
        <h2 className="m-0 font-display text-xl font-bold tracking-[-0.01em] text-ui-ink">{t("Holdings")}{holdingCount !== undefined && <span className="ml-1.5 text-ui-muted">{holdingCount}</span>}
        </h2>
        <div className="flex items-center gap-3">
          {onRebalance && positions?.some((p) => p.target_weight_pct !== null) && (
            <button
              type="button"
              onClick={onRebalance}
              className="rounded-md border border-slate-200 px-2 py-1 text-xs font-normal text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-700"
            >{t("Rebalance")}</button>
          )}
          <ColumnPicker
            columns={COLUMNS}
            isHidden={isHidden}
            onToggle={onToggleColumn}
            onShowAll={showAll}
            hiddenCount={hiddenCount}
          />
        </div>
      </div>
      <div
        className={`overflow-x-auto ${scrolled ? "pinned-col-scrolled" : ""}`}
        onScroll={(e) => setScrolled(e.currentTarget.scrollLeft > 0)}
      >
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
              {visible.map((column) => (
                <SortableHeader
                  key={column.key}
                  label={t(column.label)}

                  sortKey={column.key}
                  sort={sort}
                  onToggle={toggle}
                  align={column.align}
                  className={column.fixed ? "pinned-col" : ""}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={visible.length} className="px-4 py-6 text-center text-slate-400">{t("Loading…")}</td>
              </tr>
            ) : isError ? (
              <tr>
                <td colSpan={visible.length} className="px-4 py-6 text-center">
                  <QueryError message={t("Couldn't load positions.")} onRetry={onRetry} />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={visible.length} className="px-4 py-6 text-center text-slate-400">{t("No active positions")}</td>
              </tr>
            ) : (
              rows.map((p) => {
                const isCash = p.ticker === "CASH";
                return (
                  <tr
                    key={p.asset_id}
                    onClick={() => onSelect(p)}
                    className="cursor-pointer border-b border-slate-50 last:border-0 hover:bg-slate-50"
                  >
                    {visible.map((column) => (
                      <td
                        key={column.key}
                        className={`px-4 py-2.5 ${column.align === "right" ? "text-right tabular-nums" : ""} ${
                          column.fixed ? "pinned-col" : ""
                        } ${column.className?.(p, isCash) ?? ""}`}
                      >
                        {column.render(p, isCash, onSelect, scale)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
