"""trainr's weekly gym plan: three sessions of about 45 minutes for the coming week, aimed at muscle
growth, built from the last three weeks of home-gym sessions (docs/adr/0046). Pure, no database:
the history, the exercise list and the week's other sports come in as plain values.

The rules, so a plan can always be explained:

- **Three sessions, fixed in shape.** Bovenlichaam (chest, back, shoulders, two arms, core),
  Onderlichaam (three legs, back, core) and Full body (legs, chest, back, shoulders, arms,
  core). Over the week that's at least two exercises for every muscle group.
- **Exercises you already do come first.** Per slot, the exercise of that muscle group you did
  most often in the last three weeks, not used yet that week; then the rest of the list, in its
  own order. Full-body conditioning moves (burpee, thruster) aren't picked: they don't build
  muscle the way the rest do.
- **Double progression, 8 to 12 reps.** After reaching 12 reps, the weight goes up (2 kg for
  dumbbells, 2.5 kg for a barbell) and the reps drop back to 8; below 12, one rep more at the same
  weight. Bodyweight moves add a rep up to 15, then a set. A timed hold adds 5 seconds.
- **The two groups furthest behind get an extra set.** Of the groups that averaged fewer sets a
  week than the plan gives them, the two furthest behind get 4 sets instead of 3 on their
  exercises. Only two, so a session still fits in 45 minutes.
- **Days around the other sports.** No gym on a day with padel, football, running or cycling, no
  session with leg work on the day before one (the leg session least of all), and rest days
  between gym days where the week allows.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from itertools import combinations, permutations

from app.models.trainr_exercise import TrainrEquipment, TrainrMuscleGroup
from app.models.trainr_workout import TrainrActivityType

G = TrainrMuscleGroup
ZERO = Decimal(0)
WEEKS = 3
REPS_MIN, REPS_MAX, BODYWEIGHT_REPS_MAX = 8, 12, 15
BASE_SETS, EXTRA_SETS = 3, 4
BOOSTED_GROUPS = 2
HOLD_STEP, HOLD_MAX = 5, 90
INCREMENT = {TrainrEquipment.DUMBBELL: Decimal(2), TrainrEquipment.BARBELL: Decimal("2.5"), TrainrEquipment.OTHER: Decimal("2.5")}
# Exercises held for time rather than repeated; only needed for one never done before.
TIMED_HINTS = ("plank", "hold", "carry")


@dataclass(frozen=True)
class SessionKind:
    key: str
    title: str
    slots: tuple[TrainrMuscleGroup, ...]
    legs_heavy: bool


SESSIONS = (
    SessionKind("A", "Bovenlichaam", (G.CHEST, G.BACK, G.SHOULDERS, G.ARMS, G.ARMS, G.CORE), legs_heavy=False),
    SessionKind("B", "Onderlichaam", (G.LEGS, G.LEGS, G.LEGS, G.BACK, G.CORE), legs_heavy=True),
    SessionKind("C", "Full body", (G.LEGS, G.CHEST, G.BACK, G.SHOULDERS, G.ARMS, G.CORE), legs_heavy=False),
)
# Sets a week the plan gives each group at BASE_SETS per exercise: what a lagging group is measured against.
PLANNED_SETS = {group: BASE_SETS * sum(s.slots.count(group) for s in SESSIONS) for group in G if group != G.FULL_BODY}


@dataclass(frozen=True)
class Exercise:
    id: int
    name: str
    muscle_group: TrainrMuscleGroup
    equipment: TrainrEquipment


@dataclass(frozen=True)
class Performance:
    """How an exercise went in one completed session (its heaviest entry that day)."""

    day: date
    sets: int | None
    reps: int | None
    weight_kg: Decimal | None
    duration_seconds: int | None


@dataclass(frozen=True)
class Target:
    exercise: Exercise
    sets: int
    reps: int | None
    weight_kg: Decimal | None
    duration_seconds: int | None
    last: Performance | None
    change: str  # what moved since last time, in Dutch: "+2 kg", "+1 herhaling", "nieuw", ...


@dataclass(frozen=True)
class PlannedSession:
    kind: SessionKind
    day: date
    targets: list[Target]


@dataclass(frozen=True)
class WeekPlan:
    monday: date
    sessions: list[PlannedSession]
    sessions_done: int  # completed gym sessions in the three weeks looked at
    sets_per_week: dict[TrainrMuscleGroup, Decimal]  # averaged over the three weeks
    lagging: list[TrainrMuscleGroup]  # short of the plan, furthest behind first
    boosted: list[TrainrMuscleGroup]  # the ones getting an extra set this week
    plateaus: list[tuple[Exercise, Performance]]  # the same weight and reps three sessions running
    sports: list[tuple[date, TrainrActivityType]]
    taken_days: list[date]  # gym sessions already planned that week, kept as they are
    notes: list[str] = field(default_factory=list)


def _is_timed(exercise: Exercise, last: Performance | None) -> bool:
    if last is not None:
        return last.duration_seconds is not None and not last.reps
    return any(hint in exercise.name.lower() for hint in TIMED_HINTS)


def next_target(exercise: Exercise, history: list[Performance], lagging: bool) -> Target:
    """The next session's sets, reps and weight for one exercise, from its most recent
    performance (`history`, newest first)."""
    last = history[0] if history else None
    sets = EXTRA_SETS if lagging else BASE_SETS
    if _is_timed(exercise, last):
        if last is None:
            return Target(exercise, sets, None, None, 30, None, "nieuw")
        hold = min((last.duration_seconds or 0) + HOLD_STEP, HOLD_MAX)
        change = f"+{hold - (last.duration_seconds or 0)} s" if hold != last.duration_seconds else "zelfde"
        return Target(exercise, sets, None, last.weight_kg, hold, last, change)
    if last is None or last.reps is None:
        return Target(exercise, sets, 10, None, None, last, "nieuw")
    if last.weight_kg:  # weighted: double progression
        if last.reps >= REPS_MAX and exercise.equipment in INCREMENT:
            step = INCREMENT[exercise.equipment]
            return Target(exercise, sets, REPS_MIN, last.weight_kg + step, None, last, f"+{_kg(step)} kg")
        if last.reps < REPS_MIN:
            return Target(exercise, sets, REPS_MIN, last.weight_kg, None, last, "zelfde gewicht, 8 herhalingen")
        reps = min(last.reps + 1, REPS_MAX)
        return Target(exercise, sets, reps, last.weight_kg, None, last, "+1 herhaling" if reps > last.reps else "zelfde")
    if last.reps >= BODYWEIGHT_REPS_MAX:  # bodyweight: reps up to 15, then a set
        more = min(max(last.sets or BASE_SETS, sets) + 1, EXTRA_SETS + 1)
        return Target(exercise, more, BODYWEIGHT_REPS_MAX, None, None, last, "+1 set")
    return Target(exercise, sets, last.reps + 1, None, None, last, "+1 herhaling")


def _kg(value: Decimal) -> str:
    return f"{value.normalize():f}".replace(".", ",")


def _plateau(history: list[Performance]) -> bool:
    recent = history[:3]
    return len(recent) == 3 and len({(p.weight_kg, p.reps, p.duration_seconds) for p in recent}) == 1


def choose_days(
    monday: date, sports: list[tuple[date, TrainrActivityType]], taken: list[date], count: int,
) -> list[tuple[SessionKind, date]]:
    """Which day each session goes on: every choice of `count` free days and every order of the
    sessions is scored, and the lowest score wins (ties: the earliest days, then A-B-C)."""
    if count <= 0:
        return []
    week = [monday + timedelta(days=i) for i in range(7)]
    sport_days = {d for d, _ in sports}
    free = [d for d in week if d not in taken]
    kinds = SESSIONS[:count] if count < len(SESSIONS) else SESSIONS
    best: tuple[int, list[tuple[SessionKind, date]]] | None = None
    for days in combinations(free, min(count, len(free))):
        for order in permutations(kinds, len(days)):
            gym_days = sorted([*days, *taken])
            score = sum(10 for d in days if d in sport_days)
            score += sum(3 for a, b in zip(gym_days, gym_days[1:]) if (b - a).days == 1)
            for kind, day in zip(order, days):
                if day + timedelta(days=1) in sport_days:
                    score += 5 if kind.legs_heavy else (1 if G.LEGS in kind.slots else 0)
            if best is None or score < best[0]:
                best = (score, list(zip(order, days)))
    return sorted(best[1], key=lambda pair: pair[1]) if best else []


def plan_week(
    monday: date,
    exercises: list[Exercise],
    history: dict[int, list[Performance]],
    sessions_done: int,
    sports: list[tuple[date, TrainrActivityType]],
    taken_days: list[date],
) -> WeekPlan:
    """The plan for the week starting `monday`. `history` holds, per exercise id, its
    performances in the last three weeks, newest first; `taken_days` are days that already have a
    gym session planned, which count towards the three."""
    sets_done: dict[TrainrMuscleGroup, int] = {g: 0 for g in PLANNED_SETS}
    by_id = {e.id: e for e in exercises}
    for exercise_id, performances in history.items():
        exercise = by_id.get(exercise_id)
        if exercise is not None and exercise.muscle_group in sets_done:
            sets_done[exercise.muscle_group] += sum(p.sets or 1 for p in performances)
    sets_per_week = {g: Decimal(n) / WEEKS for g, n in sets_done.items()}
    lagging = sorted(
        (g for g in PLANNED_SETS if sessions_done and sets_per_week[g] < PLANNED_SETS[g]),
        key=lambda g: sets_per_week[g] / PLANNED_SETS[g],
    )
    boosted = lagging[:BOOSTED_GROUPS]

    frequency = {exercise_id: len(performances) for exercise_id, performances in history.items()}
    candidates = [e for e in exercises if e.muscle_group != G.FULL_BODY]
    used: set[int] = set()

    def pick(group: TrainrMuscleGroup) -> Exercise | None:
        pool = [e for e in candidates if e.muscle_group == group]
        fresh = [e for e in pool if e.id not in used] or pool
        if not fresh:
            return None
        order = {e.id: i for i, e in enumerate(candidates)}
        choice = sorted(fresh, key=lambda e: (-frequency.get(e.id, 0), order[e.id]))[0]
        used.add(choice.id)
        return choice

    sessions = []
    notes = []
    for kind, day in choose_days(monday, sports, taken_days, len(SESSIONS) - len(taken_days)):
        targets = []
        for group in kind.slots:
            exercise = pick(group)
            if exercise is None:
                notes.append(f"Geen oefening voor {group.value} in je lijst: dat onderdeel valt weg.")
                continue
            targets.append(next_target(exercise, history.get(exercise.id, []), group in boosted))
        sessions.append(PlannedSession(kind, day, targets))

    plateaus = [(by_id[i], h[0]) for i, h in history.items() if i in by_id and _plateau(h)]
    return WeekPlan(
        monday=monday, sessions=sessions, sessions_done=sessions_done, sets_per_week=sets_per_week, lagging=lagging, boosted=boosted,
        plateaus=plateaus, sports=sorted(sports), taken_days=sorted(taken_days), notes=sorted(set(notes)),
    )
