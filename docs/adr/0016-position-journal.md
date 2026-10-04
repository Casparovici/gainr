# 16. gainr: a Journal tab, and labels on position notes

## Status

Accepted

## Context

`PositionNote` already existed as a per-holding journal (ADR: none written at the time, added
alongside target weight) — a title + free-text body, rendered with a small markdown subset, on
the Notes tab of a position's own detail panel. The user wanted a third tab, next to Home and
Transactions, showing every note across every position at once as a tile grid, each tile linked
back to the position it's about, with labels addable per entry — and adding a note from that new
view had to show up on the position's own Notes tab too.

## Decisions

**One table, two views — no sync code.** The Journal tab's `GET /api/journal/notes` is a
different query over the exact same `position_notes` rows the existing
`GET /api/assets/{id}/notes` already reads and writes (`position_note_repo.list_all_notes`
instead of `list_notes`, eager-loading the asset and labels for the tile grid). Creating a note
"from the Journal" is literally `POST /api/assets/{asset_id}/notes` with an asset picked in the
UI — there's no separate journal-side create endpoint, and therefore nothing to keep in sync:
the position's own Notes tab and the Journal tab can never disagree, because they're reading the
same row, not a copy of it.

**Labels are global and many-to-many**, the identical shape listr's recipe categories already
established for "several tags at once, on a table that isn't itself the primary catalog" (ADR
0006): `PositionNoteLabel` (id, name unique, sort_order, color, is_archived) plus a plain
`position_note_label_links` association table, get-or-create by name on the same "type a name,
reuse if it exists" convention the catalog/Picnic-import flows already use. Global rather than
per-position, since the same label ("Thesis", "Risk") should filter consistently across the
whole Journal regardless of which holding a note is about — a label scoped to one position
would defeat the point of a cross-position filter.

**Linking a Journal tile to its position reuses the existing detail panel, via a URL param, not
a second copy of it.** `PositionDetailPanel` already renders a position's full detail (overview,
financials, transactions, notes) but only ever as client state on `Home.tsx` (`useState<Position
| null>`), with no route of its own. Rather than give positions a real `:id` route (a bigger
change than this feature needed) or duplicate the panel on the Journal page, a Journal tile
links to `/?position=<assetId>`; `Home.tsx` reads that param once its positions have loaded,
opens the matching one in the same panel used everywhere else, and drops the param so a later
back/refresh doesn't reopen it. One detail view, one implementation, reached two ways.

**The note-rendering pieces are shared, not duplicated**: `NoteBody`/`NoteExpandDialog` (the
3-line clamp + "Show more" dialog) moved out of `PositionDetailPanel.tsx` into their own
`components/NoteBody.tsx`, typed over just `{title, body, created_at}` so both `PositionNote`
and the Journal's `JournalNote` (which carries extra asset context) satisfy it without a cast.
`LabelPicker` (the interactive add/edit control) and `LabelChips` (read-only display) are new
shared components for the same reason — the position panel's own note form and the Journal's
both need the identical picker over the identical global label set.

## Alternatives considered

- **A separate `journal_entries` table, synced from `position_notes` on write**: rejected outright
  — two tables for one concept means a sync bug is only a matter of time, and there's no reason
  for the Journal's notes to ever be a different set than the position's own.
- **Per-position labels** (a `label` column on `PositionNote`, or labels scoped to one asset):
  rejected — the Journal's whole point is filtering *across* positions by theme ("show me every
  Risk note, whichever holding it's on"), which a per-position label can't do.
- **A dedicated position detail route** (`/position/:id`) instead of a query param on Home:
  more RESTful, but a bigger change than this feature asked for — `PositionDetailPanel` has no
  route today, and giving it one is a reasonable future step but not one this ADR needed to take
  to link a Journal tile back to its position.
- **A nested `<form>` for the label quick-add** (matching the visual shape of a single control):
  tried first, and doesn't work — a `<form>` inside another `<form>` isn't valid HTML, and
  browsers silently mangle it rather than erroring, so Enter inside it did nothing instead of
  creating the label. Replaced with a plain input plus an explicit "+ Add" button (Enter still
  works as a convenience via `onKeyDown`, but isn't the only way to commit) — the same lesson
  the listr inventory-minimum bug already taught this session: an explicit, self-contained
  action beats one that depends on an implicit event firing correctly.

## Consequences

- Deleting a note from either the Journal or the position panel removes it everywhere, since
  it's the one row — there's no "delete from journal, still shows on the position" edge case to
  handle, because that edge case can't exist.
- A label with `is_archived = true` stops appearing in the picker/filter, same as every other
  archived-category pattern in this app, but existing notes keep whatever labels they already
  had — archiving hides it from new selection, not from history.
- The Journal grid has no pagination or date-range filter yet — fine at this app's personal
  scale (a few dozen notes across a handful of holdings), the same "correct by construction,
  revisit if it ever matters" reasoning gainr's other read-heavy views already use.
