import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrLeftoverInput, ListrMealPlanEntry, ListrMealPlanInput, ListrRecipe } from "../../api/listrTypes";
import ModalOverlay from "../ModalOverlay";
import LeftoverFields, { EMPTY_LEFTOVER_DRAFT, draftToInput, type LeftoverDraft } from "./LeftoverFields";
import RecipePickerCombobox from "./RecipePickerCombobox";
import { QueryError } from "../ui/QueryError";
import { dateLocale, t } from "../../i18n";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

function formatDayHeader(dateIso: string): string {
  return new Date(dateIso + "T00:00:00").toLocaleDateString(dateLocale("nl-NL"), {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

/** The day-editor opened by clicking a cell in either weekplanner view -- pick or clear the
 * recipe (or a leftover to eat instead), add a note, and mark it as actually cooked (the explicit
 * step the popularity ranking relies on, see docs/adr/0006, and the one that takes a meal off a
 * leftover, see docs/adr/0036). Marking a recipe cooked also offers to keep the leftovers. */
export default function MealDayDialog({
  date,
  entry,
  isSubmitting,
  error,
  onCancel,
  onSave,
  onClear,
}: {
  date: string;
  entry: ListrMealPlanEntry | undefined;
  isSubmitting: boolean;
  /** Why the last save failed, shown above the buttons; null while there is nothing to report. */
  error: string | null;
  onCancel: () => void;
  /** `moveTo` is the date to plan this day for instead, or null when the date is unchanged. */
  onSave: (input: ListrMealPlanInput, newLeftover: ListrLeftoverInput | null, moveTo: string | null) => void;
  onClear: () => void;
}) {
  const [newDate, setNewDate] = useState(date);
  const [recipeId, setRecipeId] = useState<number | null>(entry?.recipe_id ?? null);
  const [recipeTitle, setRecipeTitle] = useState<string | null>(entry?.recipe_title ?? null);
  const [notes, setNotes] = useState(entry?.notes ?? "");
  const [isCooked, setIsCooked] = useState(entry?.is_cooked ?? false);
  const [leftoverId, setLeftoverId] = useState<number | null>(entry?.leftover_id ?? null);
  const [keepLeftovers, setKeepLeftovers] = useState(false);
  const [draft, setDraft] = useState<LeftoverDraft>(EMPTY_LEFTOVER_DRAFT);

  const { data: leftovers, isError: leftoversError, refetch: refetchLeftovers } = useQuery({
    queryKey: ["listr-leftovers"],
    queryFn: () => listrApi.listLeftovers(),
  });
  // Offered once, when the day flips to cooked -- re-saving an already-cooked day must not
  // stash the same batch a second time.
  const canKeepLeftovers = isCooked && recipeId !== null && !entry?.is_cooked;

  function selectRecipe(recipe: ListrRecipe) {
    setRecipeId(recipe.id);
    setRecipeTitle(recipe.title);
    setLeftoverId(null);
  }

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-sm rounded-lg bg-white p-5 shadow-lg">
      <h2 className="text-base font-semibold capitalize text-slate-900">{formatDayHeader(date)}</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSave(
            { recipe_id: recipeId, leftover_id: leftoverId, is_cooked: isCooked, notes: notes.trim() || null },
            canKeepLeftovers && keepLeftovers && recipeTitle ? draftToInput(recipeTitle, recipeId, draft) : null,
            entry && newDate !== date ? newDate : null,
          );
        }}
        className="mt-4 flex flex-col gap-3"
      >
        {/* Only a planned day can move; an empty one is planned by opening the date you want. */}
        {entry && (
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Datum")}</span>
            <input
              type="date"
              value={newDate}
              onChange={(e) => e.target.value && setNewDate(e.target.value)}
              required
              className={inputClass}
            />
          </label>
        )}

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Recept")}</span>
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
              >{t("Wissen")}</button>
            </div>
          ) : (
            <RecipePickerCombobox onSelect={selectRecipe} />
          )}
        </label>

        {recipeId === null && leftoversError && (
          <QueryError
            className="text-sm"
            message={t("Restjes laden mislukt, dus je kunt nu geen restje kiezen.")}
            onRetry={() => refetchLeftovers()}
            retryLabel={t("Opnieuw")}
          />
        )}
        {recipeId === null && (leftovers?.length || leftoverId !== null) ? (
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Of een restje")}</span>
            <select
              value={leftoverId ?? ""}
              onChange={(e) => setLeftoverId(e.target.value ? Number(e.target.value) : null)}
              className={inputClass}
            >
              <option value="">{t("Geen")}</option>
              {/* The day's own leftover stays selectable even once its last meal is eaten. */}
              {entry?.leftover_id != null && !leftovers?.some((l) => l.id === entry.leftover_id) && (
                <option value={entry.leftover_id}>{entry.leftover_name}</option>
              )}
              {(leftovers ?? []).map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name} ({l.meals}×)
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Notitie (optioneel)")}</span>
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={t("bv. uit eten, restjes, halve portie…")}
            className={inputClass}
          />
        </label>

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={isCooked} onChange={(e) => setIsCooked(e.target.checked)} />
          {leftoverId !== null ? t("Ik heb dit gegeten") : t("Ik heb dit gekookt")}
        </label>

        {canKeepLeftovers && (
          <div className="flex flex-col gap-3 rounded-md bg-slate-50 p-3">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={keepLeftovers} onChange={(e) => setKeepLeftovers(e.target.checked)} />{t("Restjes bewaren")}</label>
            {keepLeftovers && <LeftoverFields value={draft} onChange={setDraft} />}
          </div>
        )}

        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

        <div className="mt-2 flex items-center justify-between gap-2">
          {entry ? (
            <button
              type="button"
              onClick={onClear}
              disabled={isSubmitting}
              className="text-xs font-medium text-slate-400 hover:text-red-600 disabled:opacity-50"
            >{t("Dag wissen")}</button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >{t("Annuleren")}</button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {isSubmitting ? t("Bezig…") : t("Opslaan")}
            </button>
          </div>
        </div>
      </form>
    </ModalOverlay>
  );
}
