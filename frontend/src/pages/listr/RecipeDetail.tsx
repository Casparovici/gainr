import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, ShoppingCart, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { listrApi } from "../../api/listrClient";
import { sourceLabel } from "../../utils/briefr";
import type { ListrRecipeInput } from "../../api/listrTypes";
import AddToListDialog from "../../components/listr/AddToListDialog";
import RecipeForm from "../../components/listr/RecipeForm";
import RecipePhoto from "../../components/listr/RecipePhoto";
import MarkdownLite from "../../components/MarkdownLite";
import LinkedNotes from "../../components/notr/LinkedNotes";
import {
  IconChevronLeft,
  IconPencil,
  ModuleTopRow,
  PageTitle,
  iconButtonClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "../../components/ui/kit";
import { QueryError } from "../../components/ui/QueryError";
import { formatQuantity } from "../../utils/format";
import { t } from "../../i18n";

export default function ListrRecipeDetail() {
  const { id } = useParams<{ id: string }>();
  const recipeId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [addingToList, setAddingToList] = useState(false);

  const { data: recipe, isLoading, isError, refetch } = useQuery({
    queryKey: ["listr-recipe", recipeId],
    queryFn: () => listrApi.getRecipe(recipeId),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ input, photo, removePhoto }: { input: ListrRecipeInput; photo: File | null; removePhoto: boolean }) => {
      await listrApi.updateRecipe(recipeId, input);
      if (photo) await listrApi.setRecipePhoto(recipeId, photo);
      else if (removePhoto) await listrApi.deleteRecipePhoto(recipeId);
    },
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

  if (isError) {
    return <QueryError className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center" message={t("Recept laden mislukt.")} onRetry={() => refetch()} retryLabel={t("Opnieuw")} />;
  }
  if (isLoading || !recipe) {
    return <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">{t("Laden…")}</div>;
  }

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow
        left={
          <Link to="/listr/recepten" aria-label={t("Terug naar recepten")} className={`${secondaryButtonClass} pl-2 pr-3 no-underline`}>
            <IconChevronLeft size={20} />{t("Recepten")}</Link>
        }
      >
        <button onClick={() => setEditing(true)} className={secondaryButtonClass}>
          <IconPencil size={18} />{t("Bewerken")}</button>
        <button
          onClick={() => {
            if (confirm(t("Recept \"{title}\" verwijderen? Dit kan niet ongedaan worden gemaakt.", { title: recipe.title }))) deleteMutation.mutate();
          }}
          className={`${iconButtonClass} text-ui-late`}
          title={t("Verwijderen")}
          aria-label={t("Verwijderen")}
        >
          <Trash2 className="h-[18px] w-[18px]" strokeWidth={2} />
        </button>
      </ModuleTopRow>

      <div className="flex flex-col gap-2">
        <PageTitle size="md" subtitle={recipe.servings ? t("{servings} personen", { servings: recipe.servings }) : undefined}>
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

      {recipe.has_photo && (
        <RecipePhoto recipe={recipe} alt={recipe.title} className="aspect-[16/9] w-full rounded-[20px] sm:max-h-80" />
      )}

      {recipe.mealie_id && (
        <p className="rounded-2xl bg-ui-tile px-4 py-3 text-sm text-ui-ink-soft">{t("Uit Mealie. Pas dit recept daar aan: bij de volgende \"Ophalen uit Mealie\" wordt deze versie overschreven.")}</p>
      )}

      {recipe.source_url && (
        <a
          href={recipe.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 self-start text-sm text-ui-muted hover:text-ui-ink hover:underline"
        >
          {t("Bron: {site}", { site: sourceLabel(recipe.source_url) })}
          <ExternalLink size={12} aria-hidden />
        </a>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="flex flex-col gap-3 rounded-[20px] border border-ui-border bg-ui-surface p-4 lg:col-span-1">
          <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">{t("Ingrediënten")}</h2>
          <ul className="flex flex-col text-[15px]">
            {recipe.ingredients.map((ing) => (
              <li key={ing.id} className="flex justify-between gap-2 border-b border-ui-border py-2 last:border-0">
                <span className="text-ui-ink">{ing.grocery_item_name}</span>
                <span className="shrink-0 tabular-nums text-ui-muted">
                  {formatQuantity(ing.quantity)} {ing.unit}
                </span>
              </li>
            ))}
            {recipe.ingredients.length === 0 && <li className="text-ui-muted">{t("Nog geen ingrediënten.")}</li>}
          </ul>
          <button onClick={() => setAddingToList(true)} className={primaryButtonClass} disabled={recipe.ingredients.length === 0}>
            <ShoppingCart className="h-[18px] w-[18px]" strokeWidth={2} />{t("Op boodschappenlijst")}</button>
        </div>

        <div className="flex flex-col gap-2 rounded-[20px] border border-ui-border bg-ui-surface p-4 lg:col-span-2">
          <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">{t("Bereidingswijze")}</h2>
          <div className="text-[15px] leading-relaxed text-ui-ink-soft">
            {recipe.instructions ? <MarkdownLite text={recipe.instructions} /> : <span className="text-ui-muted">{t("Nog geen bereidingswijze.")}</span>}
          </div>
          {recipe.notes && (
            <>
              <h2 className="m-0 mt-3 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">{t("Notities")}</h2>
              <div className="text-[15px] leading-relaxed text-ui-ink-soft">
                <MarkdownLite text={recipe.notes} />
              </div>
            </>
          )}
        </div>
      </div>

      {/* The recipe's own short note sits above; richer notes (notr, with pictures and checklists) go here. */}
      <section aria-label={t("Notities in notr")} className="flex flex-col gap-2 rounded-[20px] border border-ui-border bg-ui-surface p-4">
        <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">{t("Notities in notr")}</h2>
        <LinkedNotes recipeId={recipe.id} />
      </section>

      {editing && (
        <RecipeForm
          initial={recipe}
          isSubmitting={updateMutation.isPending}
          onCancel={() => setEditing(false)}
          onSubmit={(input, photo, removePhoto) => updateMutation.mutate({ input, photo, removePhoto })}
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
