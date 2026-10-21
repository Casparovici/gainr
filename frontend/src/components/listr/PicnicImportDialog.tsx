import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";

import { listrApi } from "../../api/listrClient";
import type { ListrPicnicRecipeSummary } from "../../api/listrTypes";
import { usePicnicConnect } from "../../hooks/usePicnicConnect";
import { formatQuantity } from "../../utils/format";
import ModalOverlay from "../ModalOverlay";
import { msg, t, tp } from "../../i18n";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

const SEGMENT_LABELS: Record<string, string> = {
  SAVED_RECIPES: msg("Opgeslagen"),
  USER_DEFINED_RECIPES: msg("Eigen recepten"),
  THIS_WEEK_RECIPES: msg("Deze week"),
};

function segmentLabel(segment: string | null): string {
  return t((segment && SEGMENT_LABELS[segment]) || msg("Overig"));
}

function groupBySegment(recipes: ListrPicnicRecipeSummary[]) {
  const groups = new Map<string, ListrPicnicRecipeSummary[]>();
  for (const recipe of recipes) {
    const label = segmentLabel(recipe.segment);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label)!.push(recipe);
  }
  return [...groups.entries()];
}

/** Browse the Picnic cookbook, preview a recipe, and import it as a real listr recipe --
 * ingredients (name/quantity/unit) and step-by-step instructions come straight from Picnic; see
 * docs/adr/0011-listr-picnic-integration.md for how that's parsed and its known limits. */
export default function PicnicImportDialog({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: (recipeId: number) => void;
}) {
  const queryClient = useQueryClient();
  const [selectedRecipe, setSelectedRecipe] = useState<ListrPicnicRecipeSummary | null>(null);
  const [title, setTitle] = useState("");
  const [recipeCategoryIds, setRecipeCategoryIds] = useState<number[]>([]);
  const [ingredientCategoryIds, setIngredientCategoryIds] = useState<(number | null)[]>([]);

  const picnic = usePicnicConnect(() => {});

  const cookbookQuery = useQuery({
    queryKey: ["listr-picnic-cookbook"],
    queryFn: () => listrApi.picnicCookbook(),
    enabled: picnic.status?.connected === true,
  });
  const previewQuery = useQuery({
    queryKey: ["listr-picnic-preview", selectedRecipe?.id],
    queryFn: () => listrApi.picnicRecipePreview(selectedRecipe!.id),
    enabled: selectedRecipe !== null,
  });
  const { data: categories } = useQuery({
    queryKey: ["listr-categories"],
    queryFn: () => listrApi.listCategories(),
  });
  const { data: recipeCategories } = useQuery({
    queryKey: ["listr-recipe-categories"],
    queryFn: () => listrApi.listRecipeCategories(),
  });

  // Reset the per-ingredient category picks whenever a fresh preview comes in -- indices must
  // line up with preview.ingredients, so a stale array from a previous recipe can't survive.
  useEffect(() => {
    if (previewQuery.data) {
      setIngredientCategoryIds(previewQuery.data.ingredients.map(() => null));
    }
  }, [previewQuery.data]);

  useEffect(() => {
    if (selectedRecipe) setTitle(selectedRecipe.name);
  }, [selectedRecipe]);

  const importMutation = useMutation({
    mutationFn: () =>
      listrApi.picnicImportRecipe(selectedRecipe!.id, {
        name: title,
        recipe_category_ids: recipeCategoryIds,
        ingredient_category_ids: ingredientCategoryIds,
      }),
    onSuccess: (recipe) => {
      queryClient.invalidateQueries({ queryKey: ["listr-recipes"] });
      onImported(recipe.id);
    },
  });

  function toggleRecipeCategory(id: number) {
    setRecipeCategoryIds((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]));
  }

  function back() {
    setSelectedRecipe(null);
  }

  const missingCategoryCount =
    previewQuery.data?.ingredients.filter((ing, i) => ing.matched_item_id === null && ingredientCategoryIds[i] === null)
      .length ?? 0;

  return (
    <ModalOverlay onClose={onClose} cardClassName="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-lg bg-white p-5 shadow-lg">
      <div className="flex items-center gap-2">
        {selectedRecipe && (
          <button type="button" onClick={back} className="text-slate-500 hover:text-slate-900" aria-label={t("Terug")}>
            <ChevronLeft className="h-4 w-4" strokeWidth={2} />
          </button>
        )}
        <h2 className="text-base font-semibold text-slate-900">
          {selectedRecipe ? selectedRecipe.name : t("Importeren van Picnic")}
        </h2>
      </div>

      <div className="mt-4 flex-1 overflow-y-auto">
        {!picnic.status?.configured ? (
          <div className="rounded-lg border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-400">{t("Picnic is niet geconfigureerd op de server.")}</div>
        ) : !picnic.status?.connected ? (
          <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
            <p className="text-sm text-slate-500">{t("Verbind eerst met je Picnic-account om recepten te bekijken.")}</p>
            <button
              onClick={picnic.connect}
              disabled={picnic.isConnecting}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {picnic.isConnecting ? t("Bezig…") : t("Verbind met Picnic")}
            </button>
            {picnic.awaiting2FA && (
              <div className="mt-1 w-64 rounded-lg border border-slate-200 bg-white p-3 text-left shadow-sm">
                <div className="text-sm font-medium text-slate-900">{t("Code van Picnic invoeren")}</div>
                <p className="mt-0.5 text-xs text-slate-400">{t("Picnic heeft je zojuist een sms gestuurd.")}</p>
                <input
                  autoFocus
                  inputMode="numeric"
                  value={picnic.code}
                  onChange={(e) => picnic.setCode(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && picnic.code.trim()) picnic.verify();
                  }}
                  placeholder="123456"
                  className={`${inputClass} mt-2 w-full`}
                />
                {picnic.verifyError && <p className="mt-1 text-xs text-red-600">{t("Code niet geaccepteerd, probeer opnieuw.")}</p>}
                <div className="mt-2 flex justify-end gap-2">
                  <button
                    onClick={picnic.cancel}
                    className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >{t("Annuleren")}</button>
                  <button
                    disabled={!picnic.code.trim() || picnic.isVerifying}
                    onClick={picnic.verify}
                    className="rounded-md bg-slate-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                  >{t("Bevestigen")}</button>
                </div>
              </div>
            )}
            {picnic.connectError && !picnic.awaiting2FA && (
              <p className="text-sm text-red-600">{t("Verbinden met Picnic is mislukt. Probeer het later opnieuw.")}</p>
            )}
          </div>
        ) : !selectedRecipe ? (
          cookbookQuery.isLoading ? (
            <div className="px-4 py-8 text-center text-sm text-slate-400">{t("Recepten laden…")}</div>
          ) : cookbookQuery.isError ? (
            <div className="px-4 py-8 text-center text-sm text-red-600">{t("Kon recepten niet laden.")}</div>
          ) : !cookbookQuery.data || cookbookQuery.data.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-slate-400">{t("Geen recepten gevonden in je Picnic-app.")}</div>
          ) : (
            <div className="flex flex-col gap-4">
              {groupBySegment(cookbookQuery.data).map(([label, recipes]) => (
                <div key={label}>
                  <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
                  <div className="flex flex-col gap-1">
                    {recipes.map((recipe) => (
                      <button
                        key={recipe.id}
                        type="button"
                        onClick={() => setSelectedRecipe(recipe)}
                        className="rounded-md border border-slate-200 px-3 py-2 text-left text-sm text-slate-900 hover:border-slate-300 hover:bg-slate-50"
                      >
                        {recipe.name || t("(naam onbekend)")}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )
        ) : previewQuery.isLoading ? (
          <div className="px-4 py-8 text-center text-sm text-slate-400">{t("Recept laden…")}</div>
        ) : previewQuery.isError || !previewQuery.data ? (
          <div className="px-4 py-8 text-center text-sm text-red-600">{t("Kon dit recept niet laden.")}</div>
        ) : (
          <div className="flex flex-col gap-4">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Titel")}</span>
              <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
            </label>

            {recipeCategories && recipeCategories.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Categorieën")}</span>
                <div className="flex flex-wrap items-center gap-1.5">
                  {recipeCategories.map((category) => {
                    const selected = recipeCategoryIds.includes(category.id);
                    return (
                      <button
                        key={category.id}
                        type="button"
                        onClick={() => toggleRecipeCategory(category.id)}
                        className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                          selected
                            ? "border-slate-900 bg-slate-900 text-white"
                            : "border-slate-300 text-slate-600 hover:border-slate-400"
                        }`}
                      >
                        {category.color && (
                          <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: category.color }} />
                        )}
                        {category.name}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Ingrediënten")}{previewQuery.data.servings ? ` · ${t("{servings} personen", { servings: previewQuery.data.servings })}` : ""}
              </span>
              <div className="flex flex-col gap-1.5 rounded-md border border-slate-200 p-2">
                {previewQuery.data.ingredients.map((ingredient, index) => (
                  <div key={index} className="flex items-center gap-1.5">
                    <span className="w-16 shrink-0 text-right text-sm tabular-nums text-slate-500">
                      {formatQuantity(ingredient.quantity)}
                    </span>
                    <span className="w-14 shrink-0 text-xs text-slate-400">{ingredient.unit}</span>
                    <span className="flex-1 truncate text-sm text-slate-900">{ingredient.name}</span>
                    {ingredient.matched_item_id === null ? (
                      <select
                        value={ingredientCategoryIds[index] ?? ""}
                        onChange={(e) =>
                          setIngredientCategoryIds((ids) =>
                            ids.map((id, i) => (i === index ? (e.target.value ? Number(e.target.value) : null) : id)),
                          )
                        }
                        className={`${inputClass} w-40 shrink-0 ${ingredientCategoryIds[index] === null ? "border-amber-400" : ""}`}
                      >
                        <option value="">{t("Kies categorie…")}</option>
                        {(categories ?? []).map((category) => (
                          <option key={category.id} value={category.id}>
                            {category.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="w-40 shrink-0 truncate text-xs text-slate-400" title={t("Bestaat al in je Producten")}>
                        ✓ {ingredient.matched_item_name}
                      </span>
                    )}
                  </div>
                ))}
              </div>
              {missingCategoryCount > 0 && (
                <p className="text-xs text-amber-600">{tp(
                    missingCategoryCount,
                    "Kies nog een categorie voor {n} nieuw ingrediënt.",
                    "Kies nog een categorie voor {n} nieuwe ingrediënten.",
                  )}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Bereidingswijze")}</span>
              <div className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 p-2.5 text-sm text-slate-700">
                {previewQuery.data.instructions || t("Geen bereidingswijze gevonden.")}
              </div>
            </div>

            {importMutation.isError && <p className="text-sm text-red-600">{t("Importeren is mislukt. Probeer het opnieuw.")}</p>}
          </div>
        )}
      </div>

      <div className="mt-4 flex justify-end gap-2 border-t border-slate-100 pt-3">
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >{t("Annuleren")}</button>
        {selectedRecipe && previewQuery.data && (
          <button
            type="button"
            disabled={!title.trim() || missingCategoryCount > 0 || importMutation.isPending}
            onClick={() => importMutation.mutate()}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {importMutation.isPending ? t("Bezig…") : t("Importeren")}
          </button>
        )}
      </div>
    </ModalOverlay>
  );
}
