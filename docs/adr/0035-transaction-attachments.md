# 35. gainr and gripr: files attached to a transaction

## Status

Accepted

## Context

A gainr transaction is a row of numbers, but the paper behind it (a broker's contract note, the
invoice for a fee, a dividend statement) lived in a folder somewhere else, with nothing tying the
two together. The reader wants to open the document from the transaction it belongs to.

## Decision

A transaction can have attachments (`transaction_attachments`): a filename, a type, a size and the
file's bytes, one row per file.

- **The bytes live in the database**, like gardnr's log photos. portfolio.db is the one thing that
  is backed up and restored (ADR 0013); a directory of files next to it would fall out of the
  backup and need its own, and the two could drift. The `content` column is deferred, so listing
  attachments or transactions never reads a file.
- **Only PDF, PNG, JPEG and WebP**, up to 10 MB each and 10 per transaction. The type is decided
  from the file's own first bytes, not from the upload's Content-Type or extension, and the file is
  served back with that type, `nosniff`, and `inline` disposition. That is why HTML and SVG, which
  would run as part of this origin when opened, are not accepted.
- **Its own multipart endpoints** under `/api/transactions/{id}/attachments` (list, upload, open,
  delete), not part of the transaction's JSON create/update. An attachment is only served under
  the transaction it belongs to.
- **The transaction list carries only a count** (`attachment_count`, one grouped query per page) for
  the paperclip; the form loads the list itself, so it stays fresh while files come and go.
- **On a new transaction** the form keeps the picked files and uploads them right after the
  transaction is saved. A refused file doesn't undo the transaction; the reader is told which
  files didn't make it and can retry from the saved transaction.
- **Deleting a transaction deletes its files**, explicitly in `transaction_repo.delete_transaction`:
  the app doesn't turn on SQLite's foreign keys, so the `ON DELETE CASCADE` alone would leave
  orphans. Positions, cash and performance never read the table; the ledger is unchanged.

## Alternatives considered

- **Files on disk, a path in the table.** Smaller database, but the daily backup would have to
  learn about a second location, and a restore of the database alone would point at files that are
  not there.
- **A link to wherever the document already lives** (a cloud drive). Nothing to store, but links rot
  and the app can't vouch for what's behind them.
- **Any file type.** Simpler, but an HTML or SVG file served from this origin would run as part of
  the app.

## Consequences

- The database, and with it every daily backup (kept 14 days, pushed off-site), grows by the size of
  the files. At up to 10 MB each, a few hundred invoices is a noticeable but acceptable share; if it
  stops being, moving the bytes to disk is a change inside this one table and its repository.
- No thumbnails, search or OCR: a file opens in the browser's own viewer.
- Editing a file means deleting it and attaching the new one.

## Addendum: gripr (2026-10-05)

gripr transactions get the same thing, and it was meant for gripr first: the invoices and receipts
are mostly behind expenses.

- **A twin table**, `pefi_transaction_attachments` (the module's table prefix), with its own model,
  repository and endpoints under `/api/gripr/transactions/{id}/attachments`. A shared table with
  a type column was the alternative; two small tables keep each module's rows and deletes in its own
  layer, and a gripr transaction's id can never be mistaken for a gainr one.
- **Shared rules and UI.** The type sniffing, limits, filename cleaning and download header live in
  one service (`transaction_attachment_service`), and the form section is one component that takes
  gainr's or gripr's endpoints and its own colours.
- **Same behaviour**: the 10 MB / 10 files limits, deleting the transaction deletes its files
  (explicitly, in `gripr_transaction_repo`), and a count for the paperclip on the Transactions page.
  The account and category dialogs open the same form, so they attach files too.
