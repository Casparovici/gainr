# 12. gardnr: a fourth module, with a hand-drawn map instead of a photo

## Status

Accepted

## Context

Gardnr is the app's fourth module — a garden catalog and care journal alongside gainr, gripr, and
listr. The user asked for: a register of plants/trees, a log of care actions (water, prune,
trim, ...) with a record of when each was done, and "an interactive design of my garden (cartoon
like)" where hovering a plant shows what it is and its latest/upcoming actions. Before building,
the user was asked four clarifying questions and answered: build the map as an in-app shape
editor rather than a photo overlay; use a fixed action-type list plus "Other" rather than free
text; support a recurring schedule per plant+action rather than manual reminders or no scheduling
at all; and support multiple distinct garden areas (front/back yard, etc.) from day one.

## Decisions

**Module boundary**: follows the exact `listr`/`gripr` precedent (ADR 0005) — `garden_*.py`
files alongside the existing routers/services/repositories/models/schemas, `frontend/src/pages/
gardnr/` + `components/gardnr/` + `api/gardnrClient.ts`/`gardnrTypes.ts`. No subpackage, no new
architectural pattern.

**The map is an in-app shape editor, not a photo with pins.** The user's own "cartoon like"
description, and the fact that no tool in this environment can generate bespoke artwork of a
real garden, ruled out photo-realism. `GardenZone` rows (rect/circle, percent-of-canvas x/y/
width/height, a colour) are purely decorative background shapes a user draws directly on the
map; `GardenPlant` markers are dropped on top of them by clicking the canvas. Percent-of-canvas
coordinates (`Numeric(5,2)`, 0–100) keep a layout resolution-independent, the same reasoning that
keeps every currency value a `Decimal`/`NUMERIC` rather than a float.

**A zone is decorative, not a container.** A plant marker's position is just an (x, y) pair on
the same canvas — there's no `zone_id` foreign key tying a plant to the bed it visually sits on.
Making that relationship real would need polygon containment math for every shape (a circle bed,
a rect path) for no actual feature benefit yet; nothing today needs to answer "which plants are
in this zone" as a query.

**`GardenArea` is a first-class, top-level entity**, not a tag on plants. Per the user's answer
(multiple distinct areas from day one), each area owns its own zones and plants and its own map;
`GardenArea` mirrors `ListrList`/`GriprAccount`'s "user-created top-level rows with a
`sort_order`, drag-to-reorder" shape (ADR pattern already proven twice).

**A care schedule's due date is computed, never stored** — no `next_due_date` column, unlike
gripr's `GriprRecurringTransaction`. gripr's recurring rule needs a persistent cursor because it
*books a real transaction* into the ledger and must not re-book the same occurrence twice. A
Gardnr schedule books nothing; it only ever answers "when is this due", which is fully determined
by the plant's own care-log history (`garden_care_service.next_due`: latest matching log's date,
or the schedule's own creation date if never logged, plus the interval). This is the same
derive-don't-store principle positions and cash already follow (`position_service.py`) — the
alternative (a stored cursor with a `generate_due`-style catch-up loop) would need to stay in
sync with a log a user edits/deletes by hand, which a pure computation doesn't have to worry
about.

**Action types are a closed Python enum plus a nullable `custom_label`** (`GardenActionType`:
water/prune/trim/fertilize/harvest/pest_control/other), the `TransactionType` pattern, not the
`GriprCategory` open-row pattern — the user asked for a fixed list with an "Other" escape hatch,
not user-defined categories.

**`ColorPicker` moved out of `components/gripr/`** into `components/` (shared). It was already
fully generic (a `trigger: ReactNode` wrapper around swatches, no gripr-specific logic) but lived
under gripr's folder from when it was gripr-only; Gardnr's zone colour needed the identical
component, and reaching into a sibling module's folder from a new module would have been the
wrong direction to compound. Its two gripr call sites were repointed, behaviour unchanged.

**Dragging is mouse-event only for v1** (`onMouseDown`/`onMouseMove`/`onMouseUp` with a
pixel-movement threshold to distinguish a drag from a click). Real touchscreens don't reliably
fire continuous synthetic `mousemove` for a touch-drag gesture the way they do for a simple tap,
so repositioning a zone or plant by dragging may not work on a phone; tapping to open a plant's
detail panel or a zone's edit popover still works through the browser's tap→mouse-event
compatibility shim. Full touch-event support (`touchstart`/`touchmove`/`touchend`) was left for
a follow-up rather than built speculatively.

## Alternatives considered

- **Photo + pinned hotspots**: closer to a literal "map of my actual garden", but needs the user
  to source and keep updating an image, and reads as annotated-photo rather than the
  "cartoon-like" look asked for. Left as a possible future addition alongside the shape editor,
  not instead of it.
- **A stored, advancing `next_due_date`** (gripr's approach): rejected — Gardnr's schedule doesn't
  book anything, so there is no "occurrence" to consume; computing fresh from the log every read
  can never drift out of sync with a log entry added or corrected after the fact.
- **Zones as a real container** (`plant.zone_id`): rejected for v1 — no feature yet needs it, and
  it would require shape-specific containment logic (rect vs. circle) to keep it meaningful as
  zones move.

## Consequences

- Every "due" and "overdue" figure is recomputed on every request from the full care-log history
  (`garden_care_service.next_due`/`soonest_due_action`), same performance shape as position
  derivation — fine at personal-garden scale, would need the same kind of cache gainr's
  performance series got (ADR 0001) if a plant's log ever grew large enough to matter.
- Moving a plant between zones, or a zone's shape changing, never needs a data migration on the
  plant side — there's no foreign key to update, only the two independent (x, y) pairs.
- Repositioning zones/plants by drag currently only works with a mouse; a phone user places a
  plant via the click-to-place flow (which does work, tap-to-click) but can't yet drag it to
  nudge its position afterward without touch-event handlers, a known gap for a follow-up.

## Addendum: touch dragging, care log photos, a cross-area Vandaag view, and a plant status flag

**Touch dragging** closes the gap above: `AreaMap.tsx`'s drag state machine now takes its
coordinates from either a mouse or a touch event through one `pointerPosition` helper, and the
canvas gets native (not React-synthetic) `touchmove`/`touchend` listeners, attached once and
reading the live drag through a ref rather than a closure. Two reasons this couldn't just be
`onTouchMove`/`onTouchEnd` JSX props: React attaches those passively by default, so
`preventDefault()` inside them silently does nothing and the page scrolls out from under a
drag; and a React prop re-renders (hence re-binds) on every state change, which would mean
re-attaching the listener on every single drag-position update instead of once per drag.

**Care log photos** are stored inline in `garden_care_logs` (`photo` bytes,
`photo_content_type`), not on disk, so they're automatically covered by the existing whole-
database backup story ([ADR 0013](0013-backup-strategy.md)) rather than needing one of their
own. Every upload is resized and re-encoded as JPEG server-side with Pillow (already a
dependency, via `logo_provider.py`) before storage — capped at 1600px on the longest side,
`exif_transpose`d so a phone photo's rotation survives being re-served as plain bytes with no
EXIF-aware viewer downstream. Attaching a photo is its own `PUT /logs/{id}/photo` (multipart)
action, separate from the log's own JSON create/update, the same "deliberate action, not a form
field" shape listr's Picnic product mapping already established.

**Vandaag** needed no new backend endpoint at all — `garden_care_service.is_overdue` already
means "due today or earlier" (`due_date <= today`), so filtering the existing
`GET /gardnr/plants` response (every plant, every area, already carrying `is_overdue`) to just
the overdue ones *is* "what needs doing across the whole garden today," grouped by the
`area_name` already on the wire. Its "Nu gedaan" button reuses the same `POST .../logs` endpoint
a normal care-log entry uses, just pre-filled with today's date and the due schedule's own
action type — a genuine shortcut, not a new code path.

**Plant status** (`GardenPlantStatus`: thriving/struggling/dead) deliberately does *not* follow
listr's `inventory_status` shape, even though it's visually the same three-dot pattern. listr's
status is nullable and opt-in, because most catalog items aren't something any household
stocks. A catalogued plant has no equivalent "not applicable" state — it's alive and fine
(`THRIVING`, the default) until you say otherwise — so this is a plain non-nullable enum column
on `GardenPlant`, not a tracked/untracked toggle. Manual only, same as everything else in this
module: nothing infers a status from care-log history.

## Addendum: view and edit modes on the map, tap-to-peek instead of hover-only

The original brief was "hover a plant to see what it is and its latest/upcoming actions", and
touch dragging (above) was bolted onto a map where everything was draggable at all times. On a
phone that combination failed twice over: there is no hover, and a finger tap that wobbled more
than the 4 px drag threshold moved a plant instead of opening it — while zones, being drag
handles with `touch-none`, stopped the page scrolling wherever a finger landed on a bed.

The map now has two modes. **View** (the default) makes zones pure decoration
(`pointer-events: none`) and plant markers plain buttons: a tap opens a peek card under the map
with the same summary the hover card shows, plus a one-tap log for the due action; a second tap
opens the full panel. **Edit** (behind "Bewerken") restores dragging, with a larger threshold for
touch (10 px) than for a mouse (4 px). The hover card stays for devices that actually hover
(`(hover: hover)`), since a touch tap also fires an emulated `mouseenter` that would otherwise
leave it stuck open. No backend or schema change: a peek's "gedaan" is the same
`POST /plants/{id}/logs` Vandaag's "Nu gedaan" already uses.

Edit mode also resizes by dragging: a handle in each zone's and marker's bottom-right corner
runs through the same gesture state as moving (`mode: "resize"`), keeping a zone's top-left
corner and a marker's centre fixed while the width/height follow the pointer, within the bounds
the old number fields enforced (zones 2–100 %, markers 2–30 %). Those number fields are removed
rather than kept as a second way to do the same thing; the plant form no longer sends
`marker_width`/`marker_height` at all, since its copy — loaded when the panel opened — would
otherwise overwrite a resize made on the map in the meantime.

Rejected: a long-press to drag in a single mode. It keeps one mode, but long-press has no visual
affordance, collides with the browser's own long-press menu, and still leaves a finger on a bed
unable to scroll the page.

## Addendum: every scheduled action on the plant list

`GET /gardnr/plants` used to carry only each plant's soonest action (`next_action`), which was
enough for the Planten table but made Vandaag hide a second thing due on the same plant until
the first was logged. Each row now also has `scheduled_actions`: every active schedule's next
occurrence, soonest first, each tagged with its `schedule_id`. It's computed by the same
`garden_care_service` code (`scheduled_actions`, which `soonest_due_action` now just takes the
first entry of), so the two can't disagree, and it's still derived from the care log on every
read — no stored cursor. Vandaag buckets these client-side into Te laat / Vandaag / Binnenkort
(7 days), the same way it already filtered `is_overdue`, rather than growing a dedicated
endpoint.


## Addendum: an optional start date per schedule

A schedule that was never logged used to come due one interval after it was created, so
"fertilize every 2 weeks, starting Monday" couldn't be entered. `garden_care_schedules.start_date`
(nullable) is the first occurrence when set. `next_due` is then the start date itself if the
action was never logged, otherwise `max(start_date, last log + interval)`. Nothing comes due before
the start date, but a log just before it still pushes the first occurrence back (watered the day
before a schedule starts means you don't water again the next day). It's still a pure function of
the log. The start date is an input the user chose, not a cursor that advances, so the "computed,
never stored" decision above stands. Null keeps the creation-date fallback, and existing rows
weren't backfilled, so no existing due date moved.

Rejected: backfilling every row with `created_at + interval` and dropping the fallback. It's
simpler to read, but the `max` rule would then hide plants that are genuinely overdue because
they were last logged before their schedule existed.
