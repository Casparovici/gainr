# 24. gainr: a journal note can be about several positions

## Status

Accepted. Extends [ADR 0016](0016-position-journal.md).

## Context

A journal entry often isn't about one holding: "big tech is cheap after the sell-off", "rebalanced
into gold and semis", a comparison between two positions. `position_notes.asset_id` allowed exactly
one position per note, and the Journal form picked it with a single dropdown. The user wanted to
tick several positions for one entry.

## Decision

**A `position_note_assets` association table replaces `position_notes.asset_id`.** It uses
`(note_id, asset_id)` as its primary key, plus an index on `asset_id` for "notes about this
position". This is the same many-to-many shape `position_note_label_links` already uses for labels
(ADR 0016). The migration backfills one row per existing note from its old `asset_id` before
dropping the column, so every existing note keeps its position. The downgrade is lossy by nature:
a note linked to several positions keeps only one.

**The Journal gets its own write endpoints; a position's Notes tab keeps its own.**
ADR 0016 routed Journal writes through `POST /api/assets/{id}/notes` with one asset picked in the
UI. That can't express several positions, so:

- The Journal uses `POST/PUT/DELETE /api/journal/notes[/{id}]`. The body carries `asset_ids`, which
  must name at least one real asset. On `PUT`, omitting `asset_ids` leaves the links alone, the
  same convention `label_ids` follows.
- The position panel keeps `/api/assets/{id}/notes`. Creating there links just that position.
  Editing or deleting there only works on a note linked to that position; any other returns 404.

**Still one table, two views.** `GET /api/assets/{id}/notes` returns every note linked to that
position, including ones also linked to others. Both views return the same shape: the note plus an
`assets` list (id, ticker, name), replacing the old single `asset_id` and the Journal-only
`asset_ticker`/`asset_name`. `JournalNoteOut` went away because it no longer added anything.

**Deleting a shared note deletes it everywhere.** A note is one entry, not one per position.
Deleting it from a position's Notes tab removes it from the other positions and the Journal too.
The confirmation names those other positions, so this isn't a surprise.

**The picker offers the current portfolio's holdings, plus whatever the note is already linked to.**
Notes aren't portfolio-scoped (ADR 0019), so an edited note can be linked to a position held in
another portfolio or since sold. Listing only the current holdings would untick that link on the
next save without the user touching it. Those extra positions are listed, ticked, and marked "not
in this portfolio". The Cash row is excluded, since it isn't an asset.

## Alternatives considered

- **A "primary" position plus "also about" extras** (keep `asset_id`, add the association table):
  it keeps the old column meaningful, but it invents a hierarchy the user didn't ask for, and it
  means two places to check for "notes about X".
- **Copying a note once per selected position**: it needs no schema change, but one thought becomes
  several rows that drift apart the moment one is edited. This is the same objection ADR 0016 raised
  against a separate journal table.

## Consequences

- Every note query joins through the association table. It's eager-loaded with `selectinload`, so a
  Journal page load is still a fixed number of queries, not one per note.
- The frontend's `JournalNote` type is gone. Both views use `PositionNote`, with `assets: NoteAsset[]`.
