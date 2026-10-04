# 21. gripr↔gainr bridge generalizes to multiple links

## Status

Accepted

## Context

ADR 0014 bridged one gripr account ("Beleggen") to gainr's cash and portfolio value, but did so
as a single hardcoded link: `pefi_settings.portfolio_account_id`, a scalar column, and every
sync/mirror function in `gripr_portfolio_link_service.py` called `get_main_portfolio(db)`
directly rather than taking a portfolio as a parameter. That was a reasonable simplification
before gainr had more than one portfolio (ADR 0019) — there was only ever one thing to point at.

Now there's a second one. gripr already has "Beleggingsrekening kinderen", tracking the same
money as gainr's new "Kids" portfolio, and the household wants that pair bridged exactly the way
Beleggen/Main already is: balance mirrored, transfers booked as deposits/withdrawals. The
singleton design can't represent that — it has room for exactly one account, permanently wired
to Main.

## Decision

**`pefi_settings.portfolio_account_id` is replaced by a `pefi_portfolio_links` table**:
`(account_id, portfolio_id)` pairs, unique on both columns. An account mirrors at most one
portfolio; a portfolio is mirrored by at most one account. The migration carries over the
existing single link as a row pointing at Main, so this is a no-op for what was already
configured.

**Every function in `gripr_portfolio_link_service.py` now takes or resolves a specific
portfolio**, instead of assuming Main:
- `linked_account(db, portfolio_id)` looks up the account for one portfolio.
- `sync_mirror(db, txn)` walks every link to find the one (if any) whose account the transaction
  touches, and mirrors into *that* link's portfolio — not always Main.
- `sync_balance(db)` loops over every link, writing each account's balance from its own
  portfolio's value, and returns `{account_id: balance}` for all of them instead of a single
  `Decimal | None`.
- `set_link(db, account_id, portfolio_id)` creates, retargets, or clears one account's link, and
  raises `PortfolioAlreadyLinkedError` if the target portfolio already belongs to a different
  account — surfaced as a 409 by the router, so two accounts can never silently both claim to
  mirror the same portfolio.

**The mirror's `source_ref` format is unchanged** (`pefi_transfer:{gripr_txn_id}`, no account
suffix) — deliberately, so existing mirrored rows from before this change keep matching on the
next edit instead of orphaning and duplicating. This assumes at most one link ever matches a
given transaction, which holds in practice: money moves between an ordinary bank account and a
single linked broker, never directly between two linked brokers. A transfer that somehow touched
two linked accounts at once would only mirror the first match — a known, accepted limitation
rather than something worth a second source_ref scheme for a case that doesn't occur.

**The endpoints move from one scalar settings field to a small REST surface**:
`GET /gripr/portfolio-links` (list all), `PUT /gripr/portfolio-links/{account_id}`
(link/retarget/unlink one account), `POST /gripr/portfolio-links/sync` (re-sync every linked
balance now, same as the existing daily run). `GriprSettingsOut` drops `portfolio_account_id`
entirely — it was never a period-start-day-shaped setting, just parked there for lack of a
better home before this table existed.

**The frontend's per-account toggle becomes a portfolio picker.** `AccountDetailDialog`'s "Track
my gainr portfolio" checkbox becomes a `<select>` of gainr portfolios (via the existing
`usePortfolio()` context, already loaded app-wide), with portfolios already linked to a
*different* account filtered out of the options — so the UI can't attempt the 409 case at all,
rather than surfacing the rejection after the fact.

## Alternatives considered

- **A `portfolio_id` column added to `GriprAccount` itself**: fewer moving parts than a link
  table, but conflates "which portfolio does this account mirror" with the account's own
  identity, and doesn't cleanly express "unlinked" vs. "linked to portfolio 1" without a nullable
  FK on every account row for a relationship only two accounts will ever have.
- **Keep the singleton and add a second one** (`portfolio_account_id_2`, or a fixed "kids" slot):
  doesn't generalize past two, and re-hardcodes exactly the assumption this change removes.
- **Let one account mirror multiple portfolios (or vice versa) by dropping the uniqueness
  constraints**: no real use case for it here, and it reopens the ambiguity ADR 0014 explicitly
  avoided — "which figure does this balance represent" needs one unambiguous non-hardcoded
  answer per account.

## Consequences

- `scripts/refresh_prices.py`'s daily sync now reports every linked account it wrote, not one.
- Downgrading past this migration only recovers a single link (whichever one points at Main) —
  a second link (e.g. Kids) has no representation in the old scalar column and is silently
  dropped on downgrade. Acceptable since downgrading a live schema is not a normal operation
  here; documented in the migration's downgrade path rather than guarded against.
- A future third portfolio (a third kid, a joint account) needs no further schema change — just
  another row in `pefi_portfolio_links`.
