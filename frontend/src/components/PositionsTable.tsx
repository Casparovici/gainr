import { useState, type ReactNode } from "react";

import AssetLogo from "./AssetLogo";
import ColumnPicker from "./ColumnPicker";
import SortableHeader from "./SortableHeader";
import TargetWeightInput from "./TargetWeightInput";
import { useColumnVisibility } from "../hooks/useColumnVisibility";
import { useTableSort, type SortAccessors, type SortValue } from "../hooks/useTableSort";
import type { DltJudgment, Position } from "../api/types";
import {
  formatCurrency,
  formatDate,
  formatEur,
  formatPct,
  formatQuantity,
  formatWeight,
  pnlColorClass,
  todayIsoDate,
  toNumber,
} from "../utils/format";

// Same badge shape gripr uses for its expense/income/transfer pills, reused here so the two
// halves of the app read as one visual language rather than inventing a second rating style.
const DLT_BADGE: Record<DltJudgment, { label: string; className: string }> = {
  attractive: { label: "Attractive", className: "bg-emerald-50 text-emerald-700" },
  neutral: { label: "Neutral", className: "bg-slate-100 text-slate-600" },
  critical: { label: "Critical", className: "bg-red-50 text-red-700" },
};

type ColumnKey =
  | "name"
  | "quantity"
  | "price"
  | "value"
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
  render: (p: Position, isCash: boolean, onSelect: (p: Position) => void) => ReactNode;
}

const COLUMNS: readonly Column[] = [
  {
    key: "name",
    label: "Name",
    align: "left",
    fixed: true,
    sortValue: (p) => p.name,
    // On phones the name is pinned (see `.pinned-col`) and capped at two lines in a fixed width,
    // so a long fund name can't swallow the screen -- the full name is one tap away in its card.
    render: (p, _isCash, onSelect) => (
      <div className="flex items-center gap-2.5 max-sm:w-36" title={p.name}>
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
            <div className="text-xs text-amber-600 max-sm:truncate">price unavailable, using last known</div>
          )}
        </div>
      </div>
    ),
  },
  {
    key: "quantity",
    label: "Quantity",
    align: "right",
    sortValue: (p) => toNumber(p.quantity),
    render: (p, isCash) => (isCash ? "—" : formatQuantity(p.quantity)),
  },
  {
    key: "price",
    label: "Price",
    align: "right",
    sortValue: (p) => toNumber(p.current_price_native),
    className: () => "text-slate-600",
    render: (p, isCash) => (isCash ? "—" : formatCurrency(p.current_price_native, p.native_currency)),
  },
  {
    key: "value",
    label: "Value",
    align: "right",
    sortValue: (p) => toNumber(p.market_value_eur),
    className: () => "font-medium",
    render: (p) => formatEur(p.market_value_eur),
  },
  {
    key: "unrealized",
    label: "Unrealized P&L",
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
    label: "Realized P&L",
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
    label: "Weight",
    align: "right",
    sortValue: (p) => toNumber(p.weight_pct),
    className: () => "text-slate-500",
    render: (p) => formatWeight(p.weight_pct),
  },
  {
    key: "targetWeight",
    label: "Target",
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
    label: "Drift",
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
    label: "DLT Rating",
    align: "left",
    // Best first when sorted ascending, rather than alphabetical ("attractive" < "critical" <
    // "neutral"), which would bury the calls that actually matter in the middle of the table.
    // No coverage sorts alongside an explicit "neutral" call -- same badge, same rank.
    sortValue: (p) => ({ attractive: 0, neutral: 1, critical: 2 })[p.dlt_judgment ?? "neutral"],
    render: (p) => {
      const badge = DLT_BADGE[p.dlt_judgment ?? "neutral"];
      return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}>{badge.label}</span>;
    },
  },
] as const;

const ACCESSORS = Object.fromEntries(COLUMNS.map((c) => [c.key, c.sortValue])) as SortAccessors<Position, ColumnKey>;
const ALWAYS_ON = COLUMNS.filter((c) => c.fixed).map((c) => c.key);

export default function PositionsTable({
  positions,
  isLoading,
  onSelect,
}: {
  positions: Position[] | undefined;
  isLoading: boolean;
  onSelect: (position: Position) => void;
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

  // Holdings legitimately carry different price dates: crypto prices around the clock, and
  // while Amsterdam is trading, New York hasn't opened yet. Reporting whichever row happened
  // to sort first as the whole table's date was simply wrong — so report the span, which also
  // makes a holding that's genuinely stuck days behind visible instead of silently blended in.
  const priceDates = (positions ?? []).map((p) => p.price_date).filter((d): d is string => d !== null);
  const latestPriceDate = priceDates.length ? priceDates.reduce((a, b) => (a > b ? a : b)) : undefined;
  const oldestPriceDate = priceDates.length ? priceDates.reduce((a, b) => (a < b ? a : b)) : undefined;
  // "Close" is only true once the day is over; mid-session that newest price is a live one.
  const latestIsToday = latestPriceDate === todayIsoDate();

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-700">
        <span>Active positions {positions ? `(${positions.length})` : ""}</span>
        <div className="flex items-center gap-3">
          {latestPriceDate && oldestPriceDate && (
            <span className="text-xs font-normal text-slate-400">
              {latestPriceDate === oldestPriceDate
                ? `prices as of ${formatDate(latestPriceDate)}${latestIsToday ? "" : " close"}`
                : `prices as of ${formatDate(latestPriceDate)}, oldest ${formatDate(oldestPriceDate)}`}
            </span>
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
                  label={column.label}
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
                <td colSpan={visible.length} className="px-4 py-6 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={visible.length} className="px-4 py-6 text-center text-slate-400">
                  No active positions
                </td>
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
                        {column.render(p, isCash, onSelect)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
