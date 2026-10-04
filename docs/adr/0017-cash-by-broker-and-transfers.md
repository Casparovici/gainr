# 17. gainr: cash per broker, and a Transfer transaction type

## Status

Accepted

## Context

`Transaction.broker` has existed since the original schema — every Buy, Sell, Deposit, Withdraw
and so on already records which broker it happened at — but nothing ever read it back out as a
breakdown. `cash_balance_eur` summed the whole ledger into one number, and the Cash row on Home
showed only that total. The user's cash is actually split across several real brokers, and they
wanted to see the split, plus a way to move money from one broker to another without it looking
like it left the portfolio.

## Decisions

**A new `TransactionType.TRANSFER`, not a Deposit paired with a Withdraw.** A pair would work
arithmetically (withdraw from one broker, deposit to the other, net zero) but both of those types
already mean something specific elsewhere in the app: `net_invested_eur` sums Deposit and
subtracts Withdraw as money entering/leaving the portfolio from outside (see
[ADR 0014](0014-gripr-gainr-portfolio-bridge.md), which mirrors gripr's own account transfers as
exactly these two types for exactly that reason). A Transfer between two of the reader's own
brokers is not that — it's cash moving *inside* the portfolio — and booking it as Deposit+Withdraw
would silently inflate `total_invested_eur` by the transferred amount every time. A dedicated type
that both `cash_balance_eur` and `net_invested_eur` simply don't recognize (so it contributes
nothing to either) is the only shape that keeps those two figures honest.

**One row, two brokers.** `Transaction.broker` is the source; a new nullable `to_broker` column
is the destination, set only on a Transfer. This mirrors `PositionNote`'s "one table, two views"
instinct from [ADR 0016](0016-position-journal.md) more than it looks like a new pattern: a
transfer is fundamentally one event with two ends, not two independent transactions that happen
to reference each other, so it gets one row rather than a linked pair (which would need its own
reverse-then-reapply bookkeeping on edit/delete, the complexity ADR 0014 already carries for the
gripr mirror and this doesn't need to repeat internally).

**The breakdown is computed, not stored**, same as every other derived figure in gainr.
`cash_balance_by_broker_eur` walks the same transaction list `cash_balance_eur` already does,
bucketing by `broker` (or an `"Unassigned"` sentinel for older rows with none recorded) instead of
summing into one total; a Transfer is the one type that touches two buckets in the same pass
(`-total_eur` on `broker`, `+total_eur` on `to_broker`), which is exactly why it's absent from
`cash_balance_eur`'s own branches — summed across every broker a transfer is already zero, so
counting it there too would double up work for no change to the total. `SummaryOut` carries the
result as `cash_by_broker_eur: dict[str, Decimal]`, piggybacking on the summary endpoint the Home
page and the Cash detail panel already fetch, rather than a new endpoint.

**The Cash row became clickable.** Before this, `PositionsTable` explicitly excluded Cash from
selection ("a derived row with no asset behind it — nothing to open a card on"), even though
`PositionDetailPanel` already had `isCash` branches for it (quantity/price blanked to "—", no
cost-basis section) — reachable by nothing. That was fine when Cash's detail view really had
nothing beyond the total. Once the per-broker breakdown and the Transfer action needed a home,
"nothing to open a card on" stopped being true, so the row (and its name) are selectable like any
other now, opening the same panel everything else uses. The breakdown and a "Transfer" button live
in Cash's own Overview tab, under a new `CashByBrokerSection`, which reuses `TransactionForm`
exactly as `TransactionsSection` already does elsewhere in the panel — a new `defaultType` prop
lets it open pre-set to Transfer instead of the form's usual Buy default.

**The form's "To broker" list excludes whatever "From broker" is currently set to.** Transferring
a broker to itself is a data-entry mistake, not a real transfer; excluding it from the second
dropdown prevents the mistake without needing a server-side check (this app has no history of
validating things the UI can't produce in the first place — see the count/minimum steppers in
[ADR 0015](0015-listr-inventory.md) for the same instinct applied elsewhere).

## Alternatives considered

- **Deposit + Withdraw pair for a transfer** (rejected above): the immediate alternative, and the
  one this ADR spends the most space ruling out, since it's the shape ADR 0014 already uses for a
  *different* kind of transfer and it would have been easy to reach for the same tool here for the
  wrong job.
- **A second `transfers` table** (id, date, from_broker, to_broker, amount) instead of extending
  `transactions`: keeps `Transaction`'s shape simpler, but splits "everything that moves cash"
  across two tables for a distinction (asset-linked vs. not) the existing `asset_id: int | None`
  nullable column already encodes for every other cash-only type (Deposit, Withdraw, Interest,
  Broker Fee). A Transfer fits the existing table by adding one more nullable column, not a
  parallel structure.
- **Per-broker balance as its own endpoint** (`GET /api/cash/by-broker`): would decouple it from
  the summary payload, but the Cash panel already needs `["summary"]` for the total `Value` stat
  showing at the top of the same tab, and React Query dedupes the identical key Home's own
  `summaryQuery` already populates — a second endpoint would just be a second round trip for data
  the page already has.

## Consequences

- A broker that only ever appears on Buy/Sell/Dividend rows (never a Deposit/Withdraw/Transfer)
  still shows up correctly in its own bucket — `cash_balance_by_broker_eur` buckets by every cash-
  moving type the same way `cash_balance_eur` already summed them, not just the pure-cash ones.
- Editing or deleting a Transfer moves or removes both sides at once, for free — it's one row, so
  there's no "half the transfer got deleted" state to guard against, the same consequence ADR 0016
  got from putting Journal and position notes on one row instead of two.
- The Transactions page's own table still shows only one `Broker` column, so a Transfer row there
  displays its source broker and not the destination — opening the row (or the Cash panel) to edit
  it is how the destination is seen. Not fixed here: a second column for every row when only one
  type ever populates it is a wider change than this feature needed.
