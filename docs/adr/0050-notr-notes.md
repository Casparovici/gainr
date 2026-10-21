# 50. notr: a notes module, with gainr's Journal as one of its views

## Status

Accepted. Extends [ADR 0016](0016-position-journal.md) and [ADR 0024](0024-journal-notes-on-multiple-positions.md),
whose notes and labels it takes over.

## Context

The app had a place for notes about a holding (gainr's Journal) and nowhere to write anything else:
a thought about a plant, a change to a recipe, an idea. The Journal's notes were also limited to a
small Markdown subset (bold, italic, code, lists, tables), with no links and no pictures. The reader
wanted a notes module, Markdown with pictures, the Journal kept in step with it, and notes that can
be about things in other modules.

## Decision

**One table of notes, with several views.** notr's `notr_notes` replaces `position_notes` as the
only table of notes. A note has a title (it may be empty), a Markdown body, `pinned`,
`is_archived` and the usual dates.

- **Links are optional and per kind:** `notr_note_assets` (a gainr position), `notr_note_plants`
  and `notr_note_recipes`, the same many-to-many shape the Journal already used. A note with none is
  a plain note. Each link is a relationship on the other side as well, so deleting a plant or a
  recipe clears its links and leaves the note.
- **The views are queries over the same rows:** notr lists every note; gainr's Journal lists those
  with a position (`positions_only`); a position's, plant's or recipe's own Notes section lists
  those linked to it. A note written in one place is therefore in all the others, with nothing to
  keep in sync, as ADR 0016 already decided for the Journal and the Notes tab.
- **Labels** (`notr_labels`, the Journal's labels, global and many-to-many) moved with them.
- **One API, `/api/notr`,** replaces `/api/journal/*` and `/api/assets/{id}/notes*`. Listing takes
  filters (`q`, label, position, plant, recipe, `positions_only`, `archived`); pinned notes come
  first, then newest first.
- **The migration moves the Journal in.** Every `position_notes` row keeps its id, text, dates,
  labels and position links, then the old tables are dropped. The deploy already backs the database
  up before migrating. The downgrade puts notes about positions back and is lossy for the rest
  (plain notes, plant and recipe notes, pictures, pins).

**Markdown, with pictures, written as plain text.**

- A picture is `![alt](/api/notr/images/<id>)` in the body, nothing more, so the text stays readable
  anywhere and an export is a file copy.
- **Pictures live in the database** (`notr_note_images`, bytes deferred), like gardnr's log photos,
  listr's recipe photos and transaction attachments (ADRs 0012, 0035, 0043): the one backup covers
  them (ADR 0013), with no second location to drift. Only PNG, JPEG and WebP, decided from the
  bytes; SVG and HTML are refused because they would run as part of the app. Every upload is
  re-encoded and scaled to 1600 px: a small or transparent PNG stays a PNG, a large one (a photo
  saved as PNG) becomes a JPEG. A phone photo costs about 100–300 KB.
- **The text decides which pictures a note owns.** A picture is uploaded on its own first (a new
  note has no id yet) and unattached; saving the note claims the pictures its body shows, and a
  picture the body no longer shows is deleted. An upload whose note is never saved is purged a day
  later, the next time anything is uploaded (no background job). A picture owned by another note is
  left with it.
- **One renderer and one editor for every note.** `Markdown` (react-markdown with remark-gfm)
  renders headings, lists, quotes, code, tables, links, checklists and pictures; it never inserts
  HTML (raw HTML shows as text), only shows pictures notr itself stores, and opens only web, mail and
  tel links, in a new tab without the opener. `MarkdownEditor` is a plain text box with a toolbar,
  Write / Preview, list continuation on Enter, and picture upload by paste, drop or file picker.
  MarkdownLite remains for recipe steps and briefr, which are not notes.
- **A checkbox in a rendered note ticks in place** (`PUT /notes/{id}/tasks`): the server flips the
  n-th `- [ ]` line of the body, and the page counts the same lines, so the two agree.

**Vandaag and the other modules.** `GET /api/taskr/today` carries the pinned notes and their count;
Vandaag lists them and has a "+ Notitie" quick add. briefr's "Save as note" creates a note from a
report. gainr's Journal and a position's Notes tab, gardnr's plant panel and listr's recipe page
show their notes through the same components.

## Alternatives considered

- **Keep the Journal's tables and add notr's next to them,** reading both. It would have kept two
  places a note can live and two renderers, and the "same note everywhere" promise would need
  sync code.
- **A WYSIWYG editor** (TipTap, CodeMirror). Heavy for a phone and for one reader, and it would
  store HTML or a document model instead of plain Markdown.
- **Pictures on disk, or links to somewhere else.** The same reasons as ADR 0035: a second backup
  path, and links that rot.
- **A search index** (SQLite FTS5). Search is a case-insensitive substring over titles and bodies;
  at a personal note count that is instant, and the table could grow an index later.

## Consequences

- The database and its backups grow with the pictures; at a personal scale that is acceptable, and
  moving the bytes to disk would be a change inside one table and its repository.
- A note body is limited to 200,000 characters, a picture upload to 25 MB before it is scaled.
- Notes are not stored per gainr portfolio: a note about a position is about the position, like the
  Journal before it (ADR 0019 concerns ledger data, which notes are not).
- Export (a Markdown zip with the pictures) is not part of this change; it is in the backlog.
