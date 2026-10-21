"""trainr: workouts, their derived figures and the history summary.

Average speed, pace and gym volume are derived from what was entered on every read, never
stored -- the same derive-don't-store rule positions and gardnr's due dates follow -- so editing
a workout's distance or time can never leave a stale average behind (docs/adr/0037)."""

from datetime import date as date_
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.trainr_exercise import TrainrExercise
from app.models.trainr_workout import TrainrActivityType, TrainrWorkout, TrainrWorkoutEntry
from app.repositories import trainr_exercise_repo, trainr_workout_repo
from app.schemas.trainr import (
    TrainrActivitySummary,
    TrainrExerciseDemoOut,
    TrainrExerciseOut,
    TrainrSummaryOut,
    TrainrWorkoutEntryOut,
    TrainrWorkoutIn,
    TrainrWorkoutOut,
)
from app.services import trainr_exercise_demo_provider

# Which fields an activity carries. A new activity type joins one of these sets.
DISTANCE_ACTIVITIES = frozenset({TrainrActivityType.RUNNING, TrainrActivityType.CYCLING})
SET_ACTIVITIES = frozenset({TrainrActivityType.HOME_GYM})
# Team and racket sports: a time plus what a watch reports (calories, heart rate), no route or lifts.
MATCH_ACTIVITIES = frozenset({TrainrActivityType.FOOTBALL, TrainrActivityType.PADEL})

SECONDS_PER_HOUR = Decimal(3600)
ONE_DECIMAL = Decimal("0.1")
TWO_DECIMALS = Decimal("0.01")


class TrainrValidationError(ValueError):
    """A workout whose fields don't fit its activity type; the router answers 422."""


# -- pure calculations ------------------------------------------------------------------------


def avg_speed_kmh(distance_km: Decimal | None, duration_seconds: int | None) -> Decimal | None:
    """km/h to one decimal, or None when either side is missing."""
    if not distance_km or not duration_seconds:
        return None
    return (distance_km * SECONDS_PER_HOUR / Decimal(duration_seconds)).quantize(ONE_DECIMAL, ROUND_HALF_UP)


def pace_seconds_per_km(distance_km: Decimal | None, duration_seconds: int | None) -> int | None:
    """Whole seconds per km (a runner's min/km), or None when either side is missing."""
    if not distance_km or not duration_seconds:
        return None
    return int((Decimal(duration_seconds) / distance_km).quantize(Decimal(1), ROUND_HALF_UP))


def entry_volume_kg(entry: TrainrWorkoutEntry) -> Decimal | None:
    """sets x reps x weight, or None when the entry lacks one of them (a plank, a bodyweight set
    with no weight entered)."""
    if entry.sets is None or entry.reps is None or entry.weight_kg is None:
        return None
    return Decimal(entry.sets) * Decimal(entry.reps) * entry.weight_kg


def workout_volume_kg(workout: TrainrWorkout) -> Decimal | None:
    volumes = [v for v in (entry_volume_kg(e) for e in workout.entries) if v is not None]
    if not volumes:
        return None
    return sum(volumes, Decimal(0)).quantize(TWO_DECIMALS, ROUND_HALF_UP)


def weighted_avg_heart_rate(workouts: list[TrainrWorkout]) -> int | None:
    """The sessions' average heart rates weighted by their time, over those that carry both, so a
    5-minute kickabout doesn't count as much as a 90-minute match. Whole bpm."""
    rows = [(w.avg_heart_rate_bpm, w.duration_seconds) for w in workouts if w.avg_heart_rate_bpm and w.duration_seconds]
    seconds = sum(s for _, s in rows)
    if not seconds:
        return None
    return int((Decimal(sum(bpm * s for bpm, s in rows)) / Decimal(seconds)).quantize(Decimal(1), ROUND_HALF_UP))


def total_calories(workouts: list[TrainrWorkout]) -> int | None:
    values = [w.calories_kcal for w in workouts if w.calories_kcal is not None]
    return sum(values) if values else None


def peak_heart_rate(workouts: list[TrainrWorkout]) -> int | None:
    return max((w.max_heart_rate_bpm for w in workouts if w.max_heart_rate_bpm is not None), default=None)


def validate(payload: TrainrWorkoutIn) -> None:
    kind = payload.activity_type
    if kind not in DISTANCE_ACTIVITIES and (payload.distance_km is not None or payload.max_speed_kmh is not None):
        raise TrainrValidationError("Only running and cycling have a distance or speed")
    if kind not in SET_ACTIVITIES and payload.entries:
        raise TrainrValidationError("Only a home gym workout has exercises")
    body = (payload.calories_kcal, payload.avg_heart_rate_bpm, payload.max_heart_rate_bpm)
    if kind not in MATCH_ACTIVITIES and any(v is not None for v in body):
        raise TrainrValidationError("Only football and padel record calories and heart rate")
    avg, peak = payload.avg_heart_rate_bpm, payload.max_heart_rate_bpm
    if avg is not None and peak is not None and avg > peak:
        raise TrainrValidationError("The average heart rate can't be higher than the maximum")


def summarize(workouts: list[TrainrWorkout], date_from: date_, date_to: date_) -> TrainrSummaryOut:
    """Totals per activity type over the given (completed) workouts, in the enum's order and only
    for the types that occur."""
    by_activity: list[TrainrActivitySummary] = []
    for activity in TrainrActivityType:
        rows = [w for w in workouts if w.activity_type == activity]
        if not rows:
            continue
        timed_with_distance = [w for w in rows if w.distance_km and w.duration_seconds]
        distances = [w.distance_km for w in rows if w.distance_km is not None]
        volumes = [v for v in (workout_volume_kg(w) for w in rows) if v is not None]
        by_activity.append(
            TrainrActivitySummary(
                activity_type=activity,
                workouts=len(rows),
                total_duration_seconds=sum(w.duration_seconds or 0 for w in rows),
                total_distance_km=sum(distances, Decimal(0)) if distances else None,
                avg_speed_kmh=avg_speed_kmh(
                    sum((w.distance_km for w in timed_with_distance), Decimal(0)),
                    sum(w.duration_seconds for w in timed_with_distance),
                ),
                total_volume_kg=sum(volumes, Decimal(0)) if volumes else None,
                total_calories_kcal=total_calories(rows),
                avg_heart_rate_bpm=weighted_avg_heart_rate(rows),
                max_heart_rate_bpm=peak_heart_rate(rows),
            )
        )
    return TrainrSummaryOut(
        date_from=date_from,
        date_to=date_to,
        workouts=len(workouts),
        total_duration_seconds=sum(w.duration_seconds or 0 for w in workouts),
        by_activity=by_activity,
    )


def exercise_stats(
    exercises: list[TrainrExercise], entries: list[tuple[TrainrWorkoutEntry, date_]]
) -> list[TrainrExerciseOut]:
    """Each exercise with its last performance and heaviest weight. `entries` must come newest
    first (trainr_workout_repo.list_completed_entries), so an exercise's first entry is its last
    time; done twice in that session, the first entry of the session stands for it."""
    seen: dict[int, TrainrExerciseOut] = {}
    out = []
    for exercise in exercises:
        row = TrainrExerciseOut.model_validate(exercise)
        seen[exercise.id] = row
        out.append(row)
    sessions: dict[int, set[int]] = {}
    for entry, day in entries:
        row = seen.get(entry.exercise_id)
        if row is None:
            continue
        sessions.setdefault(entry.exercise_id, set()).add(entry.workout_id)
        if row.last_performed_on is None:
            row.last_performed_on = day
            row.last_sets = entry.sets
            row.last_reps = entry.reps
            row.last_weight_kg = entry.weight_kg
        if entry.weight_kg is not None and (row.best_weight_kg is None or entry.weight_kg > row.best_weight_kg):
            row.best_weight_kg = entry.weight_kg
    for exercise_id, workout_ids in sessions.items():
        seen[exercise_id].times_performed = len(workout_ids)
    return out


def to_out(workout: TrainrWorkout) -> TrainrWorkoutOut:
    return TrainrWorkoutOut(
        id=workout.id,
        activity_type=workout.activity_type,
        date=workout.date,
        is_completed=workout.is_completed,
        duration_seconds=workout.duration_seconds,
        distance_km=workout.distance_km,
        max_speed_kmh=workout.max_speed_kmh,
        calories_kcal=workout.calories_kcal,
        avg_heart_rate_bpm=workout.avg_heart_rate_bpm,
        max_heart_rate_bpm=workout.max_heart_rate_bpm,
        notes=workout.notes,
        entries=[
            TrainrWorkoutEntryOut(
                id=e.id,
                exercise_id=e.exercise_id,
                exercise_name=e.exercise.name,
                muscle_group=e.exercise.muscle_group,
                sets=e.sets,
                reps=e.reps,
                weight_kg=e.weight_kg,
                duration_seconds=e.duration_seconds,
                notes=e.notes,
            )
            for e in workout.entries
        ],
        avg_speed_kmh=avg_speed_kmh(workout.distance_km, workout.duration_seconds),
        pace_seconds_per_km=pace_seconds_per_km(workout.distance_km, workout.duration_seconds),
        volume_kg=workout_volume_kg(workout),
    )


# -- orchestration ---------------------------------------------------------------------------


def _checked_fields(db: Session, payload: TrainrWorkoutIn) -> tuple[dict, list[dict]]:
    validate(payload)
    entries = [e.model_dump() for e in payload.entries]
    wanted = {e["exercise_id"] for e in entries}
    missing = wanted - trainr_exercise_repo.existing_ids(db, wanted)
    if missing:
        raise TrainrValidationError(f"Unknown exercise id(s): {sorted(missing)}")
    fields = payload.model_dump(exclude={"entries"})
    return fields, entries


def create_workout(db: Session, payload: TrainrWorkoutIn) -> TrainrWorkout:
    fields, entries = _checked_fields(db, payload)
    workout = trainr_workout_repo.create_workout(db, entries=entries, **fields)
    return workout


def update_workout(db: Session, workout: TrainrWorkout, payload: TrainrWorkoutIn) -> TrainrWorkout:
    fields, entries = _checked_fields(db, payload)
    return trainr_workout_repo.update_workout(db, workout, entries=entries, **fields)


def list_exercises_with_stats(db: Session, include_archived: bool = False) -> list[TrainrExerciseOut]:
    exercises = trainr_exercise_repo.list_exercises(db, include_archived=include_archived)
    rows = exercise_stats(exercises, trainr_workout_repo.list_completed_entries(db))
    for row in rows:
        demo = trainr_exercise_demo_provider.get_demo(row.demo_id)
        row.demo = TrainrExerciseDemoOut.model_validate(demo.model_dump()) if demo else None
    return rows


def summary(db: Session, date_from: date_, date_to: date_) -> TrainrSummaryOut:
    workouts = trainr_workout_repo.list_range(db, date_from, date_to, completed=True)
    return summarize(workouts, date_from, date_to)
