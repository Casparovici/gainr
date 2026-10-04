import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShoppingCart, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { listrApi } from "../../api/listrClient";
import type { ListrRecipeInput } from "../../api/listrTypes";
import AddToListDialog from "../../components/listr/AddToListDialog";
import RecipeForm from "../../components/listr/RecipeForm";
import MarkdownLite from "../../components/MarkdownLite";
import {
  IconChevronLeft,
  IconPencil,
  ModuleTopRow,
  PageTitle,
  iconButtonClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "../../components/ui/kit";
import { formatQuantity } from "../../utils/format";

export default function ListrRecipeDetail() {
  const { id } = useParams<{ id: string }>();
  const recipeId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [addingToList, setAddingToList] = useState(false);

  const { data: recipe, isLoading } = useQuery({
    queryKey: ["listr-recipe", recipeId],
    queryFn: () => listrApi.getRecipe(recipeId),
  });

  const updateMutation = useMutation({
    mutationFn: (input: ListrRecipeInput) => listrApi.updateRecipe(recipeId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listr-recipe", recipeId] });
      queryClient.invalidateQueries({ queryKey: ["listr-recipes"] });
      setEditing(false);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: () => listrApi.deleteRecipe(recipeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listr-recipes"] });
      navigate("/listr/recepten");
    },
  });
  const addToListMutation = useMutation({
    mutationFn: (input: { listId: number | null; newListName: string | null; ingredientIds: number[] }) =>
      listrApi.addRecipeToList(recipeId, {
        list_id: input.listId ?? undefined,
        new_list_name: input.newListName ?? undefined,
        ingredient_ids: input.ingredientIds,
      }),
    onSuccess: (list) => {
      queryClient.invalidateQueries({ queryKey: ["listr-lists"] });
      setAddingToList(false);
      navigate(`/listr/lijst/${list.id}`);
    },
  });

  if (isLoading || !recipe) {
    return <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">Laden…</div>;
  }

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow
        left={
          <Link to="/listr/recepten" aria-label="Terug naar recepten" className={`${secondaryButtonClass} pl-2 pr-3 no-underline`}>
            <IconChevronLeft size={20} />
            Recepten
          </Link>
        }
      >
        <button onClick={() => setEditing(true)} className={secondaryButtonClass}>
          <IconPencil size={18} />
          Bewerken
        </button>
        <button
          onClick={() => {
            if (confirm(`Recept "${recipe.title}" verwijderen? Dit kan niet ongedaan worden gemaakt.`)) deleteMutation.mutate();
          }}
          className={`${iconButtonClass} text-ui-late`}
          title="Verwijderen"
          aria-label="Verwijderen"
        >
          <Trash2 className="h-[18px] w-[18px]" strokeWidth={2} />
        </button>
      </ModuleTopRow>

      <div className="flex flex-col gap-2">
        <PageTitle size="md" subtitle={recipe.servings ? `${recipe.servings} personen` : undefined}>
          {recipe.title}
        </PageTitle>
        {recipe.categories.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {recipe.categories.map((c) => (
              <span
                key={c.id}
                className="inline-flex h-[26px] items-center gap-[5px] rounded-full bg-ui-tile px-2.5 text-[13px] font-semibold text-ui-ink-soft"
              >
                {c.color && <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: c.color }} />}
                {c.name}
              </span>
            ))}
          </div>
        )}
      </div>

      {recipe.mealie_id && (
        <p className="rounded-2xl bg-ui-tile px-4 py-3 text-sm text-ui-ink-soft">
          Uit Mealie. Pas dit recept daar aan: bij de volgende "Ophalen uit Mealie" wordt deze versie overschreven.
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="flex flex-col gap-3 rounded-[20px] border border-ui-border bg-ui-surface p-4 lg:col-span-1">
          <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">Ingrediënten</h2>
          <ul className="flex flex-col text-[15px]">
            {recipe.ingredients.map((ing) => (
              <li key={ing.id} className="flex justify-between gap-2 border-b border-ui-border py-2 last:border-0">
                <span className="text-ui-ink">{ing.grocery_item_name}</span>
                <span className="shrink-0 tabular-nums text-ui-muted">
                  {formatQuantity(ing.quantity)} {ing.unit}
                </span>
              </li>
            ))}
            {recipe.ingredients.length === 0 && <li className="text-ui-muted">Nog geen ingrediënten.</li>}
          </ul>
          <button onClick={() => setAddingToList(true)} className={primaryButtonClass} disabled={recipe.ingredients.length === 0}>
            <ShoppingCart className="h-[18px] w-[18px]" strokeWidth={2} />
            Op boodschappenlijst
          </button>
        </div>

        <div className="flex flex-col gap-2 rounded-[20px] border border-ui-border bg-ui-surface p-4 lg:col-span-2">
          <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">Bereidingswijze</h2>
          <div className="text-[15px] leading-relaxed text-ui-ink-soft">
            {recipe.instructions ? <MarkdownLite text={recipe.instructions} /> : <span className="text-ui-muted">Nog geen bereidingswijze.</span>}
          </div>
          {recipe.notes && (
            <>
              <h2 className="m-0 mt-3 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">Notities</h2>
              <div className="text-[15px] leading-relaxed text-ui-ink-soft">
                <MarkdownLite text={recipe.notes} />
              </div>
            </>
          )}
        </div>
      </div>

      {editing && (
        <RecipeForm
          initial={recipe}
          isSubmitting={updateMutation.isPending}
          onCancel={() => setEditing(false)}
          onSubmit={(input) => updateMutation.mutate(input)}
        />
      )}
      {addingToList && (
        <AddToListDialog
          recipe={recipe}
          isSubmitting={addToListMutation.isPending}
          onCancel={() => setAddingToList(false)}
          onSubmit={(input) => addToListMutation.mutate(input)}
        />
      )}
    </div>
  );
}
