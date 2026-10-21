import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listrApi } from "../../api/listrClient";
import { formatDate } from "../../utils/format";
import ModalOverlay from "../ModalOverlay";
import { QueryError } from "../ui/QueryError";
import { t } from "../../i18n";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const NEW_LIST = "__new__";

export interface PlannedMeal {
  date: string;
  recipeTitle: string;
}

/** The weekplanner's bulk sibling of a single recipe's AddToListDialog -- per-day checkboxes
 * (all checked by default) instead of per-ingredient, since across several recipes a full
 * ingredient checklist would be too long to be useful; a day whose recipe you don't want in
 * the shopping list gets unchecked here instead. */
export default function AddWeekToListDialog({
  meals,
  defaultListName,
  isSubmitting,
  onCancel,
  onSubmit,
}: {
  meals: PlannedMeal[];
  defaultListName: string;
  isSubmitting: boolean;
  onCancel: () => void;
  onSubmit: (input: { listId: number | null; newListName: string | null; dates: string[] }) => void;
}) {
  const { data: lists, isError: listsError, refetch: refetchLists } = useQuery({
    queryKey: ["listr-lists", false],
    queryFn: () => listrApi.listLists(),
  });
  const [selected, setSelected] = useState<Set<string>>(new Set(meals.map((m) => m.date)));
  const [listChoice, setListChoice] = useState<string>(NEW_LIST);
  const [newListName, setNewListName] = useState(defaultListName);

  function toggle(date: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size === 0) return;
    onSubmit({
      listId: listChoice === NEW_LIST ? null : Number(listChoice),
      newListName: listChoice === NEW_LIST ? newListName.trim() : null,
      dates: [...selected],
    });
  }

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-md rounded-lg bg-white p-5 shadow-lg">
      <h2 className="text-base font-semibold text-slate-900">{t("Boodschappenlijst van geplande recepten")}</h2>
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <div className="flex max-h-64 flex-col gap-1 overflow-y-auto rounded-md border border-slate-200 p-2">
          {meals.map((meal) => (
            <label key={meal.date} className="flex items-center gap-2 rounded-md px-1.5 py-1 text-sm hover:bg-slate-50">
              <input type="checkbox" checked={selected.has(meal.date)} onChange={() => toggle(meal.date)} />
              <span className="flex-1 text-slate-900">{meal.recipeTitle}</span>
              <span className="shrink-0 text-xs text-slate-400">{formatDate(meal.date)}</span>
            </label>
          ))}
          {meals.length === 0 && (
            <div className="px-1.5 py-1 text-sm text-slate-400">{t("Geen geplande recepten in deze periode.")}</div>
          )}
        </div>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Lijst")}</span>
          <select value={listChoice} onChange={(e) => setListChoice(e.target.value)} className={inputClass}>
            <option value={NEW_LIST}>{t("+ Nieuwe lijst…")}</option>
            {(lists ?? []).map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        {listsError && (
          <QueryError
            className="text-sm"
            message={t("Je bestaande lijsten laden mislukt; je kunt wel een nieuwe lijst maken.")}
            onRetry={() => refetchLists()}
            retryLabel={t("Opnieuw")}
          />
        )}
        {listChoice === NEW_LIST && (
          <input
            required
            value={newListName}
            onChange={(e) => setNewListName(e.target.value)}
            placeholder={t("Naam van de nieuwe lijst")}
            className={inputClass}
          />
        )}

        <div className="mt-2 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >{t("Annuleren")}</button>
          <button
            type="submit"
            disabled={isSubmitting || selected.size === 0}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {isSubmitting ? t("Bezig…") : t("Toevoegen ({count})", { count: selected.size })}
          </button>
        </div>
      </form>
    </ModalOverlay>
  );
}
