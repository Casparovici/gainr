# 10. gripr: inline rename, a balance-source icon, and a fixed bank-logo catalog

## Status

Accepted

## Context

Three related gripr roadmap items, all about the Accounts/Categories tiles: category names
couldn't be edited at all (only set at creation); account names were always an open text input
rather than the read-only-with-pencil pattern already established for editing a budget amount;
and account tiles showed "Manual balance"/"From transactions" as text, with no way to mark an
account with its bank/broker's own icon.

## Decisions

**A shared `InlineEditText` component**, extracted from the read-only-until-clicked, pencil-icon,
save-on-blur/Enter pattern `BudgetCell` in `Budget.tsx` already established for editing a
budget amount — applied here to a plain name instead of a decimal. Used in three places: an
account's name (`AccountDetailDialog.tsx`, replacing what used to be an always-open input with
a separate "Save" button shared with the Type field) and a category's name, both top-level and
subcategory (`Categories.tsx`'s `CategoryTile`). `GriprCategoryUpdate` gained a `name` field to
support the latter — categories couldn't be renamed via the API at all before this.

**One known side effect, left as-is**: `categoryIcon()` (`utils/categoryIcons.tsx`) looks up a
category's icon by its exact name string. Renaming a category away from a name in that map
falls back to the generic `Tag` icon — an existing, name-keyed lookup this change now makes
reachable through renaming rather than only at creation. Not fixed here (out of scope for what
was asked), but worth knowing: a themed icon can be "lost" by a rename.

**A balance-source icon (`Hand` for manual, `Calculator` for transaction-derived) replaces the
"Manual balance"/"From transactions" text** on the account tile footer — same reasoning as the
row-level Edit/Delete icon conversion earlier in this project: the tile is small, and an icon
with a `title` tooltip carries the same information in less space.

**Bank/broker icons are a small, fixed, hand-picked catalog** (`GRIPR_BANKS` in
`gripr_bank_logo_service.py` — ING, Trading 212, Trade Republic, Revolut today), not a
general "any brand" lookup like gainr's asset logos. A gripr account isn't a ticker with a
symbol to resolve a brand from, so `WebsiteLogoProvider` (`logo_provider.py`) was refactored to
expose a new public `get_logo_for_domain(domain)` alongside its existing symbol/name-based
`get_logo()` — both share the same fetch-measure-pick-the-largest-icon machinery, but the new
entry point skips the brand-resolution step entirely, since the caller already knows exactly
which domain to ask (`ing.nl`, `trading212.com`, ...). Fetched once and cached forever in a new
`gripr_bank_logos` table (mirrors `asset_logos` exactly: bytes stored locally, served from
`GET /api/gripr/bank-logos/{key}/logo` with the same ETag/no-cache contract
`GET /api/assets/{id}/logo` already uses, never pointed at from a third-party CDN). A picker
(`BankLogoPicker.tsx`, mirroring `ColorPicker.tsx`'s popover interaction) sits top-right on each
account tile; `GriprAccount.bank_logo_key` is validated against the catalog in the router.

**Trade Republic and Revolut resolve from a local file, not the network.** Neither discovers a
usable icon through `WebsiteLogoProvider`: Trade Republic's only discoverable icon
(`/favicon.ico`) is ~280KB, over `MAX_LOGO_BYTES`'s 256KB cap; Revolut's site returns HTTP 403
to a plain request (bot-protected). The user supplied both marks directly. `LOCAL_OVERRIDES` in
`gripr_bank_logo_service.py` maps those two keys to a PNG under
`backend/app/static/gripr_bank_logos/`, checked before the network path (and skipping it
entirely for these two) — the same "a known-good source beats discovery" idea
`logo_provider.ICON_URL_OVERRIDES` already uses for VanEck, just a local file instead of a URL
since these weren't found anywhere, they were given. Still funneled through the normal
fetch-once-cache-forever path (`gripr_bank_logo_repo.upsert_logo`), so the serving endpoint's
ETag/no-cache contract needs no special case for them; `source_url` records `local:<filename>`
rather than a real fetch URL, so it's visibly distinguishable from a genuinely fetched logo.

## A bug found and fixed along the way

`BankLogo.tsx`'s first version copied `AssetLogo.tsx`'s "hide until loaded" idea but used
`display: none` instead of `AssetLogo`'s `opacity-0`, and kept `loading="lazy"` on the `<img>`.
An image inside a `display: none` ancestor never has a layout box, so the browser's lazy-load
intersection observer never considers it "near the viewport" — it never loads, so `display:
none` never clears: a permanent deadlock (confirmed live — the fetched logo returned 200 with
valid bytes over the network, but the `<img>`'s `onload` never fired). Fixed by dropping
`loading="lazy"` — a handful of small, already-cached-after-first-fetch icons per page cost
nothing to load eagerly, unlike `AssetLogo`'s use case (potentially many logos in a scrollable
holdings table, where lazy loading earns its keep).

## Alternatives considered

- **A general "any bank" logo system, symbol/name-resolved like gainr's assets**: no ticker
  exists for a bank account to resolve a brand from, and the four brands here are a small,
  stable, hand-picked set — a fixed catalog is simpler and matches what was actually asked for
  ("give me the ability to choose an icon from a list of bank accounts I have").
- **Storing the bank's brand color, not fetching a real logo**: would sidestep the two brands
  whose icon isn't fetchable, but a plain color swatch is a materially worse result than a real
  logo for the two that do resolve, for the sake of parity with two that don't.

## Consequences

- Renaming a category via the new inline field can silently drop its themed icon (see above) —
  a small UX rough edge, not addressed here.
- The bank-logo catalog is code, not data — adding a fifth bank means editing `GRIPR_BANKS` and
  redeploying, not a database migration or an in-app admin flow. Appropriate at four entries;
  reconsider if the list grows meaningfully.
- The two provided PNGs (`backend/app/static/gripr_bank_logos/`) are committed to the repo like
  any other source asset — if either bank's icon is later found through normal discovery (a
  size-cap increase, the bot-block lifting), removing its `LOCAL_OVERRIDES` entry reverts to
  fetching it live, no schema change needed either way.
