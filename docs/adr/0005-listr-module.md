# 5. listr: a third module, filename-prefixed like gripr

## Status

Accepted

## Context

listr (grocery lists + recipes, in Dutch) is the app's third module alongside gainr
(investments) and gripr (personal finance). It needed: a data model for saved/reusable grocery
lists, a product catalog organized by category, recipes whose ingredients link to that catalog,
and a way to add some or all of a recipe's ingredients to a chosen list.

## Decisions

**Module boundary**: listr follows the exact pattern gripr already established for being a
second module in this codebase — `listr_*.py` files in the same `backend/app/{routers,
services,repositories,models,schemas}/` directories as gainr's and gripr's (no subpackage), and
`frontend/src/pages/listr/` / `components/listr/` / `api/listrClient.ts`+`listrTypes.ts`
alongside gripr's equivalents. This confirms the pattern is the repo's convention for adding a
module, not a one-off gripr decision.

**The catalog is a real, editable database table, not a frontend constant.** The user was
explicit about this: "I want you to create a database of the Dutch common groceries and also
the ability to add new products myself if they don't exist." `ListrItem` is seeded once
(`backend/scripts/seed_listr.py`, ~220 items across 12 categories, idempotent/safe to re-run)
and then extended through the UI (`POST /api/listr/items`, get-or-create by name) — never a
hardcoded list the app merely displays.

**Recipe ingredients link to the catalog** (a real `grocery_item_id`), not free text. This is
what makes "add these ingredients to my grocery list" a reliable lookup instead of a fuzzy-match
problem, and it's why every ingredient and list line carries a real category along for free.

**Named, reusable lists** (`ListrList`), not one perpetual cart — archived rather than
deleted, and duplicable, so a "BBQ" list from last summer can be reused as a starting point
rather than rebuilt from scratch.

**Merging is same-item-and-same-unit only.** `listr_list_service.add_ingredients_to_list`
sums quantities onto an existing line only when both the grocery item *and* the unit match
exactly; a different unit for the same item (e.g. "200 gram" vs. "1 stuk") is kept as its own
line rather than the app guessing a conversion between units it doesn't actually know the
relationship between. Confirmed working end-to-end: adding a recipe's "3 kg" of an item onto a
list that already had "2 kg" of it produced one 5 kg line, not two.

**Checked-off list lines are hard-deleted, not archived**, unlike almost everything else
reference-shaped in this app. A grocery list line has no lasting record value the way a gripr
transaction does — "clear checked items" is meant to actually clear them.

**Dutch is hardcoded directly in listr's own components**, the same way gainr/gripr hardcode
English — no i18n framework. This app has no reader to switch languages for, and it would be
new-abstraction-ahead-of-need. This is separate from (and does not conflict with) the
catalog-must-be-a-database decision above, which is about product *data*, not UI microcopy.

## Alternatives considered

- **Free-text recipe ingredients**: faster to enter, but "add to list" would need fuzzy string
  matching against the catalog with no reliable category, defeating the point of linking.
- **One perpetual list instead of named/saved lists**: simpler model, but doesn't support the
  "BBQ list I want to reuse next summer" case the user specifically wanted multiple lists for.
- **Guessing unit conversions when merging** (e.g. treating "500 gram" as within tolerance of
  "0.5 kg"): rejected — a wrong guess silently corrupts a shopping list's quantities, and this
  app has no unit-conversion table to guess from safely.

## Consequences

- Every list line and recipe ingredient requires a catalog item to exist first — there's no
  freeform "just this once" item on a list. The inline "+ product toevoegen" flow in
  `AddItemCombobox` exists specifically to make that not feel like friction: creating the
  catalog entry and adding it to the list/recipe is one action, not two.
- Deleting a `ListrItem` outright isn't exposed anywhere (only archiving) — a hard delete
  would orphan any list line or recipe ingredient still referencing it. Same reasoning as gripr's
  categories, applied here too.
