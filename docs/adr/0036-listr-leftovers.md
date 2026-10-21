# 36. listr: leftovers are their own dated table, eaten from the weekplanner

## Status

Accepted

## Context

After cooking for four, two more meals for four go in the freezer. listr had nowhere to put that:
Voorraad ([ADR 0015](0015-listr-inventory.md)) counts catalog groceries, and a weekplanner day
could only carry a recipe or a free-text note ("restjes").

## Decisions

**A separate `grecipe_leftovers` table, not tracked `ListrItem`s.** A batch is a one-off with a
date and a use-by date, not a reference product that is restocked. Putting "Bolognese" in the
catalog would pollute Producten and give a dated thing an undated count. Columns: `name`,
`recipe_id` (nullable, unlinked when the recipe is deleted), `meals` (a bare tally, like
`inventory_count`), `servings_per_meal` (informational: nothing scales with it), `location`
(`freezer`/`fridge`), `stored_on`, `use_by`.

**Use-by is required and defaulted by location**: 3 days in the fridge, 90 in the freezer, when
the reader leaves it blank. The default lives on the server only (`listr_leftover_service`); the
form says what blank means. Nothing expires or notifies by itself; the Voorraad card colours a
batch amber within 3 days of its use-by and red once past.

**A used-up batch stays as a row with `meals = 0`** and drops off the list, rather than being
deleted or flagged archived, because a cooked weekplanner day may still point at it and un-cooking
that day must be able to give the meal back.

**A weekplanner day carries a recipe or a leftover, never both** (`ListrMealPlan.leftover_id`;
400 otherwise). Planning a leftover changes nothing; marking the day cooked takes one meal off.
`leftover_consumed` on the day records whether it already took one, so saving twice never deducts
twice, and un-cooking, switching to another leftover or recipe, or clearing the day gives the meal
back. Eating a meal that isn't there is a 409. Deleting a leftover unlinks the days that ate it
without refunding. A leftover day adds nothing to the shopping list and doesn't count toward the
recipe popularity ranking (it has no `recipe_id`).

**Storing leftovers is offered where they appear**: ticking "Ik heb dit gekookt" on a recipe in
the day editor offers "Restjes bewaren" (meals, people, location, use-by), and also from Voorraad
for anything else. This is the one place cooking creates stock, and it only does so when asked.

## Alternatives considered

- **Leftovers as tracked catalog items**: rejected for the reasons above.
- **Deduct a meal as soon as the day is planned**: rejected; planning isn't eating, the same line
  [ADR 0006](0006-listr-meal-planning.md) draws for `is_cooked`.
- **Automatic expiry (archive past use-by)**: rejected; food past its date is the reader's call,
  so it stays listed in red until they remove it.
- **Scaling meals by number of people**: rejected; `servings_per_meal` is just a note.
