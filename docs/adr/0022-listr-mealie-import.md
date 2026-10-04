# 22. listr imports recipes from a self-hosted Mealie

## Status

Accepted

## Context

The user keeps recipes in [Mealie](https://mealie.io), a self-hosted recipe manager running as its
own Proxmox container on the home LAN, and wants them in listr's Recepten — where a recipe's
ingredients feed shopping lists and the weekplanner. That makes Mealie a new external data
provider, next to yfinance and Picnic.

Two models don't line up. listr's recipe lines must reference a catalog product (`ListrItem`, via
`grocery_item_id`, never free text — ADR 0005/0006), with a quantity and a free-text unit. Mealie
ingredients are either parsed — a *food* ("ei"), a unit ("stuks") and a quantity — or unparsed
single lines ("snufje zout"). Mealie names foods in the singular, while the catalog was seeded as
shopping items ("Eieren", "Aardappelen", "Tomaten"), so an exact name match catches only part of a
real recipe: on the user's first three recipes, 13 of the foods matched nothing.

Before building, the user chose: (1) an unmatched food is asked about once and the answer is
remembered, rather than auto-creating products (which would put "Ei" next to "Eieren"); (2) Mealie
is the source of truth — re-importing overwrites a recipe changed there, rather than importing
each recipe only once; (3) the import runs from a button on Recepten, not on a schedule.

## Decisions

**Adapter + service, the Picnic split.** `mealie_provider.py` only talks HTTP to Mealie's REST API
(list recipes, get one recipe) and turns its JSON into plain dataclasses; `listr_mealie_service.py`
decides what that means for listr's tables. Same layering as `picnic_provider.py` /
`listr_picnic_service.py`, so a different recipe source later (Tandoor, say) is another provider,
not a rewrite.

**Mealie's JSON is sanitised at the boundary.** Every field is type-checked, trimmed and
length-capped in the provider (a name is a string of at most 200 characters, a quantity a positive
finite `Decimal` rounded to the catalog's 3 decimals — never a float — anything else becomes "no
quantity"). The service never sees a raw response. The recipe slug is percent-encoded into the URL
path so it can't address a different endpoint, redirects aren't followed (the bearer token only
ever goes to the configured host), and the host itself comes from `GAINR_MEALIE_URL` in the
environment, never from a request — there is no way to point the backend at another server from
the browser. Error messages the API returns name what went wrong ("Mealie weigerde de
API-sleutel") and never include the key.

**Idempotent by Mealie id; "changed" by Mealie's own stamp.** `grecipe_recipes.mealie_id` (unique)
ties a listr recipe to its Mealie original, so a re-import updates the row instead of adding a
duplicate; `mealie_updated_at` stores Mealie's `updatedAt` exactly as sent and is compared as an
opaque string — no timezone parsing to get wrong. A recipe whose stamp is unchanged isn't even
fetched past the list call. A missing stamp counts as changed (re-import rather than go stale).

**Mealie wins on update.** A changed recipe's title, servings, instructions, notes, categories and
its whole ingredient list are replaced; `is_archived` and weekplanner/cook history are untouched
(they reference the recipe row, which keeps its id). A recipe deleted in Mealie is left in listr —
deleting the reader's cooking history because a source recipe disappeared is the wrong default.
The recipe page says it came from Mealie, since an edit made in listr won't survive the next
import.

**Food → product resolution: remembered pick, then exact name, then ask.** A new
`grecipe_mealie_foods` table (Mealie food id → `ListrItem`) records what the reader chose, the
same "confirm once, remembered" idea as `ListrItem.picnic_product_id` — but a table rather than a
column on the item, because several Mealie foods can mean one product ("ei", "eieren",
"eidooier"). Failing that, a case-insensitive exact name match connects silently. Anything left is
returned by the preview with a *suggestion* — Dutch plural forms first (+en, +s, a doubled vowel
closed up as in tomaat→tomaten and boon→bonen, ei→eieren), then a catalog name containing the food
as a word or word-prefix ("peterselie" → "Platte peterselie", "kerrie" → "Kerriepoeder"). A
suggestion is only pre-selected in the dialog; nothing is stored until the reader imports with it,
and a miss means no suggestion rather than a loose one ("ui" deliberately doesn't suggest
"Druiven"). New products are created through the existing search-or-add combobox, so they get a
real category and unit, as everywhere else.

**Nothing is dropped.** Things listr has no field for go into the recipe's notes: Mealie's
description and notes, per-ingredient notes ("Bladerdeeg: uit de vriezer"), and unparsed ingredient
lines, which can't become catalog-backed recipe lines. Steps become one numbered markdown list with
a step's title as a heading, the subset MarkdownLite renders. Mealie's categories and tags become
listr recipe categories, matched case-insensitively and created when missing.

**Import re-fetches; it doesn't trust the preview.** `POST /listr/mealie/import` fetches from
Mealie again, the same as the Picnic import, and refuses with a 409 listing the remaining foods
if anything is still unresolved — for example a recipe added in Mealie after the preview. The
picks sent with that request are kept, so the dialog only asks about what's new.

## Alternatives considered

- **Auto-create unmatched products**: no questions, but catalog duplicates ("Ei" beside
  "Eieren") that then split shopping-list merging and inventory. Rejected by the user.
- **Import once, never update**: simpler, but Mealie is where the user edits recipes; a stale
  listr copy would quietly drift.
- **Scheduled sync**: unmatched foods would have nowhere to be asked about until the reader opened
  Recepten anyway, so the button is the honest trigger.
- **A mapping column on `ListrItem`** (like `picnic_product_id`): can only hold one Mealie food
  per product, but several foods legitimately mean the same product.

## Consequences

- Requires `GAINR_MEALIE_URL` and `GAINR_MEALIE_API_KEY` in the environment (locally
  `backend/.env`, on homecloud the service environment). Without them the button is hidden and
  the endpoints answer 409 "not configured".
- The Mealie container gets its address by DHCP; if it moves, `GAINR_MEALIE_URL` needs updating
  (or give it a DHCP reservation).
- Editing an imported recipe in listr is allowed but temporary by design; the UI says so.
