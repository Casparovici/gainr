# 54. briefr: a weekly home chef, whose recipes can be planned in listr from the report

## Status

Accepted. Builds on [ADR 0044](0044-briefr-agent-reports.md) (agent reports) and
[ADR 0006](0006-listr-meal-planning.md) (the weekplanner).

## Context

The owner wants a "home chef" agent: once a week it suggests five recipes, preferably from Dutch
sites (leukerecepten.nl, delicious.nl and its magazine, deliciousmagazine.nl), the suggestions
show up in briefr, and from there a recipe can be picked and planned in listr's weekplanner.

Finding recipes means reading the open web, which is what the cloud agents already do (ADR 0044).
What's new is the way back: so far a report was only read; this one has to turn into a listr
recipe on a day of the week.

## Decisions

**A cloud agent like the holdings scan.** `home-chef` is a Claude scheduled task, every Friday
morning, whose brief lives at `agents/home-chef/BRIEF.md` in the agents repository. It commits
`reports/home-chef/<date>.md`, which briefr imports like any other report. Friday, so the week's
meals can be picked before the weekend's shopping.

**The agent writes the recipe out; the server never fetches a recipe page.** A finding may carry
a `[items.recipe]` table: the page's `url`, `servings`, `minutes`, the `ingredients` (each a
`name`, optional `quantity`, `unit` and `note`) and the `steps`. The agent has read the page
anyway; having the server scrape it instead would make it fetch arbitrary URLs taken from a file
written after reading the web, the one thing ADR 0044 kept it from doing. Like the rest of a
report it is untrusted and bounded on import: an http(s) `url` of at most 500 characters, at most
60 ingredients and 40 steps, each field capped, a blank step or name refused. The recipe is kept
as JSON in a new nullable `briefr_report_items.recipe`, the way `sources` already is.

```text
[[items]]
verdict = "watch"
headline = "Pasta met spinazie en zalm"
detail = "Snel doordeweeks, 25 minuten."
sources = ["https://www.leukerecepten.nl/recepten/…"]

[items.recipe]
url = "https://www.leukerecepten.nl/recepten/…"
servings = 4
minutes = 25
steps = ["Kook de pasta.", "…"]

[[items.recipe.ingredients]]
name = "Penne"            # a product from context/listr-products.md when one fits
quantity = 400
unit = "gram"
```

**The agent gets listr's product catalog as context.** `scripts/export_briefr_context.py` also
writes `context/listr-products.md`: every product that isn't archived, per category, with its
default unit. The brief asks for ingredient names exactly as a product there when one fits. It's
grocery names only: nothing about stock, lists, orders or what was eaten, so the meal history
stays on the server. The agent avoids repeats from its own earlier reports instead.

**Planning is one tap in the report.** A recipe finding shows its facts, its ingredients and
steps folded away, and **Plan in listr**, which offers the next 14 days with what's already on
each. A free day plans it at once; a taken day asks before replacing what's there (the server
answers 409 unless the request says `replace`). `POST /api/briefr/items/{id}/plan` is the only
write in briefr's router beyond the reader's own read and archive state, and it only runs when
the reader asks.

**The first plan makes it a listr recipe, once.** `briefr_chef_service.plan_suggestion` creates
the recipe with the headline as its title, the steps as a numbered list, and the page as a new
nullable, unique `grecipe_recipes.source_url`. Planning the same suggestion again, or the same
page from a later week, reuses that recipe with whatever the reader changed in it. An ingredient
becomes a recipe line only when its name certainly means a product: the same name ignoring case,
or its Dutch plural (`listr_catalog_service.match_product`, the plural rules moved there from the
Mealie import). Anything else goes into the recipe's notes under "Ingrediënten zonder product",
with the agent's reason for the suggestion, the cooking time and the source, so nothing is lost
and nothing lands on a wrong product. Mealie's import can afford a looser guess because the reader
confirms it; this one is saved without asking.

**Whether a suggestion is planned is derived, not stored.** The report shows, per recipe, the
listr recipe its page became and the days it's planned on since the report ran, looked up by
`source_url` on every read. Deleting the recipe or clearing the day in listr shows in the report
straight away.

## Alternatives considered

- **The server fetches and parses the page** (schema.org Recipe JSON-LD, which all three sites
  publish): less for the agent to write, and photos for free. But it's an outbound fetch to a URL
  from untrusted input (SSRF, and parsing whatever comes back), from a server that so far only
  talks to services named in its config.
- **Only Dutch sites allowed:** the owner said "preferably". The brief prefers them and the import
  accepts any http(s) page.
- **Export the meal history so the agent knows what was eaten:** better variety, but it's the
  household's eating pattern going to GitHub. Its own last few reports are enough to avoid repeats;
  this can be revisited if the owner wants it.
- **Plan the five recipes on fixed days automatically**, like the gym plan (ADR 0046): the owner
  wants to choose, and some weeks have leftovers or eating out planned already.
- **A new verdict for suggestions:** the existing three are enough. The brief uses `watch` for a
  suggestion, and the recipe card shows no verdict chip.

## Consequences

- One report a week from `home-chef`, flagged Watch, with five recipes to pick from.
- A planned suggestion is an ordinary listr recipe afterwards: edit it, add the missing products,
  add it to a shopping list or a Picnic cart as usual. Its page shows a "Bron" link.
- An ingredient the catalog doesn't know needs adding by hand once; the recipe's notes list them.
- The recipe has no photo: the server doesn't fetch one, and one can be added in listr.
