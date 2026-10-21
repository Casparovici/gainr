# 6. listr: recipe categories and meal-plan history

## Status

Accepted

## Context

listr roadmap #1 asked for three related things: recipes tagged by cuisine/type (Italian,
Asian, ...), a Weekplanner tab to plan which recipe gets cooked on which day, and a "most
popular recipes" ranking based on what actually got cooked. This needed two new data concepts
beyond what the module already had: a category-like tag on recipes, and a record of meal
history distinct from a recipe's own definition.

## Decisions

**Recipe categories are a separate table from the product catalog's `ListrCategory`, and are
many-to-many.** The user confirmed a recipe can carry several tags at once ("Italiaans" +
"Vegetarisch"), whereas the product catalog's category is a required one-per-item container for
`ListrItem` with a globally unique name. Reusing that table would mean the wrong cardinality
and a name-collision risk (a recipe category and a grocery category both wanting to be named
"Fruit", say). `ListrRecipeCategory` copies the same shape (`name`, `sort_order`, `color`,
`is_archived`) and CRUD pattern, connected to `ListrRecipe` via a plain association table
(`listr_recipe_category_links`), under its own `/api/listr/recipe-categories` path.

**The meal plan is one row per calendar date, not a recurrence rule.** The user chose "one
recipe per day" over separate meal slots. `ListrMealPlan.date` is unique, so a day's entry is
always upserted in place rather than the app needing to track whether one already exists. This
is deliberately not modeled after gripr's recurring-transaction pattern (a frequency + interval +
lazily-materialized occurrences) — a weekplanner is explicit, per-day assignment, not an
indefinitely repeating rule, so a recurrence engine would be solving a problem the feature
doesn't have.

**Planning a recipe onto a date is not itself "having eaten it."** The user was explicit here:
they want to *confirm* a meal was actually cooked, not have the calendar assume every planned
day happened. `is_cooked` is a separate boolean the day-editor toggles, and the popularity
ranking (`listr_meal_plan_repo.popular_recipes`) only counts rows where `is_cooked = true`
**and** `recipe_id is not null` — a planned-but-skipped meal, or a note-only day ("uit eten"),
never inflates a recipe's count.

**A day can carry a note with no recipe attached, or a note alongside one.** Not every meal is
from the catalog — "uit eten", "restjes" — so `recipe_id` is nullable and `notes` is independent
of it. This also means clearing a day (`DELETE /meal-plan/{date}`) and blanking a recipe out of
a day (still keeping a note) are both simple, uniform writes rather than special cases.

**Deleting a recipe unlinks its meal-plan history instead of cascading into it or blocking the
delete.** Same convention gripr already uses for a deleted category's transactions: the
historical fact ("something was cooked on this date, and it was marked cooked") outlives the
recipe definition. `listr_meal_plan_repo.unlink_recipe` sets `recipe_id` to `NULL` on any
affected rows before the recipe itself is deleted.

## Alternatives considered

- **A single `category_id` FK on `ListrRecipe`** (mirroring the product catalog): simpler, but
  directly contradicted the user's explicit "multiple tags at once" requirement.
- **Treating a planned day as automatically "eaten" once its date passes**: no extra click, but
  the user specifically wanted an explicit confirmation step so a planned-then-skipped meal
  doesn't pollute the popularity ranking.
- **Reusing gripr's recurring-rule model for repeating meals** (e.g. "spaghetti every Monday"):
  would add real complexity (frequency/interval/catch-up materialization) for a feature the user
  didn't ask for; a weekplanner's day-by-day, explicit-assignment shape doesn't need it.

## Consequences

- A week/month grid always fetches a date range (`GET /meal-plan?date_from=&date_to=`) rather
  than per-cell requests — the month view's wider range is one query, same as the week view's
  narrower one.
- The popularity ranking is a live aggregate query, not a maintained counter — correct by
  construction (nothing to keep in sync) at the cost of a `GROUP BY` over the meal-plan table,
  which is fine at this app's single-user scale.

## Addendum: moving a planned day

`POST /api/listr/meal-plan/{date}/move` re-dates the row in place (`{"to": date}`), so its recipe,
note, cooked flag and `leftover_consumed` travel with it and a leftover's meal count needs no
refund-and-redo. The target must be free: a planned target answers 409 rather than being replaced
or swapped, since silently dropping a planned recipe is the worse surprise. No schema change.
