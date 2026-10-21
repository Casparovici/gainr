# 46. A weekly gym plan from fixed rules on the server, put straight into trainr's planner

## Status

Accepted. Builds on [ADR 0044](0044-briefr-agent-reports.md) and [ADR 0045](0045-briefr-performance-reports.md).

## Context

The owner wants an agent that looks at the last three weeks of home-gym workouts in trainr every
Sunday, and proposes the coming week's sessions. The owner's answers:

- **Sessions:** plan all three gym sessions of the week, about 45 minutes each.
- **Goal:** muscle growth.
- **Exercises:** trainr's exercise list is everything the owner can do at home.
- **Restrictions:** no injuries to work around.
- **Other sports:** padel, football, running and cycling in the planner should shape the plan.
- **Privacy:** the workout history must **not** go to the agents repository on GitHub.
- **Output:** a report in briefr and the sessions in trainr's planner, in Dutch like trainr, on
  Sunday at 12:00.

The privacy answer rules out a cloud agent like the holdings scan (ADR 0044): it can only read
what's in the repository. Planning with a model through the API from the server was offered and
declined in favour of fixed rules that keep the data on the server.

## Decisions

**Rules on the server, like the performance reports.** `scripts/briefr_trainr_plan.py` runs from
`briefr-trainr.timer` on Sunday at 12:00 Amsterdam time. It plans the week from the next Monday to
the next Sunday, adds the sessions to trainr's planner, and writes the report into briefr as agent
`trainr-weekplan`, keyed `server/trainr-weekplan/<monday>`. Nothing leaves the server.

**The rules** (`trainr_plan.py`, pure and tested):

- **Three sessions, fixed in shape:** Bovenlichaam (chest, back, shoulders, two arms, core),
  Onderlichaam (three legs, back, core) and Full body (legs, chest, back, shoulders, arms, core).
  Over the week, every muscle group gets at least two exercises.
- **Exercises you already do come first.** For each slot, the exercise of that group done most
  often in the three weeks, and not used yet that week; then the rest of the list in its own
  order. Full-body conditioning moves (burpee, thruster) aren't picked for a muscle-growth plan.
- **Double progression, 8 to 12 reps:**
  - at 12 reps, the weight goes up (2 kg for dumbbells, 2.5 kg for a barbell) and the reps drop
    back to 8; below 12, one rep more at the same weight;
  - bodyweight moves add a rep up to 15, then a set;
  - timed holds add 5 seconds, up to 90;
  - a new exercise starts at 3 × 10 (or a 30-second hold), with the weight left for you to pick.
- **Extra sets, sparingly.** The two muscle groups furthest behind the plan's own weekly sets over
  the three weeks get 4 sets instead of 3. Only two, so a session still fits in about 45 minutes.
- **Days around the other sports:** no gym on a day with another sport in the planner. The leg
  session is never on the day before one, and the full-body session avoids it when it can. Rest
  days between gym days where the week allows; otherwise the earliest days.
- **Your own planned sessions stay.** A gym session you planned yourself that week counts towards
  the three, and its day is left alone.

**The sessions go into the planner as planned workouts** (not ticked off), with each exercise's
sets, reps and weight filled in, and a note with the change since last time. They carry
`source_ref = briefr:weekplan:<monday>:<A|B|C>`, so a second run that week adds nothing and never
overwrites what you changed. Doing them is the existing trainr flow: tick them off or start the
guided workout, and what you actually lifted becomes next week's history.

**The report is in Dutch, like trainr:**

- the last three weeks: sessions, and sets per week per muscle group against the plan;
- the week, session by session, with what changed and why;
- the other sports it planned around;
- the rules, in two sentences.

It's flagged "watch" when there was no gym session in the three weeks, when a group gets an extra
set, or when an exercise has stood still three sessions running.

**The rules belong to trainr.** `trainr_plan.py` and `trainr_plan_service.py` do the planning and
the planner writes. `briefr_trainr_service.py` only words the report and calls them, the same split
as gainr's period figures in ADR 0045.

## Alternatives considered

- **A cloud agent reading an exported history:** declined by the owner. The history stays off GitHub.
- **A model through the Claude API, run from the server:** smarter variety, but the history would
  still leave the server, it needs an API key, and it costs per run. It can be added later, on top
  of the same history and planner code, if the rules prove too plain.
- **Report only, without touching the planner:** the owner wanted the sessions ready in trainr;
  they're easy to move or delete there.
- **Two alternative plans to choose from:** asked, and the owner meant the sessions of one week,
  not alternatives.

## Consequences

- Every Sunday afternoon there are three planned gym sessions in trainr, unless the week already
  has three, and one briefr report.
- The plan is only as good as what's logged. A session done but not ticked off, or logged without
  weights, starts that exercise from scratch.
- The shape is fixed. Changing the split, the rep range or the session length is a code change in
  `trainr_plan.py`, with its tests.
