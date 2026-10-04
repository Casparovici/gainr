# 23. gripr: refunds net against spend, attributed to the expense they came back for

## Status

Accepted

## Context

Money sometimes comes back after an expense: someone pays their half of a dinner, or a shop
refunds a return. It often lands in a different account from the one that paid (the dinner
paid from Trade Republic, the Tikkie arriving in ING). gripr had no way to record this
correctly. Its three types were expense, income and transfer, and the form tied the type to the
category kind. That left two workarounds, both wrong:

- **Book it as income.** Account balances come out right, but the category still shows the full
  expense, Budget reads as overspent, and Overview counts money that was never earned as income.
- **Edit the expense down.** The category comes out right, but the paying account's balance is
  now off by the refunded amount, and the receiving account never sees it.

## Decision

**A fourth transaction type, `REFUND`.** It moves money like income: `+amount` on `account_id`,
whichever account received it. It is filed under an **expense** category, though, and every
spend aggregate subtracts it:

| | Account balance | Category kind | Counts toward |
|---|---|---|---|
| Expense | − | expense | spend |
| Income | + | income | income |
| Refund | + | expense | spend, subtracted |
| Transfer | −/+ | — | neither |

Spend now comes from one repository building block, `gripr_transaction_repo._net_spend_query`
(`SUM(CASE type WHEN refund THEN -amount ELSE amount END)` over expense + refund rows). It feeds:

- Budget "spent" on an expense category
- Overview's income-vs-expense chart (expense side)
- Overview's by-category breakdown
- the per-category trend

Income figures still read only `INCOME` rows, so a refund never counts as income.
`sum_by_category_in_range` became unused and was removed.

**An optional link to the expense: `pefi_transactions.refund_of_id`.** When set:

- **The refund counts in the expense's period, not its own.** `_net_spend_query` outer-joins the
  original and filters on `COALESCE(original.date, refund.date)`. A Tikkie arriving on 2 October
  lowers September's dinner, not October's groceries. The future-date rule from ADR 0020 still
  applies to the refund's own date: a refund dated tomorrow doesn't count yet, whatever period
  it belongs to.
- **The refund takes the expense's category.** `gripr_transaction_service` sets it on write, and
  recategorising the expense moves its refunds along with it.
- **The expense shows what came back.** The Transactions list reads `refunded_amount`, batched
  per page, and shows "€30 back" under the amount.

The link is optional. A shop refund whose purchase predates the ledger has nothing to point at,
so an unlinked refund counts on its own date.

**Keeping the link valid** lives in `gripr_transaction_service`, alongside the loan-balance
effects from ADR 0003:

- A refund can only point at an `EXPENSE`, never at itself.
- A refund must sit under an expense category.
- Changing a transaction's type away from refund clears its link.
- Changing an expense's type away from expense leaves its refunds unlinked.
- Deleting an expense keeps its refunds but unlinks them. The money really came in.

A recurring refund rule must also use an expense category. This is checked when the rule is
saved, because its occurrences are booked later through the same validation.

**Recurring refunds** need no new mechanism: a rule can have type refund. An example is a
housemate's monthly share of the rent. Budget's "committed via Recurring" suggestion subtracts
refund rules from expense rules in the same category.

**No DDL for the enum value on SQLite.** The type column is a plain `VARCHAR(8)` holding the
member name, with no CHECK constraint, and `REFUND` fits. The migration adds only `refund_of_id`
and its index. It also adds the enum value on Postgres, in case the database is ever swapped.

## Alternatives considered

- **Income filed under an expense category, no new type.** This needs no enum change. But every
  aggregate filters on `type`, so each one would need a category-kind join. Forgetting it in any
  one place would silently double-count the money as both income and reduced spend. A separate
  type makes each aggregate choose explicitly.
- **Split transactions** (one payment spread across categories or people). This solves a
  different problem, how one payment divides up, and doesn't cover money arriving later in
  another account. It would also be a much larger change to the form and the ledger.
- **Attributing refunds by their own date only.** This is simpler: no self-join, and a closed
  month's figures never change afterwards. But a late Tikkie then makes the month it arrives in
  look cheaper, and the month of the dinner look more expensive, than either really was. The
  user chose attribution to the expense's period.
- **Clamping net category spend at zero.** A category whose refunds exceed its spend in a period
  (a return in a month with no purchases) comes out negative. That is shown as-is on Budget and
  in the trend. Only Overview's by-category breakdown drops non-positive totals, because it
  charts shares of spending and a negative share has nothing to draw.

## Consequences

- A closed period's Budget and Overview figures can change afterwards, when a linked refund
  arrives later. This is intended: the figure converges on what the period really cost.
- Linked refunds show up in a Transactions category filter under the expense's category, since
  they carry it. Their badge's tooltip names the expense they came back for.
- The MCP `add_transaction` tool accepts `refund`, but can't link it. There is no chat tool for
  looking up an expense's id yet (gripr roadmap #3).
- The CSV export writes `refund` as the type. There is no CSV *import* of gripr transactions to
  update.
