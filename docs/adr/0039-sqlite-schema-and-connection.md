# 39. SQLite: migrations build the models' schema; WAL and enforced foreign keys

## Status

Accepted

## Context

The app builds its tables two ways. `app.main` calls `Base.metadata.create_all` on startup, so a
new table exists as soon as the code that uses it runs; the deploy runs `alembic upgrade head`
for changes to existing tables. Every migration since the logo one is guarded with an inspector
for that reason.

Nothing checked that the two agree, and by October 2026 they didn't. `alembic check` against a
database migrated from nothing found:

- two model modules (`gripr_bank_logo`, `listr_meal_plan`) that `app.models` didn't import.
  `alembic/env.py` only imports that package, so Alembic didn't know those tables existed, and
  the next `alembic revision --autogenerate` would have proposed dropping them;
- foreign keys the models declare that no migration added (gainr transactions to their portfolio,
  listr items to their category, …), and NOT NULLs likewise;
- index and constraint names left over from renames (`ix_ing_synced_transactions_*`,
  `uq_pefi_budget_category_month`), and two unique columns indexed as plain ones.

Which shape the real database has depends on which way each table was first created.

## Decisions

- **`app.models` imports every model module**, and a test fails when one is added without it.
- **One guarded migration (`d9e3f1a6c2b8`) brings a migrated database to the models' shape.**
  It inspects each table and only adds what's missing, so it changes nothing on a table
  create_all built. Foreign keys go in through SQLite's batch copy, which doesn't check existing
  rows, so an orphan never blocks the deploy. A NOT NULL whose column still holds NULLs is
  skipped with a message instead of failing the deploy (the deploy would retry it every two
  minutes); missing timestamps are filled in first.
- **Where the difference was only a name, the model changed instead**: the budget constraint
  keeps its original name, and the portfolio-link columns are unique indexes as migrated.
- **A test migrates an empty database to head and compares it with the models**, and another
  applies the alignment to a create_all-built database. CI runs both with the rest of `pytest`.

### Connection settings

The app, the daily sync scripts and the backup all open the same file. With SQLite's default
rollback journal a writer locks out readers, so a page load during a long bank sync could fail
with "database is locked". Foreign keys were declared (with `ON DELETE CASCADE`/`SET NULL` on
some) but SQLite ignores them unless each connection switches them on, so the delete paths
cleaned up by hand and a missed one left rows pointing at nothing: deleting a category left its
recurring rules filed under a category that no longer existed.

- **`app.db.configure_sqlite`** turns on `foreign_keys` and `journal_mode = WAL` on every
  connection of the app's engine, which the scripts share; the tests' engine gets the same. The
  busy timeout is 15 seconds instead of Python's default 5.
- **Alembic's engine doesn't get it.** Batch migrations copy a table and drop the original,
  which must happen with foreign keys off.
- **Rows that are already orphaned stay.** SQLite only checks a foreign key when that column is
  written, so an old orphan doesn't block anything; `PRAGMA foreign_key_check` lists them.
- A gripr category's delete now also un-files the recurring rules filed under it.

## Alternatives considered

- **Drop `create_all` and only migrate.** The cleaner end state, but every migration since the
  logo one assumes a table may already exist, and dev databases and tests rely on it. Keeping
  both and testing that they agree costs less.
- **Rebuild every table with `recreate="always"`.** Simpler code, but it would rewrite tables
  that are already right on the real database for no gain.

- **Keep foreign keys off and keep cleaning up by hand.** It worked for most paths, but
  nothing caught the one that was missed.

## Consequences

- `alembic revision --autogenerate` produces only the change actually made, so a migration can
  be generated and read instead of written by hand.
- A new model needs its import in `app/models/__init__.py`; the test says so if it's missing.
- A delete that would leave a row pointing at nothing now fails loudly (a 500) instead of
  quietly corrupting the data. The test suite runs with enforcement on, so a new delete path
  that forgets its children fails there first.
- The database file has `-wal` and `-shm` companions; a restore has to handle them (ADR 0013).
  Every process writing it needs write access to the directory, which matters once the app runs
  as its own user.
