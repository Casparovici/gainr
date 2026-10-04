# 20. gripr: future-dated transactions don't count yet, and recurring pre-books one ahead

## Status

Accepted

## Context

Two related gaps: a transaction dated after today already counted immediately toward account
balances, budget spent/received, the Overview trend, and savings-goal progress — the same as one
dated yesterday — even though it hasn't actually happened. And a recurring rule only ever booked
its transaction once due (`generate_due` looped `next_due_date <= as_of`), so there was no way to
see or adjust an upcoming bill/income ahead of its date; it simply didn't exist in the ledger
until then.

## Decision

**Every gripr aggregate now excludes anything dated after today.** `gripr_transaction_repo`'s sum
functions (`sum_amount`, used for account balances; `sum_by_type`, `sum_for_categories`,
`sum_by_category_in_range`, `net_transferred_in`) each add a `date <= date.today()` clause
alongside whatever period range the caller already passed. Listing functions
(`list_transactions`, `list_all_transactions`) are untouched — a future-dated transaction stays
fully visible and editable in the Transactions ledger, just invisible to totals until its own
date arrives. No new column, no "is this counted" flag: purely a read-time filter, consistent
with positions/balances already being derived from the ledger on every request rather than
stored.

**Recurring rules now pre-book their next occurrence once it's within `PREBOOK_HORIZON_DAYS` (2)
of its own due date**, so it shows up (editable) in Transactions a couple of days ahead of time,
instead of only appearing once due. `generate_due` gained a second phase after its existing
catch-up loop: once a rule is fully caught up (`next_due_date > as_of`) and that date falls within
the horizon (`as_of < next_due_date <= as_of + PREBOOK_HORIZON_DAYS`), it books that occurrence
too — but doesn't advance `next_due_date` past it, so "next due" (shown on the Recurring page)
always names the same date as the row already sitting in the ledger for it, not the occurrence
after. The horizon is evaluated per-rule against its own due date, not as a single global "what's
due in the next 2 days" query, so with many rules on staggered schedules each one only appears
once it's actually within its own window rather than all of them showing up together the moment
any one of them is close. (An earlier version of this pre-booked unconditionally, however far off
the next occurrence was — with ~45 real staggered rules that collectively looked like everything
for the next 30 days showed up at once, which defeated the point of "a couple of days ahead of
time.") The catch-up loop and the pre-book step share one `source_ref`-keyed idempotency check
(`pefi_recurring:{rule.id}:{date}`), so a pre-booked occurrence whose date later arrives is
recognized as already-booked rather than duplicated.

**Loan-balance and portfolio-mirror side effects are deferred until an occurrence is actually
due.** `gripr_transaction_service.create_transaction` applies both immediately today (a real,
already-happened transaction should). A pre-booked future occurrence obviously shouldn't move a
loan balance or mirror into gainr's cash ledger yet — so pre-booking uses a plain
`gripr_transaction_repo.create_transaction` insert (no side effects), and the *new* `apply_effects`
function (extracted from what `create_transaction` used to do inline) gets called instead, exactly
once, when the catch-up loop later finds that occurrence already in the ledger and its date has
arrived.

**Pausing a rule removes its pre-booked-but-not-yet-due occurrence**, extending the existing
"pausing means those occurrences didn't happen" rule (already applied to *resuming*, which skips
the pause rather than backfilling it — see the original recurring-transactions work) to also cover
an occurrence that was booked ahead of schedule but hasn't happened yet. An occurrence whose date
has already passed is real money that moved and is left alone, same as any other pause.

## Alternatives considered

- **A `status` column on `GriprTransaction`** ("pending"/"posted") instead of a plain date
  comparison: more explicit, but this app already treats "derived from the ledger on every
  request" as the standard for balances/positions (see CLAUDE.md's non-negotiables) — a status
  flag that has to be kept in sync is exactly the kind of stored-derived-state this app avoids
  elsewhere.
- **Generating further ahead** (the rest of the current period, or a fixed N days): asked the
  user directly; "just the next occurrence" was the initial preference — simplest, most
  predictable, and avoids a weekly rule cluttering Transactions with several upcoming rows at
  once. In practice, "next occurrence, whenever that is" still meant everything showed up at
  once across enough rules, so it was tightened to "next occurrence, but only within 2 days of
  its own due date" — still just the one occurrence per rule, but bounded to what's actually
  imminent.
- **Applying loan/portfolio side effects at pre-book time and reversing them if the occurrence
  gets edited or deleted before its date**: would keep `create_transaction` as the only path that
  ever touches those, but means a future-dated transaction *would* move real balances early —
  exactly the thing being fixed. Deferring until due is more code (two creation paths, one
  extra idempotency check) but is the only option that's actually correct.

## Consequences

- `generate_due`'s return value (`list[GriprTransaction]`) now includes pre-booked occurrences
  alongside genuinely-due ones — callers that only cared about "what's due right now" would need
  to filter by `date <= as_of` themselves, though today's two callers (`gripr.py`'s router,
  opportunistic on page load) both discard the return value entirely.
- `gripr_recurring_repo.list_due` was removed (superseded by `list_recurring(include_inactive=False)`,
  since `generate_due` now needs to visit every active rule, not just currently-due ones).
- The Recurring page's description text and this ADR are the only two places this is explained —
  no new UI affordance distinguishes an "upcoming" transaction from a normal one in the
  Transactions list itself (it's just a row dated in the future); a visual "upcoming" badge is a
  reasonable follow-up if it turns out to be confusing in practice, not built here.

## Addendum: reverse only what was applied (2026-10-02)

Deferring a pre-booked occurrence's effects left one path unguarded: editing or deleting a
transaction always reversed its loan effect, whether or not that effect had been applied. On
26 Sep 2026 the pre-booked 25 Oct Studieschuld occurrence was deleted. That added one monthly repayment back onto
the loan that had never been taken off for it, and so undid the real 25 Sep repayment.

`pefi_transactions.effects_applied` now records whether a row's loan/portfolio effects were
applied. `apply_effects` sets it and does nothing the second time. Updates and deletes only
reverse a row that has it. A pre-booked row edited before its date keeps its effects deferred,
applied with the edited shape once due. When the bank sync claims a row whose date has passed but
whose effects were never applied, it applies them, because the bank confirms the payment happened.
The migration marks every existing row as applied, except recurring occurrences their rule hasn't
reached yet. The Studieschuld balance was corrected back by hand.

