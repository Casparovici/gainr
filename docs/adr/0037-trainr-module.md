# 37. trainr: a fifth module for workouts, planned and logged on one row

## Status

Accepted

## Context

The user asked for a module to register workouts: activity types starting with Home Gym, Running
and Cycling; for running and cycling the distance, time, speed and average speed; for home gym
several exercises per session (dumbbell and bar work), from a list of suggestions the user can add
to, with the weight used; a history to look back on; and planning "similar to the week planner in
listr". Everything is entered by hand for now. The name follows the other modules: **trainr**.

## Decisions

**Module boundary**: the gardnr/listr precedent (ADR 0005, 0012) — `trainr_*.py` models,
repositories, service, router and schemas next to the others, `pages/trainr/`,
`components/trainr/`, `api/trainrClient.ts`/`trainrTypes.ts`, one entry in `config/modules.ts` and
`moduleNav.ts`. Dutch UI, like the other household modules. Brand colour blue (`#1769AA`), the one
hue the four existing modules don't use; the glyph is a dumbbell.

**A planned workout and a done workout are the same row.** `trainr_workouts.is_completed` is the
weekplanner's `is_cooked` (ADR 0006): planning puts a row on a date, ticking it off in the planner
moves it into the history and the totals. No separate plan table and no "convert plan into log"
step, so a planned session's exercises are already there when it's done. Unlike the meal plan, a
day can hold any number of workouts (a run in the morning, gym at night), so there is no unique
date.

**Activity types are a closed enum** (`TrainrActivityType`, the `GardenActionType` shape). Each
type decides which fields apply — `DISTANCE_ACTIVITIES` (running, cycling: distance, time, top
speed) and `SET_ACTIVITIES` (home gym: exercises, plus an optional session time) in
`trainr_workout_service` — and the service rejects a workout that mixes them (422). A new activity
joins one of the two sets; one with genuinely new fields would need columns, which is a schema
change and an addendum here.

**Average speed and pace are derived, never stored.** The user listed "speed" and "average speed".
Average speed is distance ÷ time, so storing it would let an edited distance leave a stale average
behind; it's computed on every read (`avg_speed_kmh`, `pace_seconds_per_km`), the
derive-don't-store rule positions and gardnr's due dates follow. "Speed" is stored as
`max_speed_kmh`, the one figure that can't be derived (from a bike computer or watch). Distance
and speeds are `NUMERIC`/`Decimal` like every other unit value; durations are whole seconds in an
integer, which is already exact.

**A gym entry is one line per exercise: sets × reps × weight.** `trainr_workout_entries` holds
`sets`, `reps`, `weight_kg` (`NUMERIC(6,2)`) and `duration_seconds` (for holds like a plank).
Sets that differ in weight are just two entries for the same exercise. A row per *set* would model
pyramids exactly but triples the typing for the common "3 × 10 at 12 kg", and quick manual entry
is the whole point while nothing imports workouts. Volume (sets × reps × kg) is derived like the
speeds.

**The exercise catalogue is an open, user-owned table** (`trainr_exercises`, the `GriprCategory`
shape, not an enum), because the user asked to add their own. It is seeded by the migration with
43 home-gym suggestions across seven muscle groups, tagged with equipment (dumbbells, barbell,
pull-up bar, bodyweight). The seed runs only into an empty table, so re-running the migration never
duplicates one and never resurrects one the user deleted. An exercise used in a workout can be
archived (gone from the picker, still named in the history) but not deleted (409); names are unique
ignoring case.

**"Vorige keer" comes from the backend.** The exercise list carries each exercise's last completed
sets/reps/weight, best weight and session count (`trainr_workout_service.exercise_stats`), computed
from completed entries on read. The workout form shows it under an exercise and starts an untouched
row from those numbers, since the usual next session is "the same, maybe heavier".

**Shared calendar helpers.** listr's Weekplanner kept its date arithmetic inline; trainr's Planner
needs the same, so it moved to `utils/weekCalendar.ts` and both import it. No behaviour change in
listr.

## Alternatives considered

- **A separate plan table** with a "done" action copying into a log: two places for one session,
  and a planned session edited after logging would drift from its log. Rejected for the flag.
- **A row per set**: exact for varying weights, but slower to enter; rejected for v1. If wanted
  later, a `trainr_workout_sets` child of an entry can be added without touching existing rows.
- **Suggested exercises as a hard-coded frontend list**: can't be extended or archived by the user,
  and couldn't carry history. Rejected for the seeded table.
- **Storing average speed** alongside distance and time: rejected as above.

## Consequences

- Totals (`GET /api/trainr/summary`) and "vorige keer" are recomputed from completed workouts on
  every request — fine at one person's scale (a few hundred workouts a year).
- A database booted by `create_all` before the migration runs gets empty trainr tables; the
  migration still seeds them, because it checks for an empty catalogue rather than a missing table.
- Strava (or a watch) could later fill the same columns; that would be a `*_provider.py` adapter and
  its own ADR, not a schema change.

## Addendum: football and padel

Two more activity types, **football** and **padel**, recorded as a time plus what a watch
reports: total calories, average heart rate and maximum heart rate. This is the schema change the
decision above anticipated for "genuinely new fields": three nullable integer columns on
`trainr_workouts` (`calories_kcal`, `avg_heart_rate_bpm`, `max_heart_rate_bpm`), added by an
idempotent migration. The enum itself needs no DDL, since SQLAlchemy stores it as plain text
without a CHECK constraint.

- **A third field set, `MATCH_ACTIVITIES`**, next to `DISTANCE_ACTIVITIES` and `SET_ACTIVITIES`.
  The service rejects (422) distance or speed on anything but running/cycling, exercises on
  anything but home gym, calories or heart rate on anything but football/padel, and an average
  heart rate above the maximum. Ranges: 1–20,000 kcal, 30–250 bpm.
- **The body figures are not offered to running and cycling**, although a watch records them
  there too: they were asked for football and padel only, and widening it later is deleting one
  validation rule.
- **Totals derive on read like everything else.** Calories add up; the average heart rate over
  several sessions is weighted by session time (a 10-minute kickabout counts for less than a
  match) and skips sessions missing either figure; the maximum is the highest of the maxes. Match
  records are the longest session, most calories and highest heart rate.
- **The activity picker is a native dropdown** (`ActivitySelect`) in the overview, the history
  filter and the workout form. Five activities plus "all" no longer fit side by side on a phone.
- Football and padel have no guided runner and no exercises; the planner treats a planned match
  as a plain entry to tick off.

## Addendum: importing rides and runs from a Strava export

The user wanted a batch of past rides and runs from Strava. Two routes were offered — the
claude.ai Strava connector (not authorised in this environment) or Strava's own account
archive — and the user chose the archive. `scripts/import_strava.py` takes the emailed `.zip` (or
the `activities.csv` inside it); `trainr_strava_import` parses it and books each ride (Ride,
Virtual Ride, E-Bike Ride, Gravel/Mountain Bike Ride) as Fietsen and each run (Run, Trail Run,
Virtual Run) as Hardlopen, done, with the activity's name as the note. Other types are skipped and
counted in the report. Weight training is skipped too, since Strava records no exercises for it.

- **A file, not an API, so no provider adapter.** Nothing calls Strava, there's no key to keep,
  and the import is a one-off script like `import_transactions`. A live sync would be a
  `strava_provider.py` with OAuth credentials in the environment and its own ADR.
- **Idempotent through `trainr_workouts.source_ref`** (`strava:<activity id>`, nullable, unique),
  the `source_ref` pattern gainr's imports use. Re-running with a newer export adds only new
  activities. A workout edited in the app keeps its ref, because the form never sends one. A
  workout deleted in the app does come back on the next import, which is acceptable for a
  deliberate, manual run.
- **Moving time, not elapsed time.** Strava's own average speed uses moving time, so trainr's
  derived average matches what Strava shows. Elapsed time is the fallback when moving time is
  blank.
- **Units from the raw block.** The export repeats `Distance`/`Elapsed Time`: first in display
  units, then in metres and seconds next to `Moving Time` and `Max Speed` (m/s). The importer
  reads the raw columns. A file with a single `Distance` column (older exports) is read as km.
  Dates are UTC and are moved to Amsterdam's calendar day, as the Trading 212 sync does. English
  and Dutch month names are both accepted, since the export follows the account's language.

## Addendum: an overview page per activity

`GET /api/trainr/overview?activity_type=…` returns one activity's whole dashboard, computed by
`trainr_overview_service` from that activity's done workouts on every request (no cache):

- Period tiles (this week, month, year, all time) that compare against **the previous period up
  to the same point**: Monday to Wednesday last week against Monday to Wednesday this week, 1–14
  September against 1–14 October. A period still running is never set against a complete one.
  Month and year ends are clamped (31 March against 28 February, a leap day against 28 February).
- Series per month (the last 12, empty months included) and per year (from the first workout),
  each with distance, average speed and pace over the workouts that have both a distance and a
  time, plus count, time and volume.
- Records. A "fastest" record needs a real outing — at least 20 km for a ride and 3 km for a run
  — so a short GPS blip can't hold it. Top speed isn't a record, because imported Strava data
  carries GPS spikes (149 km/h on a bike).
- For home gym: sets and volume per muscle group (an entry without a set count counts as one
  set), and per exercise one point per session with the heaviest weight and the volume.

Everything the tiles show comes from the backend. The frontend only formats it and works out the
"+12 km" difference between two numbers it was given.

## Addendum: running a planned gym session

A planned home gym workout can be run step by step (`WorkoutRunner`, started from the play button
on its planner chip). It is a frontend feature on top of the existing model -- **no schema or API
change**: the plan's entries (sets, reps, weight, hold time) already say what to do, and finishing
saves through the same `PUT /api/trainr/workouts/{id}`.

- **One step per set.** `trainrRunner.buildSteps` flattens "3 × 10 at 12,5 kg" into three steps;
  the planned numbers are the starting point and can be nudged per set (reps ±1, weight ±2,5 kg).
- **Results fold back into entries.** `entriesFromResults` merges neighbouring identical sets of
  one exercise into a single entry and gives a set that came out different its own entry, the same
  shape the form uses for sets that differ in weight. Skipped sets and exercises with no done set
  are dropped, so the saved workout is what was done, not what was planned.
- **Saved as done today.** The date becomes the day it was run, `duration_seconds` the wall-clock
  time of the session, and the workout's notes are kept.
- **Timers use timestamps**, not a counted interval, so a backgrounded tab or a throttled phone
  shows the right time when it comes back. The screen wake lock and a short vibration at the end of
  a rest are used where the device supports them and skipped silently elsewhere.
- **Progress is not persisted mid-session.** Closing the runner or reloading the page loses what was
  ticked off (stopping asks first). Persisting it would need either browser storage or a
  server-side session row; neither is worth adding until losing a session turns out to hurt.
- **Time per exercise.** The runner measures how long each counted set took, from the moment the
  set began (session start, the end of the previous rest, or a skip) until it was ticked off, so
  rests never count. An entry's existing `duration_seconds` then holds the **total active time of
  that entry's sets**; merging identical sets adds their times up. For a timed hold the field keeps
  its original meaning, the time of *one* set (`3 × 0:45`), which is why equal holds still merge and
  a hold's time is the time actually held. Sets ticked off in bulk ("Oefening afvinken") carry no
  time except the one that was in progress, and a set with no reps and no hold stays untimed, since a
  time on a repless entry would read as per set. No schema change: the column and its 1 s–24 h limit
  already existed.
- The rest length is a constant (90 s, extendable by 15 s during a rest), not a setting.
