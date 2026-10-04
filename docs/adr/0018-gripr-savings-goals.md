# 18. gripr: savings goals for transfers into savings/investment accounts

## Status

Accepted

## Context

Categories and Budget could only set a monthly Budget/Target on a top-level **category**
(`GriprBudget`, keyed on `category_id` + `month`). But `GriprTransactionType.TRANSFER` is
deliberately excluded from every category spend rollup — a transfer moves money, it doesn't
spend or earn it — so there was no way to set "move €500/month into my investment account" as a
goal, even though the transaction data for it (a transfer into a savings/investment account)
already existed.

## Decision

A **new table**, `pefi_savings_goals` (`GriprSavingsGoal`: `account_id`, `month`, `amount`,
unique on the pair), parallel in shape to `GriprBudget` but keyed on `account_id` instead of
`category_id`, rather than making `GriprBudget.category_id` nullable and adding an
`account_id` alternative on the same row. Two reasons:
- `category_id` is `NOT NULL` today; relaxing it needs a SQLite table rebuild
  (`batch_alter_table`) for an XOR constraint ("exactly one of category_id/account_id")
  SQLite can't enforce cleanly as a `CHECK` anyway.
- It keeps every existing `GriprBudget` code path — descendant-category rollup, the
  delete-a-category cascade, drag-to-reorder — completely untouched.

This mirrors ADR 0002's precedent: a target that doesn't fit the existing row structure got a
new table (`portfolio_settings` for cash's target weight) rather than bending `Asset` further.

**"Saved"** (the actual, against the goal) is **net transfers into the account within the
period**: inbound (`counter_account_id = account`) minus outbound (`account_id = account`,
type=TRANSFER). A withdrawal back out during the period lowers progress — the intuitive reading
of "how much did I actually save this month," not just a running total of deposits.

**Restricted to `GriprAccountType.SAVINGS` and `GriprAccountType.INVESTMENT` accounts**,
validated in the router (`PUT /gripr/savings-goals`) the same way `linked_loan_account_id` is
restricted to `type == LOAN` today — a goal only makes sense for an account you're deliberately
building up, not a checking or loan account.

**UI reuses the existing budget tile language** (`ProgressBar`, `BudgetCell`'s
pencil-to-edit-with-suggestion-chips control) rather than a new pattern — a savings goal behaves
exactly like an income target (more is better, "Target" label, "Ahead by"/"Behind by" wording),
so it passes `kind="income"` through unchanged. `BudgetCell` was extracted out of `Budget.tsx`
into `components/gripr/BudgetCell.tsx` so Categories.tsx can reuse it too, rather than
duplicating the editable-figure control a second time.

## Alternatives considered

- **Make `GriprBudget.category_id` nullable, add a nullable `account_id`**: rejected for the
  migration/constraint reasons above.
- **Reuse `GriprBudget` unmodified by inventing a synthetic pseudo-category per savings
  account**: would avoid a new table, but conflates two different domain concepts (a spend
  category and a transfer destination) under one id space, and would need every category rollup
  query (`descendant_ids`, delete-cascade) to specifically exclude these synthetic rows to avoid
  them leaking into expense/income totals.

## Consequences

- A savings goal has no "Recurring" suggestion parity issue: `GriprRecurringTransaction` already
  supports `type=TRANSFER` with a `counter_account_id`, so a recurring rule that auto-transfers
  into a savings account feeds the same three-suggestion-chip UX (`monthly_equivalent_for_account`
  mirrors `monthly_equivalent_for_categories`).
- Out of scope for this change: Overview's `budget_status` list, drag-to-reorder for savings
  tiles (account order already comes from the Accounts page's own `sort_order`), and an
  archived-accounts toggle for this section. Each is a small, separable follow-up if wanted.
