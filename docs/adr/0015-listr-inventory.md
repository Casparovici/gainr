# 15. listr: inventory as a per-item status, not a counted stock ledger

## Status

Accepted

## Context

listr roadmap #1 asked for an inventory tab: keep track of what's at home, and when something
gets below a threshold, offer to add it to a shopping list. The obvious shape -- "I have N of
this" -- runs straight into the same problem [ADR 0005](0005-listr-module.md) already refused
to solve for merging list lines: a real quantity needs a real unit, and this app already knows
Dutch grocery units don't reduce to one settled unit per product ("gram" for baking flour,
"stuk" for the same flour once it's a bag on a list, "liter" vs "pak" for milk). Deciding how
precise inventory tracking should be, and whether it should move on its own when a list is
checked off or a recipe is cooked, were genuine open questions, not settled by anything already
in the codebase.

## Decisions

**Inventory is a three-state status per catalog item (`in_stock` / `low` / `out`), not a
counted quantity.** The user picked this explicitly over exact quantity tracking: no unit to
settle on a get up front, no conversion problem when a recipe or list uses a different unit
than the one an item was inventoried in. "Below threshold" isn't a number to configure -- it's
just the reader marking something `low` or `out` themselves, the same way `is_cooked` on a meal
plan entry is a manual confirmation, not an inference.

**Tracking is opt-in per catalog item**, via a nullable `ListrItem.inventory_status` column
(`NULL` = not tracked), not a separate table and not every catalog item defaulting into the
inventory. Most of the ~220-item seeded catalog isn't something any one household keeps
stocked; starting a new item's tracking reuses `AddItemCombobox` (get-or-create by name, same
as adding to a list or a recipe), and setting a status to `None` both clears it and stops
tracking -- there's no separate "untracked but still has a remembered status" state to reason
about.

**Nothing moves the status automatically.** Marking a weekplanner day "Ik heb dit gekookt"
doesn't deplete inventory, and checking off a grocery-list line (or a successful Picnic push)
doesn't restock it. The user chose manual-only for both, explicitly, over the fuller
auto-adjusting version -- which would only have worked cleanly when a recipe ingredient's or
list line's unit happened to match whatever unit the inventory status was implicitly tracked
in, the same unit-mismatch problem status-only tracking exists to sidestep in the first place.
The reader updates stock by hand when they notice something's running low, and flips it back to
`in_stock` once groceries are unpacked -- the same closed loop `is_checked` already uses on a
list line, just one level up.

**"Add to shopping list" is a bulk action over every `low`/`out` item**
(`POST /api/listr/inventory/add-to-list`), the bulk sibling of the recipe's and weekplanner's
own add-to-list endpoints, reusing the same `list_id`-or-`new_list_name` shape and
`add_ingredients_to_list` merge logic. Every item lands on the list at quantity 1 of its own
`default_unit` -- there's no computed quantity here either, matching the Picnic push's "always
count 1, the reader adjusts it" convention from [ADR 0011](0011-listr-picnic-integration.md).
Adding to a list doesn't touch the item's inventory status (manual-only, as above); the reader
clears it back to `in_stock` themselves once it's actually restocked.

## Alternatives considered

- **Exact quantity + unit per inventory item** (a `quantity`/`unit` pair, mirroring list
  lines): more useful in principle (real par levels, "I have exactly 2 left") but requires
  every tracked item to commit to one unit, which breaks the moment a recipe or list line uses
  a different one for the same item -- exactly the guess this app already refuses to make.
  Rejected in favor of a status.
- **Auto-deplete inventory when a weekplanner day is marked cooked**: only works given exact
  quantities, and only for ingredients whose unit happens to match the inventory item's own --
  a mismatch would need a fallback (skip silently, or flag for manual review) that adds real
  complexity for a feature that isn't asked for. Rejected; cooking never touches inventory.
- **Auto-restock inventory when a list line is checked off or pushed to Picnic**: the mirror
  image of the above, with the same unit-mismatch problem. Rejected for the same reason --
  buying never auto-adjusts inventory.
- **A separate `ListrInventory` join table** instead of a nullable column on `ListrItem`:
  would support richer per-tracking metadata later, but this is genuinely 1:1 optional data on
  an item, the same shape `picnic_product_id`/`picnic_product_name` already use directly on
  `ListrItem` -- a second table would just be a join for no benefit today.

## Consequences

- "Below threshold" has no configurable number anywhere -- it's entirely the reader's own
  judgment call, expressed by clicking a status. A future per-item numeric par level would be
  a bigger, separate feature (real quantities, real units, real conversion questions), not an
  extension of this one.
- Inventory and the rest of listr never disagree with each other because they never touch --
  cooking a planned recipe, checking off a list line, and pushing to Picnic all leave every
  item's `inventory_status` exactly as it was. The tab is a hand-maintained "what to restock"
  list, not a stock ledger kept in sync by the app.
- An item's inventory status survives archiving the item's list lines or recipes it appears in
  (nothing there references it), but archiving the `ListrItem` itself hides it from
  `GET /api/listr/inventory` the same way archiving hides it from Producten -- consistent, not
  a special case.

## Addendum: a manual +/- count, without reopening the unit-guessing question

The user asked for a counter with +/- buttons on each Voorraad item. This looked, at first
glance, like reopening the "exact quantity + unit" option this ADR rejected above -- but a bare
tally ("I have 3 of these") isn't that: it carries no unit, and nothing ever merges or converts
it against a list line's or recipe ingredient's own quantity. The unit-guessing problem only
exists where two different quantities need reconciling against each other; a number a person
increments by hand has nothing to reconcile.

`ListrItem.inventory_count` is a plain non-negative integer, default 0, adjusted via
`POST /items/{id}/inventory/count` with a **delta** (`{"delta": 1}` / `{"delta": -1}`), not an
absolute value -- the button click itself is the whole payload, and the server clamps the
result at 0 rather than trusting the client not to send one that would go negative. It's
present on every `ListrItem` (not nullable/opt-in like `inventory_status`), but only shown in
the Voorraad UI, where it sits next to the status dots -- purely a manual number the reader
maintains, same as the status: nothing (cooking, checking off a list, a Picnic push) ever
touches it, and it has no bearing on the "add to shopping list" bulk action, which still adds a
flat quantity of 1 per item, unrelated to how many are already on hand.

## Addendum: status stops being manual -- a minimum count now derives it

The count above immediately made the status dots redundant with something more useful: a
per-item reorder point. The user specified the rule directly -- at or above the minimum is
in_stock; below it (but more than one left) is low; one or none left is out, regardless of the
minimum. This supersedes the "status dots are a manual click, not computed" decision earlier in
this ADR -- once a count exists, computing status from it is strictly more informative than a
second independent manual field the reader has to keep in sync with the count by hand.

`ListrItem.inventory_minimum` (int, default 0) is the reorder point. `_compute_inventory_status`
(a pure function in `listr.py`, not a service -- it's a three-line rule, not a domain to give its
own module) applies exactly the stated precedence:

```python
if count <= 1: return "out"      # the floor -- always wins, whatever the minimum is
if count < minimum: return "low"
return "in_stock"
```

`inventory_status` is now computed, never client-set. `PUT /items/{id}/inventory` no longer
takes a status -- it takes `{"tracked": bool}`, and starting tracking computes the initial
status from whatever count/minimum the item already carries (usually 0/0, reading as `out`
under the rule above). `PUT /items/{id}/inventory/minimum` sets the reorder point and
recomputes status if the item is currently tracked; `POST .../inventory/count`'s existing delta
endpoint does the same recomputation after applying the delta. Untracking still only clears
`inventory_status` -- count and minimum are left as they are, so re-tracking later resumes
rather than resetting (unchanged from the first addendum).

The status dots in the Voorraad UI are now read-only -- a single coloured dot per item next to
the count and a small minimum-count input, instead of three clickable options. A migration
(`e5f8b3d1a9c7`) recomputes every already-tracked item's status once against the new rule on
upgrade, since a manually-set value from before this change might disagree with it (every item's
count was freshly added and still 0 for everyone at the point this landed, so in practice this
mostly just flipped existing tracked items to `out` until real counts are entered).

### Alternatives considered

- **Keep status manual, add minimum as a separate hint only** (e.g. a badge saying "below your
  minimum" next to an independently-clickable status): rejected -- two sources of truth for the
  same concept invites them drifting apart, and the reader already has to enter the count; making
  them also click a matching status is duplicate work for the same information.
- **A configurable amber/red threshold pair instead of a fixed "1 or 0 is always out" floor**:
  rejected -- the user's own rule already hard-codes the floor at 1, and a fully configurable
  version would be solving a problem ("what if someone wants their floor at 2?") nobody asked for.

## Addendum: the minimum field itself didn't save -- a typed number, not a stepper, was the bug

The first version of the minimum input (a free-text `<input type="number">`, committed on blur)
shipped, and the user reported it losing their entered values -- confirmed for real by checking
homecloud's live request logs directly: for the items they'd just added, `POST .../count` and
`PUT .../inventory` (tracking) calls were landing, but not one `PUT .../inventory/minimum` ever
reached the server. The first fix attempt (making the input's label visible) addressed a real
but secondary problem -- the field was genuinely easy to miss -- without touching the actual
bug, and the user correctly called that out when it still didn't work.

The real cause: the row held the typed value in local component state (`minimumDraft`) synced
back to the server value with `useEffect(() => setMinimumDraft(...), [item.inventory_minimum])`.
Every mutation in Voorraad -- adjusting a *different* item's count, tracking a *different* new
item -- invalidates the same `["listr-inventory"]` query and refetches the whole list. If that
refetch landed while the reader was still mid-edit (a very real case restocking several freezer
items in one sitting: add item, bump its count, type its minimum, move to the next item), the
effect fired on the *unrelated* refetch and silently overwrote the in-progress draft back to the
server's still-stale value -- before blur ever had a chance to send it. No error, no visible
failure; the number just reverted next time that row re-rendered, or on the next real reload if
the reader had already navigated away by then.

**Fix: no local draft state at all.** The minimum field is now a +/- stepper --
`POST /items/{id}/inventory/minimum` with a `delta`, identical in shape to
`POST /items/{id}/inventory/count` (`ListrInventoryMinimumDeltaIn` replacing the old
`ListrInventoryMinimumIn`, endpoint changed PUT→POST to match). This isn't a workaround for the
bug above so much as removing the class of bug entirely: there's nothing to hold in a
`useState`, nothing for an unrelated refetch to stomp, and nothing waiting on a blur event that
might not fire the way it's expected to (typing on a phone, tapping straight to the next
control) -- every tap is its own immediate, self-contained request, the same shape the count
buttons already used and had been reliably persisting the whole time. Both `Inventory.tsx`
steppers (count and minimum) now share one `Stepper` component.

### Alternatives considered

- **Guard the sync effect with an `isFocused` ref instead of removing the draft state**: would
  have fixed the specific "wiped mid-edit" case, but leaves the same class of bug available to
  the next person who adds a text-entry field to this list, and doesn't address blur not firing
  reliably on every input method. Removing draft state entirely closes the bug class instead of
  patching one instance of it.
- **Keep a text input for minimum, just commit on every keystroke instead of on blur**: still
  needs draft state and still races the same refetch-triggered effect; only shrinks the window,
  doesn't close it.

## Addendum: the "1 or 0 is always out" floor overrode a minimum of 1 itself

The original design (and this ADR's own alternatives-considered section) treated the floor at
1 as a deliberate, non-negotiable part of the user's rule. In practice it wasn't: several
freezer items are legitimately kept at a minimum of 1 (a single spare pizza, one bag of
peas), and for those the floor meant `count == minimum == 1` still rendered `out` -- a
fully-restocked item permanently flagged as needing restocking, with no way to ever clear it
short of raising the minimum to 2 (which changes what the number means, not just its color).

Reported live: four Diepvries items sitting at `count=1, minimum=1` all showing red, which
reads as a bug regardless of the floor's original intent -- "I have exactly what I said I need"
should never be the same color as "I have none."

**Fix:** the floor is now 0, not 1 -- `_compute_inventory_status` returns `out` only at
`count == 0`; `count == 1` is judged against `minimum` like any other value, so `minimum=1` at
`count=1` is `in_stock`. A one-off data migration
(`e2c9a4f6b8d3_recompute_listr_inventory_status_floor.py`) recomputed `inventory_status` for
every already-tracked row against the new rule, the same way the minimum column's own migration
backfilled once when that rule first landed.

### Alternatives considered

- **Leave the floor at 1, tell the user to set minimum to 2 for single-unit items**: rejected --
  it repurposes "minimum" to mean "minimum, plus 1 for the floor's sake," which is a worse
  mental model than removing the special case, and would need re-explaining every time a new
  single-unit item gets tracked.
- **Make the floor configurable per item**: rejected for the same reason the original ADR
  rejected it -- nobody asked for a per-item floor, they asked for `count >= minimum` to mean
  `in_stock` even when minimum is 1.

## Addendum: the dot lagged behind the number -- the optimistic update never recomputed status

Even after the previous addendum fixed the minimum field's save reliability, the user reported
the status dot still showing the wrong colour after adjusting a count/minimum -- specifically an
item at count 2, minimum 1, showing red (`out`) instead of green (`in_stock`). Checked directly
against homecloud's live database rather than assumed: every currently-tracked item's stored
`inventory_status` was in fact correct for its stored count/minimum, so this wasn't a repeat of
the previous addendum's server-side save bug -- the server-computed value was right all along.

The real cause was in the Stepper's optimistic update (`Inventory.tsx`'s `onMutate` for both
count and minimum mutations): it patched only the field the button changed (`inventory_count` or
`inventory_minimum`) into the React Query cache, immediately, for a snappy click -- but left
`inventory_status` untouched. The dot reads `inventory_status` directly, so it kept showing
whatever status was cached *before* the click, for the entire round-trip to homecloud over
Tailscale, only correcting itself once `onSettled`'s `invalidateQueries` refetch actually landed.
On a fast local network that's invisible; on this app's real deployment it reads as "the colour
didn't update" -- the same complaint as before, but this time in the +/- stepper's optimistic
path rather than in the old text-field's save path.

**Fix:** the optimistic patch now also recomputes `inventory_status`, via a client-side
`computeInventoryStatus` that mirrors `_compute_inventory_status` exactly (same three-line rule,
including the previous addendum's corrected floor, kept in sync by inspection since there's no
shared package between the two languages). It only recomputes when the item is currently tracked
(`inventory_status` isn't already `null`), matching the server's own
`if item.inventory_status is not None` guard, so an untracked item's dot -- which doesn't exist --
isn't accidentally given one. Verified against a seeded item at count 0, minimum 1, status `out`:
clicking `+` now flips the dot straight to `in_stock` within the same render pass, confirmed by
reading the DOM before the mocked network call was allowed to resolve in the new regression test,
and live in a browser against a real (non-mocked) local backend.

### Alternatives considered

- **Skip the local recompute and just make `onSettled` fire faster / show a loading state on the
  dot while in flight**: doesn't fix the actual mismatch, just makes the stale-colour window
  shorter or more honestly labelled. The dot briefly lying about the item's status is the bug;
  recomputing it locally removes the window entirely instead of shrinking or disclosing it.
- **Derive the dot's colour from `count`/`minimum` directly in the component, dropping
  `inventory_status` from the read path entirely**: would also fix this, and removes the
  duplicated formula this addendum's fix now requires. Not taken here because `inventory_status`
  being `null` vs. a real value is also how the UI knows whether an item is tracked at all (the
  dot vs. no dot), which the raw count/minimum pair can't distinguish from "tracked, count 0,
  minimum 0" -- keeping the server's `inventory_status` as the read path and just correcting the
  optimistic patch was the smaller, more targeted fix.

## Addendum (October 2026): Picnic deliveries restock

When delivery processing is switched on (ADR 0027), a delivered Picnic order adds each product's
number of selling units to the count of every *tracked* catalog item linked to it. It's the one
automatic change to the count; untracked items stay untouched, and the count/status rule moved
into `listr_inventory_service` so the +/- buttons and a delivery apply the same one.
