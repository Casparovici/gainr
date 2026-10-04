# 19. gainr: multi-portfolio support

## Status

Accepted

## Context

gainr was single-portfolio at the schema level, not just the UI: every derived figure
(positions, cash, performance, summary) was computed by `transaction_repo.list_all_transactions`
— a completely unfiltered read of the whole `transactions` table — with no owner/portfolio
column anywhere. The only existing "grouping" concept was `Transaction.broker`, a free-text
label (no `Broker` table) used purely for a cash-by-broker breakdown, orthogonal to *whose* money
it is. `PortfolioSettings` (cash's target weight) was a hardcoded `SETTINGS_ID=1` singleton, and
`Asset.target_weight_pct` was a single column per asset.

The user wants to track a second, genuinely separate portfolio (their kids' investments)
alongside their existing one, inside the same gainr module — its own transactions, positions,
performance, and cash, never mixed with the main one.

## Decision

**A new `Portfolio` model** (`portfolios`: `id`, `name`, `is_archived`, `sort_order`,
`created_at`), structurally mirroring `GardenArea` — this codebase's existing precedent for "a
container entity owning a scoped slice of another table via a plain FK." `Transaction.portfolio_id`
scopes the ledger; every derived read (`transaction_repo.list_all_transactions`/`list_transactions`
/`list_distinct_brokers`, and everything built on them — `position_service`, `performance_service`,
`summary_service`) now takes a required `portfolio_id`.

**`Asset` stays global**, keyed by its existing unique `ticker`. If two portfolios hold the same
ticker, they share one `Asset` row (and its price/logo cache) — correct and desired, avoids
duplicate price-fetching. Only the *ledger* is portfolio-scoped; identity/price data isn't.

**Target-weight judgments move off the two places they used to live as globals/singletons.**
`Asset.target_weight_pct` is removed; a new `PortfolioAssetTarget(portfolio_id, asset_id,
target_weight_pct)` table replaces it. `PortfolioSettings` stops being a hardcoded `SETTINGS_ID=1`
singleton and gets a `portfolio_id` column instead (one row per portfolio, looked up rather than
assumed). Without this, a target weight set on a ticker held in both portfolios would silently
apply to both — wrong, since the kids' portfolio's allocation strategy has nothing to do with the
main one's. `target_weight_service`'s 100%-cap check is scoped to one portfolio's rows.
`Asset.dlt_judgment` stays global — DLT's rating is a property of the security itself, not of
which portfolio holds it.

**The performance cache (ADR 0001) becomes keyed by portfolio** —
`dict[int, tuple[date, list[SeriesPoint]]]` instead of one process-lifetime slot, since a second
portfolio's computation would otherwise overwrite the first's. `invalidate_cache(portfolio_id)`
clears one entry; called with no argument it clears every portfolio's (used where a mutation's
portfolio isn't known at the call site).

**The gripr↔gainr bridge (ADR 0014) keeps pointing at the "Main" portfolio only.**
`gripr_portfolio_link_service` resolves Main's id (`portfolio_service.get_main_portfolio`,
get-or-create by name) for its mirrored deposits/withdrawals and its `portfolio_value_eur` call,
so it keeps working exactly as before. Linking a *second* gripr account (gripr already has one
literally named "Beleggingsrekening kinderen") to the new Kids portfolio is a natural follow-up,
not built here — it wasn't asked for and roughly doubles the bridge's own scope.

**The import script** (`scripts/import_transactions.py`) gained an optional `--portfolio NAME`
flag (default `"Main"`, get-or-create by name). `source_ref` stays exactly
`xlsx:Transaction:row{n}` when importing into Main, for zero risk to already-imported rows'
idempotency; any other portfolio's rows are prefixed with the portfolio name
(`xlsx:{portfolio}:Transaction:row{n}`) since those are fresh imports with no legacy format to
preserve.

**`scripts/refresh_prices.py`** now unions held assets across every portfolio (archived included)
before refreshing prices once per asset — prices are a shared cache, so this shouldn't run once
per portfolio.

**UI: a portfolio switcher, not a combined/stacked view.** Home is a full dashboard (charts,
performance series, allocation) that fundamentally differs per portfolio — unlike gripr's
Accounts tile grid (many small rows, naturally shown together with subtotals), stacking two full
dashboards doesn't work. A switcher (mirroring `useTheme`'s context + localStorage pattern,
visually like `ModuleSwitcher`) scopes Home/Transactions/Journal to one portfolio at a time.

## Alternatives considered

- **A nullable `category_id`/`account_id`-style XOR on the existing settings row**, i.e. keep
  `PortfolioSettings` as-is and bolt on an optional portfolio pointer: rejected the same way
  ADR 0018 rejected it for gripr's savings goals — SQLite can't enforce the XOR cleanly, and it
  keeps a hard singleton's assumptions half-alive.
- **A synthetic pseudo-asset-per-portfolio trick to keep `Asset.target_weight_pct`**: would avoid
  a new table, but conflates two different domain concepts (an asset's identity and a portfolio's
  allocation judgment about it) under one id space.

## Consequences

- Every gainr endpoint that reads or writes portfolio-scoped data now requires a `portfolio_id`
  query param (or body field) — no implicit "current portfolio" on the backend; the frontend
  always passes the selected portfolio's id from `usePortfolio()`.
- Deliberately out of scope for this change: an "All portfolios" combined/consolidated total,
  drag-to-reorder for the portfolio switcher, and extending the gripr bridge to link a second
  gripr account to a second gainr portfolio. Each is a small, separable follow-up if wanted later.
- Position notes / Journal stay asset-scoped, not portfolio-scoped — a note on a ticker shows
  regardless of which portfolio holds that ticker. Low-stakes (a personal annotation), and
  scoping it too would have meaningfully grown this change for little value.
- The migration backfills every existing transaction, target weight, and the settings singleton
  onto one seeded "Main" portfolio, so this is a no-op change in what the app shows for existing
  data — verified by running it against seeded pre-migration data and confirming the backfilled
  rows land correctly before/after an upgrade→downgrade→upgrade round trip.
