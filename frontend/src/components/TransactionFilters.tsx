import { useState } from "react";

import type { TransactionType } from "../api/types";
import { TRANSACTION_TYPES } from "../api/types";
import { inputClass, primaryButtonClass, secondaryButtonClass } from "./ui/kit";
import Sheet from "./ui/Sheet";
import { t as tr } from "../i18n";

export interface TransactionFilterState {
  type: TransactionType | "";
  assetName: string;
  broker: string;
  dateFrom: string;
  dateTo: string;
}

export const EMPTY_FILTERS: TransactionFilterState = { type: "", assetName: "", broker: "", dateFrom: "", dateTo: "" };

// The types worth one tap; the rest are in the filter sheet's type list.
const CHIP_TYPES: TransactionType[] = ["Buy", "Sell", "Dividend", "Deposit"];

const chipClass = (on: boolean) =>
  `h-9 shrink-0 rounded-full px-3.5 text-sm font-semibold transition-colors ${
    on ? "bg-ui-ink text-ui-surface" : "border border-ui-line bg-ui-surface text-ui-ink hover:bg-ui-tile"
  }`;

/** gainr Transactions' filters, the way every list in the app filters: a search box, one row of
 * chips for the common types, and a Filter button that opens a sheet with the rest (broker,
 * dates, any type). Nothing takes up the screen until it's asked for. */
export default function TransactionFilters({
  filters,
  onChange,
  brokers,
}: {
  filters: TransactionFilterState;
  onChange: (filters: TransactionFilterState) => void;
  brokers: string[];
}) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const update = (patch: Partial<TransactionFilterState>) => onChange({ ...filters, ...patch });
  // The sheet's filters: what the chips and search box don't show.
  const sheetCount = [filters.broker, filters.dateFrom, filters.dateTo].filter(Boolean).length +
    (filters.type && !CHIP_TYPES.includes(filters.type) ? 1 : 0);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center gap-2">
        <label className="flex h-11 min-w-0 flex-1 items-center gap-2 rounded-xl border border-ui-line bg-ui-surface px-3 focus-within:border-ui-brand">
          <svg aria-hidden width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="shrink-0 text-ui-muted">
            <circle cx="11" cy="11" r="6" />
            <path d="m20 20-4-4" />
          </svg>
          <span className="sr-only">{tr("Search by asset")}</span>
          <input
            type="search"
            value={filters.assetName}
            onChange={(e) => update({ assetName: e.target.value })}
            placeholder={tr("Search by asset")}
            className="h-full min-w-0 flex-1 bg-transparent text-base text-ui-ink outline-none placeholder:text-ui-faint"
          />
        </label>
        <button type="button" onClick={() => setSheetOpen(true)} className={`${secondaryButtonClass} shrink-0`} aria-haspopup="dialog">
          <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M4 6h16M7 12h10M10 18h4" />
          </svg>{tr("Filter")}{sheetCount > 0 && <span className="rounded-full bg-ui-brand px-1.5 text-xs text-white">{sheetCount}</span>}
        </button>
      </div>

      <div role="group" aria-label={tr("Type")} className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-0.5 sm:mx-0 sm:flex-wrap sm:px-0">
        <button type="button" aria-pressed={filters.type === ""} onClick={() => update({ type: "" })} className={chipClass(filters.type === "")}>{tr("All")}</button>
        {CHIP_TYPES.map((t) => (
          <button key={t} type="button" aria-pressed={filters.type === t} onClick={() => update({ type: filters.type === t ? "" : t })} className={chipClass(filters.type === t)}>
            {t === "Buy" ? tr("Buys") : t === "Sell" ? tr("Sells") : t === "Dividend" ? tr("Dividends") : tr("Deposits")}
          </button>
        ))}
      </div>

      {sheetOpen && <FilterSheet filters={filters} brokers={brokers} onApply={onChange} onClose={() => setSheetOpen(false)} />}
    </div>
  );
}

function FilterSheet({
  filters,
  brokers,
  onApply,
  onClose,
}: {
  filters: TransactionFilterState;
  brokers: string[];
  onApply: (filters: TransactionFilterState) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState(filters);
  const set = (patch: Partial<TransactionFilterState>) => setDraft((d) => ({ ...d, ...patch }));
  return (
    <Sheet
      title={tr("Filter transactions")}
      onClose={onClose}
      footer={
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => {
              onApply({ ...EMPTY_FILTERS, assetName: filters.assetName });
              onClose();
            }}
            className={`${secondaryButtonClass} h-12 flex-1`}
          >{tr("Clear")}</button>
          <button
            type="button"
            onClick={() => {
              onApply(draft);
              onClose();
            }}
            className={`${primaryButtonClass} flex-1`}
          >{tr("Show results")}</button>
        </div>
      }
    >
      <div className="flex flex-col gap-4 pt-2">
        <label className="flex flex-col gap-1.5 text-sm font-semibold text-ui-ink-soft">{tr("Type")}<select value={draft.type} onChange={(e) => set({ type: e.target.value as TransactionType | "" })} className={inputClass}>
            <option value="">{tr("All types")}</option>
            {TRANSACTION_TYPES.map((t) => (
              <option key={t} value={t}>
                {tr(t)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-semibold text-ui-ink-soft">{tr("Broker")}<select value={draft.broker} onChange={(e) => set({ broker: e.target.value })} className={inputClass}>
            <option value="">{tr("All brokers")}</option>
            {brokers.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex min-w-0 flex-col gap-1.5 text-sm font-semibold text-ui-ink-soft">{tr("From")}<input type="date" value={draft.dateFrom} onChange={(e) => set({ dateFrom: e.target.value })} className={inputClass} />
          </label>
          <label className="flex min-w-0 flex-col gap-1.5 text-sm font-semibold text-ui-ink-soft">{tr("To")}<input type="date" value={draft.dateTo} onChange={(e) => set({ dateTo: e.target.value })} className={inputClass} />
          </label>
        </div>
      </div>
    </Sheet>
  );
}
