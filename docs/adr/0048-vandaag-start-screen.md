# 48. Vandaag: one start screen for the whole app

## Status

Accepted

## Context

The app opened on gainr Home, and every module was an island. What needed the reader today was
spread over five places: overdue garden care in gardnr, uncategorised payments in gripr, unread
reports in briefr, the day's workout in trainr, tonight's meal in listr. Only gainr and gripr had a
notification bell, and only gardnr's bottom bar showed a count. taskr already merged gardnr,
trainr and its own tasks into one agenda, but it was a module of its own with a single tab.

A review of the app's flow (October 2026) proposed a start screen that gathers this, and a module
switcher that shows what waits where.

## Decision

**Vandaag is the app's root, `/`.** It shows what asks for attention (late garden care, late tasks,
payments without a category, unread reports), the chosen gainr portfolio's value and today's
move, gripr's "safe to move out today", today's agenda (taskr's own tasks ticked off in place) and
tonight's meal, each linking to its module, plus quick-add buttons. gainr Home moves to `/gainr`;
an old `/?position=…` link is sent on to `/gainr?position=…`, and every position link in the app
now comes from one helper (`positionPath`). The Android app loads the root URL, so it opens on
Vandaag too.

**One endpoint, hosted by taskr: `GET /api/taskr/today?portfolio_id=`.**
`taskr_today_service.build_today` asks each module for its own figures through its services and
repositories, the way taskr's agenda already does (ADR 0038): `taskr_agenda_service.build_agenda`
for today, `performance_service.get_range(…, "1D")` for the portfolio, `gripr_overview_service.
balance_forecast` for the money, `briefr_report_repo`, `gripr_transaction_repo`, `listr_list_repo`
and `listr_meal_plan_repo` for the counts. Nothing is stored; it's derived on every request. The
portfolio is the one the reader has picked (the first one without it), so nothing sums across
portfolios (ADR 0019). The server returns numbers; the page only words them.

**The module switcher shows what waits.** On a phone it opens a sheet of module tiles, Vandaag
first, each with a short line and a count (uncategorised payments, garden care due, today's
workouts, unread reports); a dot on the switcher says something waits elsewhere. On a wider screen
the header's menu carries the same counts. Both read the same request as Vandaag (`useToday`), so
they agree.

**taskr has no tile any more.** Its agenda is on Vandaag, with a link to the full agenda at
`/taskr`, which stays as it was. A module bar with one tab or none is no longer shown on a phone.

**Vandaag belongs to no module**, so it has a neutral ink "brand" (`.module-vandaag` in
index.css) rather than a module colour, and the copy is Dutch like taskr's.

## Alternatives considered

- **Keep gainr Home as the root and put Vandaag at `/vandaag`.** No links to change, but the app
  and the Android wrapper would still open on one module's page, which is what this fixes.
- **Let the page call each module's API itself.** Five or six requests per page load and the
  counting logic in the frontend, against the rule that logic lives in the backend.
- **A notification bell per module.** It would cover counts but not "what's today", and bells
  only show inside their own module.

## Consequences

- One more request on every page (the switcher's counts), cached for two minutes and shared with
  Vandaag. It replays nothing heavy: the portfolio series is the cached one (ADR 0001).
- A bookmark of gainr Home at `/` now opens Vandaag; gainr is one tap away in the switcher.
- A new module that has something waiting adds a count to `TodayCountsOut` and a line to the
  switcher's `moduleStatus`.
