import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { listrApi } from "../../api/listrClient";
import type { ListrMealieImportResult, ListrMealieRecipeStatus, ListrMealieUnmatchedFood } from "../../api/listrTypes";
import ModalOverlay from "../ModalOverlay";
import AddItemCombobox from "./AddItemCombobox";

type Pick = { id: number; name: string };

const STATUS_LABELS: Record<ListrMealieRecipeStatus["status"], string> = {
  new: "nieuw",
  changed: "gewijzigd",
  unchanged: "ongewijzigd",
};

/** The server's own message out of a failed request ("409 Conflict: {"detail": "..."}"), so the
 * dialog can say what Mealie actually complained about instead of a generic failure. */
function serverMessage(error: unknown): string {
  const text = error instanceof Error ? error.message : "";
  try {
    const detail = JSON.parse(text.slice(text.indexOf(": ") + 2)).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail.message === "string") return detail.message;
  } catch {
    // not a JSON body -- fall through to the generic message
  }
  return "Er ging iets mis bij het ophalen uit Mealie.";
}

function FoodRow({
  food,
  pick,
  onPick,
}: {
  food: ListrMealieUnmatchedFood;
  pick: Pick | null;
  onPick: (pick: Pick | null) => void;
}) {
  return (
    <li className="flex flex-col gap-1.5 py-2.5 sm:flex-row sm:items-center sm:gap-3">
      <div className="min-w-0 sm:w-44 sm:shrink-0">
        <div className="text-sm font-medium text-slate-900">{food.name}</div>
        <div className="truncate text-xs text-slate-400">{food.recipe_names.join(", ")}</div>
      </div>
      <div className="min-w-0 flex-1">
        {pick ? (
          <div className="flex items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-sm">
            <span className="truncate text-slate-900">✓ {pick.name}</span>
            <button type="button" onClick={() => onPick(null)} className="shrink-0 py-0.5 text-xs font-medium text-slate-500 hover:text-slate-900">
              Wijzigen
            </button>
          </div>
        ) : (
          <AddItemCombobox initialQuery={food.name} onSelect={(item) => onPick({ id: item.id, name: item.name })} />
        )}
      </div>
    </li>
  );
}

/** "Ophalen uit Mealie": shows what's new/changed in Mealie, asks for a catalog product for any
 * ingredient that doesn't match one yet (pre-selecting a best guess), then imports. The picks are
 * remembered server-side, so the next import only asks about foods it hasn't seen before. See
 * docs/adr/0022-listr-mealie-import.md. */
export default function MealieImportDialog({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [picks, setPicks] = useState<Record<string, Pick | null>>({});
  const [result, setResult] = useState<ListrMealieImportResult | null>(null);

  const previewQuery = useQuery({
    queryKey: ["listr-mealie-preview"],
    queryFn: () => listrApi.mealiePreview(),
    // Always fresh: the point is to see what changed in Mealie since the last look.
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });

  // Seed picks from the server's suggestions for any food not picked yet, keeping choices the
  // reader already made (a refetch after a failed import mustn't undo them).
  useEffect(() => {
    if (!previewQuery.data) return;
    setPicks((current) => {
      const next = { ...current };
      for (const food of previewQuery.data.unmatched_foods) {
        if (!(food.food_id in next)) {
          next[food.food_id] =
            food.suggested_item_id !== null && food.suggested_item_name !== null
              ? { id: food.suggested_item_id, name: food.suggested_item_name }
              : null;
        }
      }
      return next;
    });
  }, [previewQuery.data]);

  const importMutation = useMutation({
    mutationFn: () =>
      listrApi.mealieImport(
        (previewQuery.data?.unmatched_foods ?? [])
          .filter((f) => picks[f.food_id])
          .map((f) => ({ food_id: f.food_id, grocery_item_id: picks[f.food_id]!.id })),
      ),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["listr-recipes"] });
      queryClient.invalidateQueries({ queryKey: ["listr-recipe"] });
      queryClient.invalidateQueries({ queryKey: ["listr-recipe-categories"] });
    },
    // A recipe added in Mealie since the preview can bring new foods: show the fresh list.
    onError: () => previewQuery.refetch(),
  });

  const preview = previewQuery.data;
  const pending = preview?.recipes.filter((r) => r.status !== "unchanged") ?? [];
  const unchangedCount = (preview?.recipes.length ?? 0) - pending.length;
  const unmatched = preview?.unmatched_foods ?? [];
  const openCount = unmatched.filter((f) => !picks[f.food_id]).length;
  const canImport = pending.length > 0 && openCount === 0 && !importMutation.isPending;

  return (
    <ModalOverlay onClose={onClose} cardClassName="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-lg bg-white p-5 shadow-lg">
      <h2 className="text-base font-semibold text-slate-900">Ophalen uit Mealie</h2>

      <div className="mt-4 min-h-0 flex-1 overflow-y-auto">
        {result ? (
          <div className="flex flex-col gap-1 px-1 py-6 text-center text-sm text-slate-700">
            <p className="font-medium text-slate-900">Klaar.</p>
            <p>
              {result.created} {result.created === 1 ? "recept" : "recepten"} toegevoegd, {result.updated} bijgewerkt
              {result.unchanged > 0 && `, ${result.unchanged} al up-to-date`}.
            </p>
          </div>
        ) : previewQuery.isLoading ? (
          <div className="px-4 py-8 text-center text-sm text-slate-400">Recepten ophalen uit Mealie…</div>
        ) : previewQuery.isError || !preview ? (
          <div className="flex flex-col items-center gap-3 px-4 py-8 text-center text-sm">
            <p className="text-red-600">{serverMessage(previewQuery.error)}</p>
            <button onClick={() => previewQuery.refetch()} className="font-medium text-slate-900 underline">
              Opnieuw proberen
            </button>
          </div>
        ) : preview.recipes.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-slate-400">Er staan nog geen recepten in Mealie.</div>
        ) : pending.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-slate-500">
            Alles is al bijgewerkt — {unchangedCount} {unchangedCount === 1 ? "recept" : "recepten"} ongewijzigd sinds de vorige import.
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <section className="flex flex-col gap-1.5">
              <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Recepten{unchangedCount > 0 && ` · ${unchangedCount} ongewijzigd`}
              </h3>
              <ul className="flex flex-col gap-1">
                {pending.map((r) => (
                  <li key={r.mealie_id} className="flex items-center justify-between gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm">
                    <span className="truncate text-slate-900">{r.name}</span>
                    <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{STATUS_LABELS[r.status]}</span>
                  </li>
                ))}
              </ul>
              {pending.some((r) => r.status === "changed") && (
                <p className="text-xs text-slate-500">Gewijzigde recepten worden overschreven met de versie uit Mealie.</p>
              )}
            </section>

            {unmatched.length > 0 && (
              <section className="flex flex-col gap-1.5">
                <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Ingrediënten koppelen</h3>
                <p className="text-xs text-slate-500">
                  Welk product uit je Producten is dit? Een voorstel staat al klaar waar er een past. Je kiest dit eenmalig — de keuze wordt
                  onthouden voor volgende recepten.
                </p>
                <ul className="divide-y divide-slate-100">
                  {unmatched.map((food) => (
                    <FoodRow
                      key={food.food_id}
                      food={food}
                      pick={picks[food.food_id] ?? null}
                      onPick={(pick) => setPicks((current) => ({ ...current, [food.food_id]: pick }))}
                    />
                  ))}
                </ul>
              </section>
            )}

            {importMutation.isError && <p className="text-sm text-red-600">{serverMessage(importMutation.error)}</p>}
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-slate-100 pt-3">
        {!result && openCount > 0 && (
          // Its own line on a phone, beside the buttons from sm up, so the buttons never wrap.
          <span className="w-full text-xs text-amber-600 sm:mr-auto sm:w-auto">
            Nog {openCount} {openCount === 1 ? "ingrediënt" : "ingrediënten"} te koppelen
          </span>
        )}
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          {result ? "Sluiten" : "Annuleren"}
        </button>
        {!result && pending.length > 0 && (
          <button
            type="button"
            disabled={!canImport}
            onClick={() => importMutation.mutate()}
            className="whitespace-nowrap rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {importMutation.isPending ? "Bezig…" : `Importeren (${pending.length})`}
          </button>
        )}
      </div>
    </ModalOverlay>
  );
}
