import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrRecipe } from "../../api/listrTypes";
import { formatQuantity } from "../../utils/format";
import ModalOverlay from "../ModalOverlay";
import { QueryError } from "../ui/QueryError";
import { t } from "../../i18n";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const NEW_LIST = "__new__";

/** Per-ingredient checkboxes (all checked by default, so "add everything" is one click) plus
 * a target list -- an existing one, or a brand-new one named on the spot. */
export default function AddToListDialog({
  recipe,
  isSubmitting,
  onCancel,
  onSubmit,
}: {
  recipe: ListrRecipe;
  isSubmitting: boolean;
  onCancel: () => void;
  onSubmit: (input: { listId: number | null; newListName: string | null; ingredientIds: number[] }) => void;
}) {
  const { data: lists, isError: listsError, refetch: refetchLists } = useQuery({
    queryKey: ["listr-lists", false],
    queryFn: () => listrApi.listLists(),
  });
  const [selected, setSelected] = useState<Set<number>>(new Set(recipe.ingredients.map((i) => i.id)));
  const [listChoice, setListChoice] = useState<string>(NEW_LIST);
  const [newListName, setNewListName] = useState(recipe.title);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size === 0) return;
    onSubmit({
      listId: listChoice === NEW_LIST ? null : Number(listChoice),
      newListName: listChoice === NEW_LIST ? newListName.trim() : null,
      ingredientIds: [...selected],
    });
  }

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-md rounded-lg bg-white p-5 shadow-lg">
      <h2 className="text-base font-semibold text-slate-900">{t("Toevoegen aan boodschappenlijst")}</h2>
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        <div className="flex flex-col gap-1 rounded-md border border-slate-200 p-2">
          {recipe.ingredients.map((ing) => (
            <label key={ing.id} className="flex items-center gap-2 rounded-md px-1.5 py-1 text-sm hover:bg-slate-50">
              <input type="checkbox" checked={selected.has(ing.id)} onChange={() => toggle(ing.id)} />
              <span className="flex-1 text-slate-900">{ing.grocery_item_name}</span>
              <span className="tabular-nums text-slate-400">
                {formatQuantity(ing.quantity)} {ing.unit}
              </span>
            </label>
          ))}
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
