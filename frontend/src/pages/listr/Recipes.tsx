import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChefHat, DownloadCloud, ShoppingCart } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listrApi } from "../../api/listrClient";
import type { ListrRecipeInput } from "../../api/listrTypes";
import MealieImportDialog from "../../components/listr/MealieImportDialog";
import PicnicImportDialog from "../../components/listr/PicnicImportDialog";
import RecipeForm from "../../components/listr/RecipeForm";
import { IconChevronRight, IconPlus, ModuleTopRow, PageTitle, dashedButtonClass, secondaryButtonClass } from "../../components/ui/kit";

export default function ListrRecipes() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [importingFromPicnic, setImportingFromPicnic] = useState(false);
  const [importingFromMealie, setImportingFromMealie] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<number[]>([]);

  const { data: recipes, isLoading } = useQuery({
    queryKey: ["listr-recipes"],
    queryFn: () => listrApi.listRecipes(),
  });
  const { data: categories } = useQuery({
    queryKey: ["listr-recipe-categories"],
    queryFn: () => listrApi.listRecipeCategories(),
  });
  const { data: picnicStatus } = useQuery({
    queryKey: ["listr-picnic-status"],
    queryFn: () => listrApi.picnicStatus(),
  });
  const { data: mealieStatus } = useQuery({
    queryKey: ["listr-mealie-status"],
    queryFn: () => listrApi.mealieStatus(),
  });

  const createMutation = useMutation({
    mutationFn: (input: ListrRecipeInput) => listrApi.createRecipe(input),
    onSuccess: (recipe) => {
      queryClient.invalidateQueries({ queryKey: ["listr-recipes"] });
      setCreating(false);
      navigate(`/listr/recept/${recipe.id}`);
    },
  });

  function toggleFilter(id: number) {
    setCategoryFilter((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]));
  }

  const visibleRecipes = (recipes ?? []).filter(
    (r) => categoryFilter.length === 0 || r.categories.some((c) => categoryFilter.includes(c.id)),
  );

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow>
        {mealieStatus?.configured && (
          <button onClick={() => setImportingFromMealie(true)} className={secondaryButtonClass} aria-label="Ophalen uit Mealie">
            <DownloadCloud className="h-4 w-4" strokeWidth={2} />
            <span className="sm:hidden">Mealie</span>
            <span className="hidden sm:inline">Ophalen uit Mealie</span>
          </button>
        )}
        {picnicStatus?.configured && (
          <button onClick={() => setImportingFromPicnic(true)} className={secondaryButtonClass} aria-label="Importeren van Picnic">
            <ShoppingCart className="h-4 w-4" strokeWidth={2} />
            <span className="sm:hidden">Picnic</span>
            <span className="hidden sm:inline">Importeren van Picnic</span>
          </button>
        )}
      </ModuleTopRow>
      <PageTitle subtitle={recipes && recipes.length > 0 ? `${recipes.length} ${recipes.length === 1 ? "recept" : "recepten"}` : undefined}>
        Recepten
      </PageTitle>

      {categories && categories.length > 0 && (
        // One scrolling row on a phone instead of three wrapped ones; wraps from tablet width up.
        <div className="-mx-4 flex items-center gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
          {categories.map((category) => {
            const selected = categoryFilter.includes(category.id);
            return (
              <button
                key={category.id}
                type="button"
                onClick={() => toggleFilter(category.id)}
                aria-pressed={selected}
                className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-sm font-semibold transition-colors ${
                  selected
                    ? "border-ui-brand bg-ui-brand-soft text-ui-brand-strong"
                    : "border-ui-border bg-ui-surface text-ui-ink-soft hover:border-ui-line"
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
      )}

      {isLoading ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">Laden…</div>
      ) : !recipes || recipes.length === 0 ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-8 text-center text-ui-muted">
          Nog geen recepten — voeg er hieronder een toe.
        </div>
      ) : visibleRecipes.length === 0 ? (
        <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-8 text-center text-ui-muted">
          Geen recepten in deze categorie.
        </div>
      ) : (
        // One list, like gripr's accounts: a row per recipe, compact enough to scan a long cookbook.
        <ul aria-label="Recepten" className="divide-y divide-ui-border overflow-hidden rounded-[20px] border border-ui-border bg-ui-surface">
          {visibleRecipes.map((recipe) => (
            <li key={recipe.id}>
              <Link
                to={`/listr/recept/${recipe.id}`}
                className="flex min-h-[52px] items-center gap-3 px-4 py-2.5 transition-colors hover:bg-ui-tile"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ui-brand-soft text-ui-brand-strong">
                  <ChefHat className="h-4 w-4" strokeWidth={2} />
                </span>
                <span className="flex min-w-0 flex-grow flex-col">
                  <span className="truncate font-semibold text-ui-ink">{recipe.title}</span>
                  <span className="flex min-w-0 items-center gap-2 text-sm text-ui-muted">
                    <span className="shrink-0">{recipe.servings ? `${recipe.servings} personen` : "Personen onbekend"}</span>
                    {recipe.categories.map((c) => (
                      <span key={c.id} className="flex min-w-0 items-center gap-1">
                        <span aria-hidden className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: c.color ?? "currentColor" }} />
                        <span className="truncate">{c.name}</span>
                      </span>
                    ))}
                  </span>
                </span>
                <span className="shrink-0 text-ui-muted">
                  <IconChevronRight size={18} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <button type="button" onClick={() => setCreating(true)} className={dashedButtonClass}>
        <IconPlus size={20} />
        Nieuw recept
      </button>

      {creating && (
        <RecipeForm
          initial={undefined}
          isSubmitting={createMutation.isPending}
          onCancel={() => setCreating(false)}
          onSubmit={(input) => createMutation.mutate(input)}
        />
      )}

      {importingFromPicnic && (
        <PicnicImportDialog
          onClose={() => setImportingFromPicnic(false)}
          onImported={(recipeId) => {
            setImportingFromPicnic(false);
            navigate(`/listr/recept/${recipeId}`);
          }}
        />
      )}

      {importingFromMealie && <MealieImportDialog onClose={() => setImportingFromMealie(false)} />}
    </div>
  );
}
