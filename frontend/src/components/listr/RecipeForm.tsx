import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Trash2 } from "lucide-react";

import { listrApi } from "../../api/listrClient";
import type { ListrItem, ListrRecipe, ListrRecipeInput } from "../../api/listrTypes";
import { decimalInputToApi, formatQuantity } from "../../utils/format";
import ModalOverlay from "../ModalOverlay";
import AddItemCombobox from "./AddItemCombobox";

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
  onSubmit: (input: ListrRecipeInput) => void;
}) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(initial?.title ?? "");
  const [servings, setServings] = useState(initial?.servings != null ? String(initial.servings) : "");
  const [instructions, setInstructions] = useState(initial?.instructions ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [rows, setRows] = useState<IngredientRow[]>(() => toRows(initial));
  const [categoryIds, setCategoryIds] = useState<number[]>(() => (initial?.categories ?? []).map((c) => c.id));
  const [newCategoryName, setNewCategoryName] = useState("");

  const { data: categories } = useQuery({
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
    });
  }

  return (
    <ModalOverlay onClose={onCancel} cardClassName="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-lg bg-white p-5 shadow-lg">
      <h2 className="text-base font-semibold text-slate-900">{initial ? "Recept bewerken" : "Nieuw recept"}</h2>
      <form onSubmit={handleSubmit} className="mt-4 flex flex-1 flex-col gap-4 overflow-y-auto">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="col-span-2 flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Titel</span>
            <input required autoFocus value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Aantal personen</span>
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
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Categorieën</span>
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
              placeholder="+ nieuwe categorie…"
              className={`${inputClass} w-36`}
            />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Ingrediënten</span>
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
                  title="Verwijderen"
                  aria-label="Verwijderen"
                >
                  <Trash2 className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
              </div>
            ))}
            {rows.length === 0 && <div className="px-1 py-1 text-sm text-slate-400">Nog geen ingrediënten.</div>}
            <div className="mt-1">
              <AddItemCombobox onSelect={addRow} placeholder="Ingrediënt toevoegen…" />
            </div>
          </div>
        </div>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Bereidingswijze</span>
          <textarea
            rows={6}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="**Vet**, *cursief*, - opsomming en 1. genummerde stappen worden ondersteund."
            className={`${inputClass} resize-y`}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Notities (optioneel)</span>
          <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} className={`${inputClass} resize-y`} />
        </label>

        <div className="mt-2 flex justify-end gap-2 border-t border-slate-100 pt-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Annuleren
          </button>
          <button
            type="submit"
            disabled={isSubmitting || !title.trim()}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {isSubmitting ? "Bezig…" : "Opslaan"}
          </button>
        </div>
      </form>
    </ModalOverlay>
  );
}
