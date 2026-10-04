# 2. Target weight: a nullable Asset column, cash in its own singleton table

## Status

Accepted

## Context

Each holding needed an editable target allocation weight, visible as a column on the active
positions table and editable from a position's detail card, with cash included in the same
budget — the total across every holding plus cash must never exceed 100%.

Positions themselves are derived from the transaction ledger on every request and never
stored (see the summary_service/position_service architecture). Cash is a *synthetic* position
— `positions.py` builds a `CASH_ASSET_ID = 0` row on the fly; there is no `Asset` row for it and
never has been, since it isn't a holding.

## Decision

**Real holdings**: a nullable `target_weight_pct` column directly on `Asset`, the same shape as
the existing `dlt_judgment` column — both are per-asset "judgment" values that live alongside
the asset's identity, not derived from the ledger, and both are edited independently of any
transaction.

**Cash**: since cash has no `Asset` row to attach a column to, its target weight lives in a new
`portfolio_settings` table — a **singleton** (exactly one row, fixed id) rather than a generic
key-value settings table. Nothing else needs configurable portfolio-wide settings yet, so a
generic table would be speculative complexity for a single value.

**The 100%-sum rule** is centralized in one new `target_weight_service`, called from both write
paths (`PUT /api/assets/{id}` for a real holding, `PUT /api/positions/cash-target-weight` for
cash) rather than duplicated in each router. Both paths sum every *other* target weight
(excluding the row being written, so raising an existing value doesn't double-count its own old
value against itself) plus cash's current value, and reject the write — naming the resulting
total in the error — if it would exceed 100%. This guarantees the two endpoints can't drift
into two different interpretations of the same rule.

Target weight is exposed on `PositionOut.target_weight_pct` for both real positions (via a new
batched `asset_repo.target_weights_by_asset_id`, mirroring the existing
`dlt_judgments_by_asset_id` one-query-for-everything shape) and the cash row (from
`portfolio_settings_repo`).

## Alternatives considered

- **A separate `position_targets` table keyed by asset_id** (including a `NULL`/sentinel row
  for cash) instead of a plain `Asset` column: would unify the storage of real and cash targets
  under one table, but adds a join for something that's a 1:1 property of an asset already
  living happily as a nullable column elsewhere on that same row (`dlt_judgment`). Rejected as
  unnecessary indirection.
- **Validating the 100% sum at write time only within each router**: simpler per-endpoint, but
  is exactly the kind of duplicated business rule that drifts — a future change to what counts
  toward the cap (e.g. excluding a specific asset class) would need to be made twice, and could
  easily be made once.

## Consequences

- Clearing a target weight (`null`) never needs the headroom check — only a non-null value can
  push the total over 100%, so `target_weight_service` skips validation entirely on a clear.
- The `portfolio_settings` table is a new kind of thing in this schema (a singleton), worth
  knowing about if a second portfolio-wide setting shows up later — reuse this table rather
  than inventing a third pattern.
