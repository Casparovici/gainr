# 14. Bridge gripr's brokerage account to gainr's portfolio

## Status

Accepted

## Context

gainr and gripr have always described the same money from two sides. gripr's "Beleggen" account
holds what the household thinks is at the broker; gainr holds the actual ledger of deposits,
buys, sells and prices. Until now the two were maintained entirely independently, and had
drifted a few percent apart: gripr summed an opening balance plus 113 transfers in, gainr
valued cash plus holdings at market.

Two different things were being conflated in that gap:

1. **Money moving into or out of the broker** — a transfer from checking to Beleggen. That is a
   real transaction, and it already had to be typed twice: once as a gripr transfer, once as an
   gainr deposit.
2. **Market movement** — the portfolio being worth more or less today than yesterday. That is
   *not* a transaction. Nothing moved between accounts; an asset revalued.

Conflating them is what makes naive syncing wrong. If daily P&L were booked as gripr
transactions, the ledger would fill with movements that never happened and every
category/budget/cash-flow figure downstream would be polluted.

## Decision

A single link — `GriprSettings.portfolio_account_id` — names the gripr account that mirrors
gainr. Null (the default) leaves the whole bridge inert. It's an explicit id rather than
matching a name like "Beleggen" because there are four investment-ish accounts with similar
names ("Beleggen", "Robeco Beleggen", "Beleggingsrekening kinderen", "Crypto") and names are
renameable in-app.

Across that link, the two kinds of change are handled differently, which is the whole point:

- **Transfers are mirrored as transactions.** A gripr transfer *into* the linked account books an
  gainr `Deposit`; a transfer *out* books a `Withdraw`. The mirror carries
  `source_ref = "gripr_transfer:{gripr_txn_id}"` (already unique on `transactions`), so editing the
  gripr transfer updates its counterpart, deleting removes it, and re-pointing it at another
  account deletes it — the same reverse-then-reapply discipline ADR 0003 established for
  loan-linked categories. Only transfers mirror: an expense or income booked directly on the
  brokerage account (a fee, a dividend) is already in gainr's own ledger, and mirroring it would
  count the same euro twice.
- **Market movement is only ever a balance.** `sync_balance` overwrites the linked account's
  stored balance with gainr's portfolio value and books nothing. It runs after any mirrored
  transfer, daily right after the price refresh (so the figure comes from that day's prices),
  and on demand from a "Sync now" button.

Linking forces the account to `MANUAL` balance mode, since a transactional account would
recompute its balance straight back out of its own ledger and discard the synced figure.

## Alternatives considered

- **Derive the balance live on read** (a third balance mode that reads through to gainr): can't
  drift and needs no sync job, and it matches the project's "derive, never store" instinct.
  Rejected in favour of a stored balance the user can still see, reason about, and hand-correct,
  accepting that it's stale between syncs — a deliberate call, since an account balance that
  silently changes on every page load is harder to trust than one with a known "as of".
- **Match the account by name** (`"Beleggen"`): no schema change, but ambiguous against three
  similarly-named accounts and broken by the rename feature shipped the same week.
- **Book daily P&L as gripr transactions** so the balance follows from the ledger: rejected
  outright. It would invent money movements that never happened and corrupt every spend,
  budget and cash-flow figure that reads the transaction table.
- **Backfill the existing 113 transfers into gainr deposits**: rejected. gainr already holds 136
  deposits covering that same history, imported from the xlsx; mirroring them now would
  double-count most of the portfolio.

## Consequences

- Linking moves the account's displayed balance to gainr's total — a few percent lower in the
  current data. That gap was always there; it just wasn't visible.
- Only *new* transfers mirror. Historical gripr transfers keep their existing gainr counterparts
  from the xlsx import, and nothing reconciles the two retroactively.
- Re-running `scripts/import_transactions.py` on a sheet that also contains a transfer already
  mirrored from gripr would create a second gainr row for it: the xlsx row carries an
  `xlsx:`-prefixed `source_ref`, the mirror a `gripr_transfer:` one, so neither dedupes the other.
  Worth remembering before any future re-import.
- gripr now depends on gainr's services (`position_service.portfolio_value_eur`). That's a new
  direction of coupling between modules, deliberately confined to one service
  (`gripr_portfolio_link_service`) so it stays greppable rather than spreading.
