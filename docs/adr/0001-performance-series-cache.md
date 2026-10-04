# 1. Cache the daily performance series in memory

## Status

Accepted

## Context

The Home page metrics, the portfolio value line chart, and benchmark comparisons were all slow.
Investigation found the cause wasn't missing indexes or data volume (the whole database is
11.7MB — trivial for SQLite) but algorithmic: `PerformanceService.get_full_series` replayed the
*entire* transaction ledger from portfolio inception, day by day, on every single request —
even when the user only asked for "1D". `SummaryService.get_summary` made this worse by calling
`performance_service.get_range(db, "YTD")` on every Home page load just to get one change
figure, paying the full replay cost a second time in the same request.

CLAUDE.md's non-negotiable is that "positions and cash are derived from the transaction ledger
on every request, never stored" — specifically so the Home page can't drift out of sync with
the ledger on the Transactions page. Any caching here has to not violate that.

## Decision

`PerformanceService` now holds a process-lifetime, in-memory cache of the full daily series:
a single `(computed_as_of: date, points: list[SeriesPoint])` tuple. `get_full_series` returns
the cached points if they were computed today; otherwise it recomputes and re-caches.
`get_range` slices from this cached series instead of recomputing per range.

The cache is invalidated whenever a transaction is created, updated, or deleted (the
transactions router calls `performance_service.invalidate_cache()` after each write). It is
**not** explicitly invalidated on a price-history write — the price refresh (`price_service`)
is itself gated to once per calendar day per asset, and `get_full_series` performs that day's
refresh as part of computing the series, so the cache is always populated *after* that day's
price data is in. A later same-day price correction (e.g. a manual re-run) would not be
reflected until the next day or a process restart — an accepted, narrow gap, not worth a
cross-module invalidation hook between `price_service` and `performance_service` for.

This does **not** violate "derived on every request, never stored": nothing is persisted to
disk, a process restart recomputes from scratch, and every ledger write invalidates the cache
immediately. It's a memoization of a pure function of the ledger, not an alternate source of
truth.

Two smaller, related fixes shipped alongside this:
- `SummaryService`/`PositionService` no longer fetch the transaction ledger twice per request
  (`PositionService.get_positions` now delegates to a new `get_positions_from(transactions)`
  that a caller who already has the ledger can call directly).
- `PositionService.valuation()` (called once per position) is now backed by a batched
  `valuations()` that fetches all assets and FX rates once per request instead of once per
  position.
- The once-a-day Yahoo Finance price refresh moves out of the request path into a new
  scheduled script (`backend/scripts/refresh_prices.py`, run via `deploy/gainr-refresh.timer`),
  so a page load only reads `price_history` and never blocks on a live network call. The
  request path keeps its on-miss fallback fetch as a self-healing backstop.

## Alternatives considered

- **Recompute-from-scratch, no cache**: simplest, safest against drift, but does nothing for
  the actual complaint (every load still replays 4 years of history).
- **A persisted table of daily values**: would survive a restart and could be queried
  cross-process, but re-introduces exactly the "derived vs. stored" drift risk the ledger-first
  design exists to avoid, for a single-user local app where a cold cache costs at most one slow
  request per day. Not worth it here.

## Consequences

- First request of a new day (or after any transaction write) still pays the full replay cost;
  every subsequent request that day is a cache hit.
- The cache lives in one process's memory — restarting the backend (a deploy) simply
  recomputes on the next request, with no migration or persisted state to manage.
- If gainr ever runs multiple worker processes, each would hold its own cache; not a concern
  today (a single local user, single uvicorn worker) but worth revisiting if that changes.
