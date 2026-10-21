import { Pencil } from "lucide-react";
import { useState } from "react";

import type { GriprCategoryKind, GriprSuggestionFigures } from "../../api/griprTypes";
import { decimalInputToApi, formatEur, toNumber } from "../../utils/format";
import { t } from "../../i18n";

/** Reads as static text until the pencil (or the row itself) is clicked, then becomes an
 * editable input that closes itself again on save — so a tile with a budget set doesn't sit
 * permanently open as an input box. Used on Budget for every editable budgeted/target/goal
 * figure (expense budgets, income targets, savings goals). */
export default function BudgetCell({
  value,
  kind,
  suggestion,
  onSave,
  compact = false,
}: {
  value: string;
  kind: GriprCategoryKind;
  suggestion: GriprSuggestionFigures | undefined;
  onSave: (value: string) => void;
  /** Inline in a list row: just the amount and pencil, no "Budget" label, not full width. */
  compact?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const isIncome = kind === "income";
  const label = isIncome ? t("Target") : t("Budget");
  const editTitle = isIncome ? t("Edit target") : t("Edit budget");

  if (!editing && compact) {
    const unset = (toNumber(value) ?? 0) === 0;
    return (
      <button
        type="button"
        onClick={() => {
          setDraft(String(toNumber(value) ?? 0).replace(".", ","));
          setEditing(true);
        }}
        className="group inline-flex items-center gap-1 rounded-md px-1 text-xs tabular-nums hover:bg-surface-container sm:text-sm"
        title={editTitle}
      >
        <span className="text-on-surface-variant">
          {unset ? (isIncome ? t("set target") : t("set budget")) : formatEur(value)}
        </span>
        <Pencil className="h-3 w-3 text-outline group-hover:text-on-surface-variant" strokeWidth={2} />
      </button>
    );
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => {
          setDraft(String(toNumber(value) ?? 0).replace(".", ","));
          setEditing(true);
        }}
        className="group flex w-full items-center justify-between rounded-md px-1.5 py-1 text-sm hover:bg-surface-container"
        title={editTitle}
      >
        <span className="text-on-surface-variant">{label}</span>
        <span className="flex items-center gap-1.5 font-medium tabular-nums text-on-surface">
          {formatEur(value)}
          <Pencil className="h-3.5 w-3.5 text-outline group-hover:text-on-surface-variant" strokeWidth={2} />
        </span>
      </button>
    );
  }

  // Only worth suggesting when there's nothing set yet — once a budget exists, "last month"
  // etc. isn't filling in a blank anymore, it'd be overwriting a deliberate choice.
  const isEmpty = (toNumber(value) ?? 0) === 0;
  const chips = isEmpty
    ? [
        { label: t("Last month"), amount: toNumber(suggestion?.previous_month) ?? 0 },
        { label: t("Year avg"), amount: toNumber(suggestion?.year_average) ?? 0 },
        { label: t("Recurring"), amount: toNumber(suggestion?.recurring_monthly) ?? 0 },
      ].filter((chip) => chip.amount > 0)
    : [];

  return (
    <div className={`flex flex-col gap-1.5 px-1.5 text-sm ${compact ? "w-44 items-end" : ""}`}>
      <div className="flex items-center gap-1.5">
        <span className="text-on-surface-variant">€</span>
        <input
          autoFocus
          inputMode="decimal"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => {
            setEditing(false);
            const parsed = decimalInputToApi(draft);
            if (parsed !== null) onSave(parsed);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
            if (e.key === "Escape") setEditing(false);
          }}
          className="w-full rounded-md border border-outline px-2 py-1 text-right tabular-nums focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {chips.map((chip) => (
            <button
              key={chip.label}
              type="button"
              // Keeps focus on the input so its onBlur (which would save an empty draft) never
              // fires before this click is handled.
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                setEditing(false);
                onSave(String(chip.amount));
              }}
              className="rounded-lg border border-outline-variant px-2 py-0.5 text-xs text-on-surface-variant hover:border-primary hover:text-on-surface"
            >
              {chip.label} {formatEur(chip.amount)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
