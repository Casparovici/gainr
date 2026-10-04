# 32. gripr: expenses can expect money back

## Status

Accepted

## Context

The reader regularly fronts money: a restaurant bill for the table, borrels and pizza for work.
Part or all of it comes back later, by Tikkie or bank transfer. This was tracked in two ways:

- a **Debiteuren account**, with transfers to it when lending and back when repaid. That fits a
  pure loan.
- a **Debiteuren expense category**. That mixed spending with money owed: the full bill counted as
  spending, and a repayment either inflated income or went unrecorded.

Refunds (ADR 0023) already net a repayment against its expense, in the expense's period. But until
the money arrived, the full bill counted as spending, and nothing showed what was still owed.

## Decision

An expense can carry `expected_back` (an amount, at most the expense) and `expected_from` (who
owes it).

- **Spending counts only the reader's share from the start.** Every spend figure (Budget,
  Overview) is built in one query, `_net_spend_query`. For an expense expecting money back, it
  counts the amount minus whatever is still outstanding, next to the refunds already received.
  Receiving the money therefore doesn't change the share. Getting back more than expected lowers it
  further.
- **Account balances are untouched.** The bill really left the account, so the bank and gripr
  agree throughout. The open amount is listed as "Owed to you" on Accounts and counts in net worth
  as an asset, like the Debiteuren account's balance, until it's repaid or written off.
- **An amount closes** when linked refunds cover it. **Writing it off** lowers the expectation to
  what came back, so the rest becomes the reader's own spending.
- **The bank sync books a repayment as a refund** of the expense when a word of `expected_from`
  appears in the payment's counterparty or description, and exactly one open expense fits
  (amount at most what's outstanding). Otherwise it's booked as income as before, and the edit
  form offers "Money back for…" with the open amounts, which turns it into that refund.

The Debiteuren account stays for pure loans. The Debiteuren category's expenses were re-filed:
own spending to its real category, money still owed as `expected_back`, and the category archived.

## Alternatives considered

- **Count the full bill until repaid** (cash view). Simpler, but Budget overstates spending for
  weeks and swings when the Tikkies arrive. The share is known when the bill is paid.
- **Book the fronted part as a transfer to the Debiteuren account.** Accurate, but it means
  splitting every bill into two transactions by hand, and the bank's single payment no longer
  matches one row.
- **Leave open amounts out of net worth.** More conservative, but inconsistent with the Debiteuren
  account, whose balance (a loan) does count. The reader chose to count both; a write-off removes
  an amount that isn't coming.

## Consequences

- A repayment is only matched automatically when `expected_from` names the payer. Without a name,
  or with two open expenses from the same person, the reader picks.
- Matching by name can mismatch when two people share a word (a surname). The amount check limits
  that to payments that fit what's still owed.
