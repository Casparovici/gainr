import { useEffect, useRef, useState } from "react";

import type { Asset } from "../api/types";
import { t } from "../i18n";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

function label(asset: Asset): string {
  return `${asset.ticker} — ${asset.name}`;
}

/** Type-to-filter asset picker -- narrows to matching ticker/name as you type, instead of
 * scrolling a long alphabetical <select>. Used wherever a transaction picks a single asset. */
export default function AssetCombobox({
  assets,
  value,
  onChange,
  onAddNew,
  placeholder = t("Search ticker or name…"),
}: {
  assets: Asset[];
  value: number | null;
  onChange: (assetId: number) => void;
  onAddNew: () => void;
  placeholder?: string;
}) {
  const selected = assets.find((a) => a.id === value) ?? null;
  const [query, setQuery] = useState(selected ? label(selected) : "");
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Keep the input text in sync when the selection changes from outside (e.g. switching to
  // editing a different transaction).
  useEffect(() => {
    setQuery(selected ? label(selected) : "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id]);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery(selected ? label(selected) : "");
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open, selected]);

  const trimmed = query.trim().toLowerCase();
  const filtered = trimmed
    ? assets.filter((a) => a.ticker.toLowerCase().includes(trimmed) || a.name.toLowerCase().includes(trimmed))
    : assets;
  const optionCount = filtered.length + 1; // + "Add new asset"

  function select(asset: Asset) {
    onChange(asset.id);
    setQuery(label(asset));
    setOpen(false);
  }

  function selectAddNew() {
    onAddNew();
    setOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setHighlighted((h) => Math.min(h + 1, optionCount - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      if (!open) return;
      e.preventDefault();
      if (highlighted < filtered.length) select(filtered[highlighted]);
      else selectAddNew();
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery(selected ? label(selected) : "");
    }
  }

  return (
    <div className="relative" ref={containerRef}>
      <input
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setHighlighted(0);
        }}
        onFocus={(e) => {
          setOpen(true);
          setHighlighted(0);
          e.target.select();
        }}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className={`${inputClass} w-full`}
      />

      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
          {filtered.length === 0 && <div className="px-2 py-1.5 text-sm text-slate-400">{t("No matching assets")}</div>}
          {filtered.map((a, i) => (
            <button
              key={a.id}
              type="button"
              onClick={() => select(a)}
              onMouseEnter={() => setHighlighted(i)}
              className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm ${
                i === highlighted ? "bg-slate-100" : "hover:bg-slate-50"
              }`}
            >
              <span className="text-slate-900">{a.name}</span>
              <span className="text-xs text-slate-400">{a.ticker}</span>
            </button>
          ))}
          <button
            type="button"
            onClick={selectAddNew}
            onMouseEnter={() => setHighlighted(filtered.length)}
            className={`mt-1 w-full rounded-md border-t border-slate-100 px-2 py-1.5 text-left text-sm text-blue-700 ${
              filtered.length === highlighted ? "bg-slate-50" : "hover:bg-slate-50"
            }`}
          >{t("+ Add new asset…")}</button>
        </div>
      )}
    </div>
  );
}
