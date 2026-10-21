import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Camera, ImagePlus, Trash2 } from "lucide-react";

import { listrApi } from "../../api/listrClient";
import type { ListrItem, ListrRecipe, ListrRecipeInput } from "../../api/listrTypes";
import { decimalInputToApi, formatQuantity } from "../../utils/format";
import ModalOverlay from "../ModalOverlay";
import AddItemCombobox from "./AddItemCombobox";
import { secondaryButtonClass } from "../ui/kit";
import { QueryError } from "../ui/QueryError";
import RecipePhoto from "./RecipePhoto";
import { t } from "../../i18n";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

interface IngredientRow {
  key: string;
  grocery_item_id: number;
  itemName: string;
  quantity: string;
  unit: string;
}

let rowKeyCounter = 0;

function toRows(recipe: ListrRecipe | undefined): IngredientRow[] {
  if (!recipe) return [];
  return recipe.ingredients.map((ing) => ({
    key: String(rowKeyCounter++),
    grocery_item_id: ing.grocery_item_id,
    itemName: ing.grocery_item_name,
    quantity: formatQuantity(ing.quantity),
    unit: ing.unit,
  }));
}

/** An ingredient always needs some amount: an empty or zero quantity saves as 1. */
function positiveOrOne(parsed: string | null): string {
  return parsed !== null && Number(parsed) > 0 ? parsed : "1";
}

export default function RecipeForm({
  initial,
  isSubmitting,
  onCancel,
  onSubmit,
}: {
  initial: ListrRecipe | undefined;
  isSubmitting: boolean;
  onCancel: () => void;
  /** `photo` is a newly chosen file; `removePhoto` asks to drop the current one (ignored when a file is chosen). */
  onSubmit: (input: ListrRecipeInput, photo: File | null, removePhoto: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(initial?.title ?? "");
  const [servings, setServings] = useState(initial?.servings != null ? String(initial.servings) : "");
  const [instructions, setInstructions] = useState(initial?.instructions ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [rows, setRows] = useState<IngredientRow[]>(() => toRows(initial));
  const [categoryIds, setCategoryIds] = useState<number[]>(() => (initial?.categories ?? []).map((c) => c.id));
  const [newCategoryName, setNewCategoryName] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [removePhoto, setRemovePhoto] = useState(false);
  // Object URL for the chosen file, revoked when it changes or the form closes.
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!photo) {
      setPhotoPreview(null);
      return;
    }
    const url = URL.createObjectURL(photo);
    setPhotoPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  const { data: categories, isError: categoriesError, refetch: refetchCategories } = useQuery({
    queryKey: ["listr-recipe-categories"],
    queryFn: () => listrApi.listRecipeCategories(),
  });

  const createCategoryMutation = useMutation({
    mutationFn: (name: string) => listrApi.createRecipeCategory(name),
    onSuccess: (category) => {
      queryClient.invalidateQueries({ queryKey: ["listr-recipe-categories"] });
      setCategoryIds((ids) => [...ids, category.id]);
      setNewCategoryName("");
    },
  });

  function toggleCategory(id: number) {
    setCategoryIds((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]));
  }

  function addRow(item: ListrItem) {
    setRows((r) => [
      ...r,
      { key: String(rowKeyCounter++), grocery_item_id: item.id, itemName: item.name, quantity: "1", unit: item.default_unit },
    ]);
  }

  function updateRow(key: string, patch: Partial<IngredientRow>) {
    setRows((r) => r.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  }

  function removeRow(key: string) {
    setRows((r) => r.filter((row) => row.key !== key));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      title,
      servings: servings ? Number(servings) : null,
      instructions,
      notes: notes || null,
      ingredients: rows.map((row) => ({
        grocery_item_id: row.grocery_item_id,
        quantity: positiveOrOne(decimalInputToApi(row.quantity)),
        unit: row.unit,
      })),
      category_ids: categoryIds,
    }, photo, removePhoto);
  }

  function choosePhoto(file: File | undefined) {
    if (!file) return;
    setPhoto(file);
    setRemovePhoto(false);
  }
  const hasCurrentPhoto = !!initial?.has_photo && !removePhoto;
  const showsPhoto = photoPreview !== null || hasCurrentPhoto;

  return (
    <ModalOverlay onClose={onCancel} cardClassName="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-lg bg-white p-5 shadow-lg">
      <h2 className="text-base font-semibold text-slate-900">{initial ? t("Recept bewerken") : t("Nieuw recept")}</h2>
      <form onSubmit={handleSubmit} className="mt-4 flex flex-1 flex-col gap-4 overflow-y-auto">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="col-span-2 flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Titel")}</span>
            <input required autoFocus value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Aantal personen")}</span>
            <input
              type="number"
              min={1}
              value={servings}
              onChange={(e) => setServings(e.target.value)}
              className={inputClass}
            />
          </label>
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Categorieën")}</span>
          <div className="flex flex-wrap items-center gap-1.5">
            {(categories ?? []).map((category) => {
              const selected = categoryIds.includes(category.id);
              return (
                <button
                  key={category.id}
                  type="button"
                  onClick={() => toggleCategory(category.id)}
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
            <input
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && newCategoryName.trim()) {
                  e.preventDefault();
                  createCategoryMutation.mutate(newCategoryName.trim());
                }
              }}
              placeholder={t("+ nieuwe categorie…")}
              className={`${inputClass} w-36`}
            />
            {categoriesError && (
              <QueryError className="text-sm" message={t("Categorieën laden mislukt.")} onRetry={() => refetchCategories()} retryLabel={t("Opnieuw")} />
            )}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Foto")}</span>
          <div className="flex flex-wrap items-center gap-3">
            {photoPreview ? (
              <img src={photoPreview} alt={t("Gekozen foto")} className="h-20 w-20 rounded-xl object-cover" />
            ) : (
              initial && <RecipePhoto recipe={removePhoto ? { ...initial, has_photo: false } : initial} className="h-20 w-20 rounded-xl" />
            )}
            <div className="flex flex-wrap items-center gap-2">
              {/* Two inputs rather than one: `capture` sends a phone straight to the camera, which
                  would otherwise hide the gallery for a photo that already exists. */}
              <label className={`cursor-pointer ${secondaryButtonClass}`}>
                <Camera className="h-4 w-4" strokeWidth={2} />{" "}{t("Foto maken")}<input type="file" accept="image/*" capture="environment" onChange={(e) => choosePhoto(e.target.files?.[0])} className="sr-only" />
              </label>
              <label className={`cursor-pointer ${secondaryButtonClass}`}>
                <ImagePlus className="h-4 w-4" strokeWidth={2} /> {showsPhoto ? t("Andere foto") : t("Kies foto")}
                <input type="file" accept="image/*" onChange={(e) => choosePhoto(e.target.files?.[0])} className="sr-only" />
              </label>
              {showsPhoto && (
                <button
                  type="button"
                  onClick={() => {
                    setPhoto(null);
                    setRemovePhoto(true);
                  }}
                  className="rounded-md px-3 py-2 text-sm font-medium text-slate-500 hover:text-slate-900"
                >{t("Foto verwijderen")}</button>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Ingrediënten")}</span>
          <div className="flex flex-col gap-1.5 rounded-md border border-slate-200 p-2">
            {rows.map((row) => (
              <div key={row.key} className="flex items-center gap-1.5">
                <span className="flex-1 truncate text-sm text-slate-900">{row.itemName}</span>
                <input
                  inputMode="decimal"
                  value={row.quantity}
                  onChange={(e) => updateRow(row.key, { quantity: e.target.value })}
                  className={`${inputClass} w-16 text-right`}
                />
                <input
                  value={row.unit}
                  onChange={(e) => updateRow(row.key, { unit: e.target.value })}
                  className={`${inputClass} w-20`}
                />
                <button
                  type="button"
                  onClick={() => removeRow(row.key)}
                  className="text-slate-300 hover:text-red-600"
                  title={t("Verwijderen")}
                  aria-label={t("Verwijderen")}
                >
                  <Trash2 className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
              </div>
            ))}
            {rows.length === 0 && <div className="px-1 py-1 text-sm text-slate-400">{t("Nog geen ingrediënten.")}</div>}
            <div className="mt-1">
              <AddItemCombobox onSelect={addRow} placeholder={t("Ingrediënt toevoegen…")} />
            </div>
          </div>
        </div>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Bereidingswijze")}</span>
          <textarea
            rows={6}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder={t("**Vet**, *cursief*, - opsomming en 1. genummerde stappen worden ondersteund.")}
            className={`${inputClass} resize-y`}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("Notities (optioneel)")}</span>
          <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} className={`${inputClass} resize-y`} />
        </label>

        <div className="mt-2 flex justify-end gap-2 border-t border-slate-100 pt-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >{t("Annuleren")}</button>
          <button
            type="submit"
            disabled={isSubmitting || !title.trim()}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {isSubmitting ? t("Bezig…") : t("Opslaan")}
          </button>
        </div>
      </form>
    </ModalOverlay>
  );
}
