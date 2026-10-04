# 11. listr: Picnic integration — cart push and recipe import

## Status

Accepted

## Context

listr roadmap item 1 asks for two things against Picnic (Dutch grocery delivery): pushing a
listr shopping list into the user's real Picnic cart, and importing a Picnic recipe's
ingredients and instructions into a real listr recipe. Built as two phases on the same
foundation — the cart push first, then recipe import once that connection/session plumbing was
proven live.

Picnic has no official public API. Every option is a reverse-engineered wrapper around Picnic's
private Android app API: `picnic-api` (npm, JavaScript) and `python-picnic-api` (PyPI). Neither
cleanly covers what this feature needs — `python-picnic-api` has no 2FA support at all (many
Picnic accounts have 2FA on) and no recipe endpoints for the later phase; `picnic-api` has both,
but it's JavaScript, and this backend is Python/FastAPI throughout with no other runtime Node
dependency.

## Decisions

**A small hand-rolled Python client (`app/services/picnic_provider.py`) over either existing
package.** It implements only the handful of endpoints actually needed — login+2FA, product
search, add-to-cart — against the same private endpoints `picnic-api` documents in the open, the
same way `YFinanceProvider`/`YFinanceFundamentalsProvider` already wrap other external,
semi-documented data sources in this codebase rather than pulling in a third-party client for
them. This keeps the whole feature in one language, avoids Node becoming a backend runtime
dependency (today it's a frontend build-time tool only), and means fixing an API change is a
change to code this app already owns.

**The Picnic account's email/password stay environment-only** (`GAINR_PICNIC_EMAIL`/
`GAINR_PICNIC_PASSWORD`), the same pattern `GAINR_LISTR_ICS_TOKEN` already uses — never in git,
never sent to the frontend. Only the resulting session key is persisted, in a new single-row
`picnic_session` table (one Picnic account for this single-user app). A 401/403 from any Picnic
call clears that row and surfaces as "not connected", never a silent failure or a blind retry
against an account that might be rate-limiting or flagging the request.

**Every push adds a product at count 1, never a computed quantity.** Picnic's cart holds a count
of a specific product, not a weight or volume — a listr line like "500 gram bloem" can't be
mechanically turned into "how many bags of flour" without guessing a conversion, and this
codebase already refuses to do that (`listr_list_service.add_ingredients_to_list`'s comment on
never guessing a unit conversion when merging list lines). Pushing means "put this product in the
cart"; the user adjusts the count in Picnic's own app, the same as they would if they'd added it
there themselves.

**Product mapping lives on `ListrItem`** (`picnic_product_id`/`picnic_product_name`, both
nullable), set once via a dedicated `PUT /items/{id}/picnic-mapping` endpoint — a deliberate
search-and-confirm action, not a field folded into the item's general edit form. A list line
with no mapping yet is reported back by the push endpoint rather than silently skipped, so the
UI can prompt for one inline.

**Recipe import reads Picnic's undocumented `selling-group-details-page` instructions tab, not
the structured ingredients endpoint the community wrapper exposes.** Confirmed by probing a real
recipe: the structured endpoint gives a Picnic product id per ingredient but only a *selling-unit
count* (e.g. `1`), never the real-world quantity+unit a listr ingredient line actually needs;
the plain-markdown instructions tab has the opposite trade-off — clean `**name** quantity unit`
lines and the full step-by-step method, but no product id. Getting both would mean also parsing
per-tile product ids that only exist inside minified click-handler JS expressions elsewhere on
the page — real, but meaningfully more fragile than parsing plain text. **No Picnic-product
auto-mapping on import**, as a result: an imported ingredient that becomes a new `ListrItem`
gets mapped to a Picnic product the same one-time way as any other item, the first time it's
actually pushed to a cart.

**Recipe discovery is the account's Picnic "cookbook" (saved, self-created, and Picnic's own
weekly featured recipes), not a keyword search** — Picnic's private API has no recipe search
endpoint at all, only this listing.

**An ingredient that doesn't already match an existing catalog item by name requires picking a
category in a review step before import**, one dropdown per new ingredient, matching the same
one-pick-per-new-item convention `AddItemCombobox`'s inline "add a product" flow already uses.
No generic "misc" catch-all category was added to the seeded 12 — Picnic's naming
("Kipdijfilets", "Basmatirijst") often won't match this catalog's existing entries closely enough
to guess a category safely.

**A markdown parsing quirk worth naming**: instructions use single `# heading` lines per step
(`MarkdownLite.tsx` only recognizes one `#`, not `##`) — caught by screenshotting an actual
imported recipe, not by reading the renderer's code first.

## Alternatives considered

- **Use `python-picnic-api` for cart/search and hand-roll only the (later) recipe piece**: splits
  the Picnic surface across two different approaches for no real benefit, and still leaves the
  2FA gap for accounts that have it enabled.
- **Bridge to the npm `picnic-api` package via a Node subprocess**: less endpoint work up front,
  but makes Node a runtime dependency of a Python backend for the first time and adds a
  cross-language subprocess boundary to debug. Rejected in favor of staying in one language.
- **Convert a listr quantity/unit into a Picnic count automatically** (e.g. guessing "500 gram"
  means "1 bag" for a specific mapped product): would need a per-mapping conversion factor with
  no reliable source of truth, and silently wrong grocery counts are worse than the user
  adjusting a count themselves in an app they already use for checkout anyway.
- **Also parse per-ingredient Picnic product ids on import**, so a newly created catalog item
  arrives pre-mapped for pushing: rejected for now because those ids only exist inside minified
  click-handler JS expressions in a different page section, not plain fields — meaningfully more
  fragile than the plain-text instructions tab for a benefit (skipping one later search-and-pick)
  that's already a low-friction, one-time step.
- **Bucket every unmatched ingredient into one chosen category for the whole import** instead of
  one pick per ingredient: faster, but a single recipe's ingredients span several real
  categories (meat, produce, spices), so this would leave most of them wrong until manually
  fixed later in Producten anyway.

## Consequences

- Using this at all rests on an undocumented, unofficial API — Picnic could change it without
  notice, and there's a small, accepted risk of unusual automated activity getting an account
  flagged. Used personally and infrequently, matching how every other project built on these
  same reverse-engineered wrappers already operates.
- A listr catalog item only pushes cleanly to Picnic once it's been mapped once; a brand-new
  item added to a list still needs that one-time search-and-confirm step before its first push.
  An imported recipe's new ingredients are no exception — import doesn't pre-map them either.
- The Picnic session key can expire or be revoked outside this app entirely (e.g. logging out of
  the Picnic app elsewhere) — every call path treats that as "reconnect", not an error to chase.
- The instructions-tab parser depends on Picnic's current Dutch wording ("Stap N", "Tip",
  "Notitie", "Bereidingswijze", "Uit eigen keuken") — consistent with listr already being
  Dutch-only with no i18n layer, but it means a Picnic copy change could silently misparse a step
  as an ingredient or vice versa. Verified end-to-end against a live recipe before shipping;
  unrecognized lines are kept as freeform content rather than dropped, so the worst case is an
  odd-looking entry the reader can fix by hand, not lost data.

## Addendum (October 2026): order history

listr now also reads the account's **delivery history** (`POST /deliveries/summary` with
`["COMPLETED"]`, the same endpoint `picnic-api` documents as `getDeliveries`) to show what was
spent on Picnic over the last 12 months (`/listr/bestellingen`).

- **Read live, stored nowhere.** One call returns the whole history (back to the account's first
  order), so there's nothing to sync or cache; the page asks Picnic each visit. The session and
  2FA handling are the existing ones, including clearing a rejected session and offering to
  reconnect.
- **The amount is each completed order's `total_price`:** the groceries after discounts,
  excluding deposit. Picnic charges deposit (`checkout_total_price` = `total_price` +
  `total_deposit`) and refunds it later through returned containers, so including it would add
  money that mostly comes back. Cancelled orders don't count; a delivery's date is its actual
  drop-off time, falling back to the slot start.
- **A rolling 12 months, bucketed by calendar month.** The total covers exactly the last 12
  months whatever day it's asked; the monthly chart groups those deliveries by calendar month,
  so the oldest and the current month are partial, and are drawn lighter with a note saying so.
- Still read-only toward Picnic: nothing here places, changes or cancels an order.
