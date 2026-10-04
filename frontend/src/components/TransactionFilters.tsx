import type { TransactionType } from "../api/types";
import { TRANSACTION_TYPES } from "../api/types";

export interface TransactionFilterState {
  type: TransactionType | "";
  assetName: string;
  broker: string;
  dateFrom: string;
  dateTo: string;
}

export const EMPTY_FILTERS: TransactionFilterState = { type: "", assetName: "", broker: "", dateFrom: "", dateTo: "" };

const selectClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

export default function TransactionFilters({
  filters,
  onChange,
  brokers,
}: {
  filters: TransactionFilterState;
  onChange: (filters: TransactionFilterState) => void;
  brokers: string[];
}) {
  const update = (patch: Partial<TransactionFilterState>) => onChange({ ...filters, ...patch });
  const isActive = Object.values(filters).some((v) => v !== "");

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-3">
      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium uppercase tracking-wide text-slate-500">Type</span>
        <select
          value={filters.type}
          onChange={(e) => update({ type: e.target.value as TransactionType | "" })}
          className={selectClass}
        >
          <option value="">All</option>
          {TRANSACTION_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium uppercase tracking-wide text-slate-500">Asset</span>
        <input
          type="text"
          value={filters.assetName}
          onChange={(e) => update({ assetName: e.target.value })}
          placeholder="Type a name…"
          className={selectClass}
        />
      </label>

      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium uppercase tracking-wide text-slate-500">Broker</span>
        <select value={filters.broker} onChange={(e) => update({ broker: e.target.value })} className={selectClass}>
          <option value="">All</option>
          {brokers.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium uppercase tracking-wide text-slate-500">From</span>
        <input type="date" value={filters.dateFrom} onChange={(e) => update({ dateFrom: e.target.value })} className={selectClass} />
      </label>

      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium uppercase tracking-wide text-slate-500">To</span>
        <input type="date" value={filters.dateTo} onChange={(e) => update({ dateTo: e.target.value })} className={selectClass} />
      </label>

      {isActive && (
        <button onClick={() => onChange(EMPTY_FILTERS)} className="rounded-md px-2.5 py-1.5 text-sm font-medium text-slate-500 hover:text-slate-900">
          Clear filters
        </button>
      )}
    </div>
  );
}
