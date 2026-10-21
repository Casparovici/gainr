"""trainr's weekly gym plan, from the database: the last three weeks of home-gym sessions, the
exercise list and the coming week's planner go into trainr_plan's rules, and the sessions that
come out are added to the planner as planned workouts (docs/adr/0046)."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.trainr_exercise import TrainrEquipment
from app.models.trainr_workout import TrainrActivityType, TrainrWorkout
from app.repositories import trainr_exercise_repo, trainr_workout_repo
from app.services.trainr_plan import Exercise, Performance, PlannedSession, Target, WeekPlan, plan_week

GYM = TrainrActivityType.HOME_GYM
# `source_ref` of a session the plan added, so a second run in the same week never adds it twice.
SOURCE_PREFIX = "briefr:weekplan"
WINDOW_DAYS = 21


def next_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def source_ref(plan_monday: date, key: str) -> str:
    return f"{SOURCE_PREFIX}:{plan_monday.isoformat()}:{key}"


def _history(workouts: list[TrainrWorkout]) -> dict[int, list[Performance]]:
    """Per exercise, one performance per session (its heaviest entry, then most reps), newest
    first."""
    history: dict[int, list[Performance]] = {}
    for workout in sorted(workouts, key=lambda w: (w.date, w.id), reverse=True):
        best = {}
        for entry in workout.entries:
            key = (entry.weight_kg or 0, entry.reps or 0, entry.duration_seconds or 0)
            if entry.exercise_id not in best or key > best[entry.exercise_id][0]:
                best[entry.exercise_id] = (key, entry)
        for exercise_id, (_, entry) in best.items():
            history.setdefault(exercise_id, []).append(Performance(
                day=workout.date, sets=entry.sets, reps=entry.reps, weight_kg=entry.weight_kg,
                duration_seconds=entry.duration_seconds,
            ))
    return history


def build_plan(db: Session, today: date) -> WeekPlan:
    """The plan for the week after `today`, from the three weeks up to and including `today`."""
    monday = next_monday(today)
    done = trainr_workout_repo.list_range(db, today - timedelta(days=WINDOW_DAYS - 1), today, GYM, completed=True)
    exercises = [
        Exercise(e.id, e.name, e.muscle_group, e.equipment) for e in trainr_exercise_repo.list_exercises(db)
    ]
    week = trainr_workout_repo.list_range(db, monday, monday + timedelta(days=6))
    sports = [(w.date, w.activity_type) for w in week if w.activity_type != GYM]
    # Gym sessions you planned yourself stay, and count towards the three. The plan's own, from
    # an earlier run this week, don't: they're the same proposal again.
    taken = sorted({w.date for w in week if w.activity_type == GYM and not (w.source_ref or "").startswith(SOURCE_PREFIX)})
    return plan_week(monday, exercises, _history(done), len(done), sports, taken)


UNWEIGHTED = (TrainrEquipment.BODYWEIGHT, TrainrEquipment.PULL_UP_BAR)


def needs_weight(target: Target) -> bool:
    """A new exercise done with a weight: you pick the starting weight yourself."""
    return target.last is None and bool(target.reps) and target.exercise.equipment not in UNWEIGHTED


def _entry_note(target: Target) -> str | None:
    last = target.last
    if last is None:
        return "Nieuw: kies een gewicht waarmee de laatste herhalingen zwaar zijn" if needs_weight(target) else "Nieuw"
    return f"Vorige keer ({last.day.strftime('%d-%m')}): {target.change}"[:200]


def add_to_planner(db: Session, plan: WeekPlan) -> list[tuple[PlannedSession, bool]]:
    """Adds each session as a planned home-gym workout, unless this week's run already did (then
    it's left as it is, with whatever you changed). Returns each session and whether it was added."""
    refs = {source_ref(plan.monday, s.kind.key): s for s in plan.sessions}
    existing = trainr_workout_repo.existing_source_refs(db, set(refs))
    outcomes = []
    for ref, session in refs.items():
        if ref in existing:
            outcomes.append((session, False))
            continue
        trainr_workout_repo.create_workout(
            db,
            entries=[
                dict(exercise_id=t.exercise.id, sets=t.sets, reps=t.reps, weight_kg=t.weight_kg,
                     duration_seconds=t.duration_seconds, notes=_entry_note(t))
                for t in session.targets
            ],
            activity_type=GYM, date=session.day, is_completed=False, source_ref=ref,
            notes=f"Voorstel uit briefr: {session.kind.title.lower()}, zo'n 45 minuten.",
        )
        outcomes.append((session, True))
    return outcomes
