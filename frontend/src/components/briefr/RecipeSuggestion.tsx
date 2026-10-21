import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { briefrApi } from "../../api/briefrClient";
import type { BriefrItem, BriefrRecipe } from "../../api/briefrTypes";
import { listrApi } from "../../api/listrClient";
import type { ListrMealPlanEntry } from "../../api/listrTypes";
import { t, tp } from "../../i18n";
import { ingredientLabel, planDayLabel, sourceLabel } from "../../utils/briefr";
import { addDays, range, toIso } from "../../utils/weekCalendar";
import { primaryButtonClass, secondaryButtonClass } from "../ui/kit";
import { QueryError } from "../ui/QueryError";

/** How far ahead a suggestion can be planned from here: this week and the next. */
const PLAN_DAYS = 14;

function entryTitle(entry: ListrMealPlanEntry): string {
  return entry.recipe_title ?? entry.leftover_name ?? entry.notes ?? t("Planned");
}

/** The next two weeks with what's on each day; a free day plans the recipe at once, a taken one
 * asks first whether to replace what's there. */
function DayPicker({ item, today, onDone }: { item: BriefrItem; today: string; onDone: () => void }) {
  const queryClient = useQueryClient();
  const last = addDays(today, PLAN_DAYS - 1);
  const [replacing, setReplacing] = useState<ListrMealPlanEntry | null>(null);
  const days = useQuery({ queryKey: ["listr-meal-plan", today, last], queryFn: () => listrApi.listMealPlan(today, last) });
  const plan = useMutation({
    mutationFn: ({ date, replace }: { date: string; replace: boolean }) => briefrApi.planItem(item.id, date, replace),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["briefr-report"] });
      queryClient.invalidateQueries({ queryKey: ["listr-meal-plan"] });
      queryClient.invalidateQueries({ queryKey: ["listr-recipes"] });
      onDone();
    },
  });

  if (days.isPending) return <p className="m-0 text-sm text-ui-muted" role="status">{t("Loading the weekplanner…")}</p>;
  if (days.isError) {
    return <QueryError message={t("Couldn't load the weekplanner.")} onRetry={() => days.refetch()} className="text-sm" />;
  }
  const byDate = new Map(days.data.map((e) => [e.date, e]));

  if (replacing) {
    return (
      <div className="flex flex-col gap-2 rounded-xl bg-ui-tile p-3">
        <p className="m-0 text-sm text-ui-ink">
          {t("{day} already has {title}. Replace it?", { day: planDayLabel(replacing.date, today), title: entryTitle(replacing) })}
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={primaryButtonClass}
            disabled={plan.isPending}
            onClick={() => plan.mutate({ date: replacing.date, replace: true })}
          >
            {plan.isPending ? t("Planning…") : t("Replace")}
          </button>
          <button type="button" className={secondaryButtonClass} disabled={plan.isPending} onClick={() => setReplacing(null)}>
            {t("Cancel")}
          </button>
        </div>
        {plan.isError && <p className="m-0 text-sm text-ui-late" role="alert">{t("Couldn't plan the recipe. Try again.")}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="m-0 text-sm font-semibold text-ui-ink-soft">{t("Which day?")}</p>
      <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-3">
        {range(today, last).map((date) => {
          const entry = byDate.get(date);
          return (
            <li key={date}>
              <button
                type="button"
                disabled={plan.isPending}
                onClick={() => (entry ? setReplacing(entry) : plan.mutate({ date, replace: false }))}
                className="flex w-full flex-col items-start rounded-xl border border-ui-border px-3 py-2 text-left hover:bg-ui-tile disabled:opacity-60"
              >
                <span className="text-sm font-semibold text-ui-ink">{planDayLabel(date, today)}</span>
                <span className={`w-full truncate text-[13px] ${entry ? "text-ui-ink-soft" : "text-ui-muted"}`}>
                  {entry ? entryTitle(entry) : t("Free")}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {plan.isError && <p className="m-0 text-sm text-ui-late" role="alert">{t("Couldn't plan the recipe. Try again.")}</p>}
      <div>
        <button type="button" className={secondaryButtonClass} disabled={plan.isPending} onClick={onDone}>
          {t("Cancel")}
        </button>
      </div>
    </div>
  );
}

function RecipeFacts({ recipe }: { recipe: BriefrRecipe }) {
  const facts = [
    recipe.servings !== null ? tp(recipe.servings, "{n} serving", "{n} servings") : null,
    recipe.minutes !== null ? t("{n} min", { n: recipe.minutes }) : null,
  ].filter((fact): fact is string => fact !== null);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-ui-muted">
      {facts.map((fact) => (
        <span key={fact}>{fact}</span>
      ))}
      <a
        href={recipe.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 hover:text-ui-ink hover:underline"
      >
        {sourceLabel(recipe.url)}
        <ExternalLink size={12} aria-hidden />
      </a>
    </div>
  );
}

/** A finding that suggests a recipe: what it is, the recipe itself folded away, and planning it
 * in listr's weekplanner, which makes it a listr recipe the first time. */
export default function RecipeSuggestion({ item, recipe, now }: { item: BriefrItem; recipe: BriefrRecipe; now: Date }) {
  const [picking, setPicking] = useState(false);
  const today = toIso(now);
  const upcoming = recipe.planned_on.filter((date) => date >= today);
  return (
    <li className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
      <span className="text-[15px] font-semibold text-ui-ink">{item.headline}</span>
      {item.detail && <p className="m-0 whitespace-pre-line text-sm text-ui-ink-soft">{item.detail}</p>}
      <RecipeFacts recipe={recipe} />
      <details className="text-sm text-ui-ink">
        <summary className="cursor-pointer text-ui-ink-soft">{t("Ingredients and steps")}</summary>
        <div className="flex flex-col gap-2 pt-2">
          <ul className="m-0 list-disc pl-5">
            {recipe.ingredients.map((ingredient, n) => (
              <li key={n}>{ingredientLabel(ingredient)}</li>
            ))}
          </ul>
          <ol className="m-0 list-decimal pl-5">
            {recipe.steps.map((step, n) => (
              <li key={n}>{step}</li>
            ))}
          </ol>
        </div>
      </details>
      {upcoming.length > 0 && (
        <p className="m-0 flex flex-wrap items-center gap-x-2 text-sm text-ui-ink-soft" role="status">
          {t("Planned for {days}", { days: upcoming.map((date) => planDayLabel(date, today)).join(", ") })}
          <Link to="/listr/weekplanner" className="font-semibold text-ui-brand-strong hover:underline">{t("Open weekplanner")}</Link>
          {recipe.listr_recipe_id !== null && (
            <Link to={`/listr/recept/${recipe.listr_recipe_id}`} className="font-semibold text-ui-brand-strong hover:underline">
              {t("Open recipe")}
            </Link>
          )}
        </p>
      )}
      {picking ? (
        <DayPicker item={item} today={today} onDone={() => setPicking(false)} />
      ) : (
        <div>
          <button type="button" className={upcoming.length ? secondaryButtonClass : primaryButtonClass} onClick={() => setPicking(true)}>
            {upcoming.length ? t("Plan another day") : t("Plan in listr")}
          </button>
        </div>
      )}
    </li>
  );
}
