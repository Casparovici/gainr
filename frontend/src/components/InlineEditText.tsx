import { Pencil } from "lucide-react";
import { useState } from "react";
import { t } from "../i18n";

/** Reads as static text with a pencil icon until clicked, then becomes an editable input that
 * closes itself again on save -- same interaction Budget's amount cells already use
 * (BudgetCell in Budget.tsx), applied here to a plain name instead of a decimal amount. */
export default function InlineEditText({
  value,
  onSave,
  title = t("Edit name"),
  textClassName = "truncate text-sm font-medium text-slate-900",
  inputClassName = "w-full rounded-md border border-slate-300 px-1.5 py-0.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500",
}: {
  value: string;
  onSave: (value: string) => void;
  title?: string;
  textClassName?: string;
  inputClassName?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  if (!editing) {
    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setDraft(value);
          setEditing(true);
        }}
        className="group flex min-w-0 items-center gap-1.5"
        title={title}
      >
        <span className={textClassName}>{value}</span>
        <Pencil className="h-3 w-3 shrink-0 text-slate-300 group-hover:text-slate-500" strokeWidth={2} />
      </button>
    );
  }

  return (
    <input
      autoFocus
      value={draft}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        setEditing(false);
        const trimmed = draft.trim();
        if (trimmed && trimmed !== value) onSave(trimmed);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        if (e.key === "Escape") {
          setDraft(value);
          setEditing(false);
        }
      }}
      className={inputClassName}
    />
  );
}
