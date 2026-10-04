import { useState } from "react";

import type { ListrMealPlanEntry, ListrMealPlanInput, ListrRecipe } from "../../api/listrTypes";
import ModalOverlay from "../ModalOverlay";
import RecipePickerCombobox from "./RecipePickerCombobox";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

function formatDayHeader(dateIso: string): string {
  return new Date(dateIso + "T00:00:00").toLocaleDateString("nl-NL", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

/** The day-editor opened by clicking a cell in either weekplanner view -- pick or clear the
 * recipe, add a note, and mark it as actually cooked (the explicit step the popularity ranking
 * relies on; see docs/adr/0006). */
export default function MealDayDialog({
  date,
  entry,
  isSubmitting,
  onCancel,
  onSave,
  onClear,
}: {
  date: string;
  entry: ListrMealPlanEntry | undefined;
  isSubmitting: boolean;
  onCancel: () => void;
  onSave: (input: ListrMealPlanInput) => void;
  onClear: () => void;
}) {
  const [recipeId, setRecipeId] = useState<number | null>(entry?.recipe_id ?? null);
  const [recipeTitle, setRecipeTitle] = useState<string | null>(entry?.recipe_title ?? null);
  const [notes, setNotes] = useState(entry?.notes ?? "");
  const [isCooked, setIsCooked] = useState(entry?.is_cooked ?? false);

  function selectRecipe(recipe: ListrRecipe) {
    setRecipeId(recipe.id);
    setRecipeTitle(recipe.title);
  }

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-sm rounded-lg bg-white p-5 shadow-lg">
      <h2 className="text-base font-semibold capitalize text-slate-900">{formatDayHeader(date)}</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSave({ recipe_id: recipeId, is_cooked: isCooked, notes: notes.trim() || null });
        }}
        className="mt-4 flex flex-col gap-3"
      >
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Recept</span>
          {recipeId && recipeTitle ? (
            <div className="flex items-center justify-between gap-2 rounded-md border border-slate-300 px-2.5 py-1.5 text-sm">
              <span className="truncate text-slate-900">{recipeTitle}</span>
              <button
                type="button"
                onClick={() => {
                  setRecipeId(null);
                  setRecipeTitle(null);
                }}
                className="shrink-0 text-xs text-slate-400 hover:text-red-600"
              >
                Wissen
              </button>
            </div>
          ) : (
            <RecipePickerCombobox onSelect={selectRecipe} />
          )}
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Notitie (optioneel)</span>
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="bv. uit eten, restjes, halve portie…"
            className={inputClass}
          />
        </label>

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={isCooked} onChange={(e) => setIsCooked(e.target.checked)} />
          Ik heb dit gekookt
        </label>

        <div className="mt-2 flex items-center justify-between gap-2">
          {entry ? (
            <button
              type="button"
              onClick={onClear}
              disabled={isSubmitting}
              className="text-xs font-medium text-slate-400 hover:text-red-600 disabled:opacity-50"
            >
              Dag wissen
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Annuleren
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {isSubmitting ? "Bezig…" : "Opslaan"}
            </button>
          </div>
        </div>
      </form>
    </ModalOverlay>
  );
}
