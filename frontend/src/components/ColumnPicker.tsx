import { useEffect, useRef, useState } from "react";
import { t } from "../i18n";

export interface ColumnOption<K extends string> {
  key: K;
  label: string;
  /** Columns that carry the row's identity can't be switched off. */
  fixed?: boolean;
}

/** Dropdown for choosing which of a table's columns are shown. */
export default function ColumnPicker<K extends string>({
  columns,
  isHidden,
  onToggle,
  onShowAll,
  hiddenCount,
}: {
  columns: readonly ColumnOption<K>[];
  isHidden: (key: K) => boolean;
  onToggle: (key: K) => void;
  onShowAll: () => void;
  hiddenCount: number;
}) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (!container.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={container} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        className="rounded-md border border-slate-200 px-2 py-1 text-xs font-normal text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-700"
      >{t("Columns")}{hiddenCount > 0 && ` · ${t("{n} hidden", { n: hiddenCount })}`}

      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-1 w-52 rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
          {columns.map((column) => {
            const checked = !isHidden(column.key);
            return (
              <label
                key={column.key}
                className={`flex items-center gap-2 rounded px-2 py-1.5 text-sm font-normal ${
                  column.fixed ? "text-slate-400" : "cursor-pointer text-slate-700 hover:bg-slate-50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={column.fixed}
                  onChange={() => onToggle(column.key)}
                  className="h-3.5 w-3.5 rounded border-slate-300 accent-slate-900"
                />
                <span className="flex-1">{t(column.label)}</span>
                {column.fixed && <span className="text-[10px] uppercase tracking-wide">{t("always")}</span>}
              </label>
            );
          })}

          <button
            type="button"
            onClick={onShowAll}
            disabled={hiddenCount === 0}
            className="mt-1 w-full border-t border-slate-100 px-2 pb-1 pt-2 text-left text-xs text-slate-500 transition-colors hover:text-slate-700 disabled:text-slate-300"
          >{t("Show all columns")}</button>
        </div>
      )}
    </div>
  );
}
