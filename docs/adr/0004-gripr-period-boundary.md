# 4. A configurable period-start-day generalizes gripr's calendar-month assumption

## Status

Accepted

## Context

gripr's period-shaped views — Budget, Categories' budget progress, Overview, and Transactions'
"Upcoming recurring" preview — all hard-coded the calendar month (1st to end-of-month) as the
unit of "a period," independently, in five places: `GriprBudget.month`'s storage convention
(always the 1st), `gripr_budget_service.month_bounds()`, `gripr_overview_service`'s hand-rolled
month-decrement loop, the frontend `MonthSwitcher` component, and Transactions' own
`isoDate.slice(0,7)` string check. The user wants periods that don't start on the 1st — e.g. a
cycle running the 25th to the 24th, aligned to a payday rather than the calendar.

## Decision

**One configurable setting, `period_start_day` (1–28), default 1.** Default 1 makes every
existing behavior a special case of the general one — nothing changes for anyone who never
touches it, and every existing `GriprBudget` row (all keyed at the 1st) stays exactly as valid
as it always was. Capped at 28 deliberately: every month has a 28th, so the period-start date
never needs end-of-month fallback logic, and it keeps "+1 month" day-preserving arithmetic
(Python's `relativedelta`, JS's `Date.setMonth`) safe on both ends of the stack — neither ever
has to reason about February or 30- vs. 31-day months for the start day itself.

**One shared primitive, `gripr_period_service.period_bounds(reference_date, start_day)`**,
replacing the five independent calendar-month assumptions rather than patching each one
separately. It returns the `[start, end]` of whichever period `reference_date` falls in: if the
reference date's day is on or after `start_day`, the period starts that day in the reference
date's own month; otherwise it starts `start_day` in the previous month. At `start_day == 1`
this is byte-for-byte what the old `month_bounds()` returned — that equivalence is the
backward-compatibility guarantee, and it has a dedicated regression test
(`test_gripr_period_service.py`).

**`GriprBudget.month`'s meaning shifts from "always the 1st" to "always the configured period's
start date."** No column type change, no data migration: since the default is 1, this is
invisible until the setting is changed, and only *future* periods (and any budget set against
them) use the new boundary. `frontend/src/utils/griprPeriod.ts` is a JS port of the same
primitive, kept in exact sync, so the frontend never disagrees with the backend about which
period a date falls in — critical for seeding a page's initial period correctly (see
Consequences).

**The setting is a new singleton table, `gripr_settings`** — not a field added to
`portfolio_settings` (gainr-scoped by name and existing purpose; conflating gripr into it saves
one table at the cost of a confusing split). Same pattern: fixed id, lazy-create-on-write.

**The control lives inside `PeriodSwitcher`** (the renamed, generalized `MonthSwitcher`) behind
a small gear icon, rather than a new standalone settings page for one field — it's reachable
from every page that already shows a period (Budget, Categories, Overview), and changing it
from any one of them takes effect everywhere via one shared `["gripr-settings"]` query.

## Alternatives considered

- **Retroactively re-key existing `GriprBudget` rows when the setting changes**: rejected — a
  budget "for September" has no single obvious mapping onto "the period starting Aug 25," and
  silently rewriting historical budget data on a settings change is exactly the kind of
  automatic guess this app avoids elsewhere (the "Correct balance" flow makes the
  missing-transaction-vs-drift choice explicit rather than assuming one).
- **A field on `portfolio_settings`**: rejected for the scoping reason above.

## Consequences

- A page can't safely guess "the current period" from a hardcoded `start_day=1` and correct it
  after settings load — if today's day-of-month is past the *real* configured start day but the
  guess assumes 1, the guessed reference date can land in the wrong (previous) period entirely.
  Budget.tsx, Categories.tsx, and Overview.tsx all gate their initial period on the settings
  query resolving first, rather than seeding eagerly.
- Changing the setting mid-use intentionally does not try to translate the currently-viewed
  period into the new scheme — `PeriodSwitcher` lands on "the period containing today" under
  the new setting instead, which is always well-defined.
