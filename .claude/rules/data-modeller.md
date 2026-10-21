---
paths:
  - "backend/app/models/**/*.py"
  - "backend/app/schemas/**/*.py"
  - "backend/alembic/**/*.py"
---

# Role: Data Modeller
# Purpose: Schema, migrations and the ledger

## Principles

- The transaction ledger is the source of truth. Positions and cash are derived on every
  request, never stored.
- Every gainr transaction belongs to exactly one portfolio; nothing sums across portfolios
  implicitly (ADR 0019). Assets are shared; target weights and cash settings are per portfolio.
- Money columns are `NUMERIC`/`Decimal`, never float, stored in the transaction's native
  currency with that currency alongside. Base currency is EUR; convert with point-in-time FX
  rates, never one current rate applied to history. gripr is euro-only (ADR 0033).
- SQLite: no materialized views, limited `ALTER TABLE`. Write migrations that work on it and
  could still move to Postgres later (`GAINR_DATABASE_URL`), so no SQLite-only types or pragmas
  in models.

## Migrations

- A schema change is an Alembic revision in `backend/alembic/` plus an ADR in `docs/adr/`.
- Make migrations idempotent and safe on the real, populated database: add nullable columns or
  give a default, backfill in the revision, and never drop or rewrite a ledger column.
- Index what the queries filter on (portfolio, asset, date). Schemas in `app/schemas/` are the
  API contract; change them together with the frontend types.
