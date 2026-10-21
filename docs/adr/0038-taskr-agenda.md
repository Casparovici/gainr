# 38. taskr: a read-only agenda over the other modules

## Status

Accepted, with an addendum (2026-10-18) for tasks taskr owns. The endpoint and the Agenda page (`/taskr`) are built; see "The page" below.

## Context

Things the user has to do are spread over the modules: gardnr's care schedules, trainr's planned
workouts, listr's meal plan. "What do I need to do this week?" means
opening each of them. The user asked for a module that combines the tasks of all modules into one
overview and helps plan.

## Decisions

**taskr owns no copy of anyone's tasks.** It is a read-only aggregation layer, derived on every
request, the same rule positions and gardnr's due dates follow. A stored copy of "water the
tomatoes" would drift the moment the care is logged in gardnr. Completing an item happens in the
module that owns it, through the `link` the item carries.

**One item shape, one provider per module.** Each module contributes through a service with the
same signature, `agenda_items(db, date_to, today) -> list[AgendaItemOut]`, returning everything
due on or before `date_to` (overdue included): `garden_agenda_service` and
`trainr_agenda_service`. `taskr_agenda_service` calls them and merges. This is the architect
rule's "go through services and repositories, never router to router"; taskr imports the modules,
never the other way round, so there is no cycle. These are not `*_provider.py` files because that
suffix is reserved for external vendors.

**Only things the reader has to do are on the agenda.** A care action or a planned workout is
something to do and tick off. gripr's recurring payments were built as a first provider and then
removed: they book by themselves, so they are not a to-do, and they cluttered the list. Dates
that are information only (dividends, earnings) are left out for the same reason. Items therefore
have no `kind`; if something that isn't a to-do is ever wanted, add the field back with it.

**Overdue is relative to the requested range.** `GET /api/taskr/agenda?date_from=&date_to=` returns
`overdue` (due before `date_from`, oldest first) and `days` (one entry per day that has something
due in the range). A week view starting next Monday therefore still lists what slipped before it.
The range is capped at 366 days.

**Planned workouts only count as overdue for 14 days.** An unticked session planned months ago is
history nobody will log, and would otherwise sit on the agenda forever.

## The page

taskr is a sixth module in the frontend (`config/modules.ts`, a berry brand colour `#A3307A`,
its own logo and favicon), with one page, **Agenda** at `/taskr`:

- **Range views**: Dag (1 day), Week (7 days) and Maand (30 days). Each is a window that starts
  on the selected day, today by default, and runs forward; previous/next move by a whole window
  and "Naar vandaag" returns. A window starting today (rather than a Monday-based week or a
  calendar month, as trainr's planner uses) keeps every day in it still ahead, so what slipped
  is all in the overdue list instead of spread over past days of the week.
- The backend's `overdue` list comes first. It is titled "Achterstallig" when the range starts
  today or earlier; for a window further ahead it also holds items that are not late yet, so it
  is titled "Vóór deze periode" there, and each item's own `is_overdue` marks the late ones.
- Then one card per day the backend returns. Every line shows its module (the module's glyph and
  name in its brand colour), title and detail, with an open circle. The only action is a link, "Open in <module>", to
  the item's `link`.
- The agenda query is always refetched when the page opens (`staleTime: 0`): completing happens
  in another module, whose mutations don't invalidate taskr's query.

## Not in this slice

- listr's meal plan as a fourth provider.
- User-created tasks. These are the one thing taskr would own, so they need a table and an
  addendum here.
- Rescheduling and snoozing. gardnr's due dates are computed from the care log, so postponing one
  needs an override stored somewhere; decide that before building it.

## Consequences

- No schema change and no migration.
- A new module that has dates the reader acts on adds one `*_agenda_service` and one entry in
  `_PROVIDERS`.
- Each request queries every provider; at this data size that is a handful of cheap queries.

## Addendum (2026-10-18): tasks taskr owns

The user wanted to add tasks that don't come from a module ("bel de loodgieter") straight in taskr.
These are the user-created tasks "Not in this slice" set aside, and the one thing taskr owns.

- **A table, `taskr_tasks`**: title, optional notes, a due date and `completed_at`. No other module
  has these tasks, so storing them copies nothing, and the rule above, "taskr owns no copy of
  anyone's tasks", still holds for the modules' items.
- **Every task has a day.** The agenda is a list of days, and the quick-add row on top fills in the
  first day on screen, so adding one stays a title and Enter. An undated backlog and repeating
  tasks are left out for now. A repeating task would need its own schedule and next-due logic
  (gardnr's is computed from the care log), and an undated one would need a section outside the
  days.
- **Same provider signature.** `taskr_task_service.agenda_items(db, date_to, today)` sits in
  `_PROVIDERS` next to the modules' services, with the source `taskr`. Its items carry
  `task_id` instead of a `link` (`link` is now optional), and the frontend uses that to tell a
  task, ticked off right on the agenda, from a module's item, which still only links out.
- **No lookback.** Unlike a planned workout, an open task stays overdue however long ago it was
  due, because nothing else will ever close it.
- **Ticking off stamps `completed_at`** rather than deleting the row, so the undo toast is one
  call back. Deleting is a separate action in the task's dialog, behind a confirm. Endpoints:
  `POST /api/taskr/tasks`, `PUT /api/taskr/tasks/{id}` (a null title or date leaves it, a null
  note clears it), `PUT /api/taskr/tasks/{id}/completed`, `DELETE /api/taskr/tasks/{id}`.

Consequence: taskr now has a schema (migration `a3c7e1f9b5d2`), so "No schema change and no
migration" above no longer holds.
