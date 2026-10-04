# 3. Loan-linked categories adjust the loan balance via reverse-and-reapply

## Status

Accepted

## Context

A handful of gripr expense categories map onto a specific loan (e.g. a "Studieschuld" category
alongside a "Studieschuld" loan account). When a transaction is filed there, the loan itself
should visibly move — money leaving a checking account to make a student-loan payment should
lower what's still owed, without a second manual step.

Loan accounts use `GriprBalanceMode.MANUAL`: `manual_balance` is a hand-edited running figure,
not derived from the transaction ledger the way a checking account's balance is. So "the
transaction lowers the loan" has to mean something concrete: some code, somewhere, needs to
mutate a *second* account's balance as a side effect of writing a transaction against a
*different* account. That's new — nothing in gripr mutates more than one account per write today.

## Decision

**Schema**: a nullable `linked_loan_account_id` FK on `GriprCategory`, meaningful only on an
`EXPENSE` category, validated in the category router to reference an account of type `LOAN`.

**Business logic lives in a new `gripr_transaction_service`**, not the router and not
`gripr_transaction_repo`. Until now, `backend/app/routers/gripr.py`'s create/update/delete
transaction handlers called the repository directly — there was no service layer for gripr
transactions because there was no business logic beyond validation. This is genuinely new
business logic (money-bearing, cross-entity), so it gets the layer CLAUDE.md's architecture
already expects: router → service → repository.

**Strategy: capture the pre-image, reverse it, apply the post-image** — not recompute the loan
balance from scratch on every write. Concretely: `_loan_effect(category_id, type, amount)`
answers "what does this transaction's *shape* imply for a linked loan, if anything" as a pure
function; `create_transaction` applies it once; `update_transaction` computes it from the
transaction's state *before* the repo mutates the row, lets the repo apply the field changes,
computes it again from the *new* state, and applies old-reversed then new-applied;
`delete_transaction` applies it reversed. This handles every transition (amount-only change,
category changed between two different linked loans, linked→unlinked, unlinked→linked, type
changed away from expense) via the same two calls rather than a hand-written case per
transition.

Recurring-rule-generated transactions go through the same service
(`gripr_recurring_service.generate_due` now calls `gripr_transaction_service.create_transaction`
instead of the repo directly), so a recurring loan payment adjusts the loan exactly like a
manually-entered one.

**No retroactive re-derivation**: if a category's link is changed or removed after transactions
have already adjusted a loan, those past adjustments are not undone or recomputed. This mirrors
`manual_balance` itself — already a hand-adjusted running figure, not a derived one — so once an
adjustment has applied, it stays applied; only future transactions respect the current link.
The same applies to `gripr_category_service.delete_category`'s bulk un-tagging
(`gripr_transaction_repo.clear_category`): it's a raw UPDATE that bypasses this service entirely,
by design — deleting a category doesn't reach back and reverse loan adjustments its
now-untagged transactions already made.

## Alternatives considered

- **Recompute the loan's contribution from scratch on every write** (sum every transaction
  currently filed under a category linked to this loan, plus whatever the loan's own
  `manual_balance` baseline was before any linked category existed): more robust against drift
  — a bug in the delta logic can't leave the loan permanently off — but requires storing that
  baseline somewhere, and turns every transaction write touching a linked category into an
  aggregate query over the whole ledger instead of an O(1) update. Rejected for now given the
  small number of transactions this ever applies to, but worth revisiting if drift is ever
  observed in practice.
- **A distinct "loan payment" transaction type**, requiring both accounts to be picked
  explicitly every time: more explicit, but reintroduces exactly the manual step this feature
  exists to remove, and doesn't fit the existing expense/income/transfer shape.

## Consequences

- `gripr_transaction_service` is now the required entry point for any future gripr-transaction
  business logic — a later feature should extend it, not add a second parallel service or push
  logic back into the router.
- A loan's `manual_balance` can silently drift from "what it should be" if the delta logic ever
  has a bug, precisely because nothing re-derives it from scratch. The round-trip test
  (`create → update → update → delete` returns the balance to its exact starting value) is the
  guard against that, and should be extended alongside any future change to this service.
