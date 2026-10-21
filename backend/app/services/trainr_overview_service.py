"""trainr: one activity's dashboard -- period tiles, monthly and yearly series, records, and for
home gym the muscle-group split and per-exercise progress.

Everything is derived on each request from the activity's done workouts (a few hundred at most),
the same derive-don't-store rule as the rest of trainr; there's no cache (docs/adr/0037)."""

import calendar
from collections.abc import Iterable
from datetime import date as date_, timedelta
from decimal import Decimal

from app.models.trainr_workout import TrainrActivityType, TrainrWorkout
from app.schemas.trainr import (
    TrainrExerciseProgress,
    TrainrExerciseProgressPoint,
    TrainrMuscleGroupShare,
    TrainrOverviewOut,
    TrainrPeriodTile,
    TrainrPeriodTotals,
    TrainrRecord,
    TrainrSeriesPoint,
)
from app.services.trainr_workout_service import (
    DISTANCE_ACTIVITIES,
    MATCH_ACTIVITIES,
    SET_ACTIVITIES,
    avg_speed_kmh,
    entry_volume_kg,
    pace_seconds_per_km,
    peak_heart_rate,
    total_calories,
    weighted_avg_heart_rate,
    workout_volume_kg,
)

# A "fastest" record only counts a proper outing, so a 400 m GPS blip can't hold it.
MIN_DISTANCE_FOR_SPEED_RECORD = {
    TrainrActivityType.CYCLING: Decimal(20),
    TrainrActivityType.RUNNING: Decimal(3),
}


def _timed(workouts: Iterable[TrainrWorkout]) -> tuple[Decimal, int]:
    """Total distance and time over the workouts that carry both -- the basis for an average
    speed that isn't skewed by a ride logged without a time."""
    distance, seconds = Decimal(0), 0
    for w in workouts:
        if w.distance_km and w.duration_seconds:
            distance += w.distance_km
            seconds += w.duration_seconds
    return distance, seconds


def totals(workouts: list[TrainrWorkout]) -> TrainrPeriodTotals:
    distances = [w.distance_km for w in workouts if w.distance_km is not None]
    volumes = [v for v in (workout_volume_kg(w) for w in workouts) if v is not None]
    distance, seconds = _timed(workouts)
    return TrainrPeriodTotals(
        workouts=len(workouts),
        duration_seconds=sum(w.duration_seconds or 0 for w in workouts),
        distance_km=sum(distances, Decimal(0)) if distances else None,
        avg_speed_kmh=avg_speed_kmh(distance, seconds),
        volume_kg=sum(volumes, Decimal(0)) if volumes else None,
        calories_kcal=total_calories(workouts),
        avg_heart_rate_bpm=weighted_avg_heart_rate(workouts),
        max_heart_rate_bpm=peak_heart_rate(workouts),
    )


def _between(workouts: list[TrainrWorkout], start: date_ | None, end: date_) -> list[TrainrWorkout]:
    return [w for w in workouts if (start is None or w.date >= start) and w.date <= end]


def _same_day_in(year: int, month: int, day: int) -> date_:
    """`day` of the given month, clamped to its length (31 March -> 28/29 February)."""
    return date_(year, month, min(day, calendar.monthrange(year, month)[1]))


def period_bounds(today: date_) -> dict[str, tuple[date_, date_, date_, date_]]:
    """Per period: (start, end, previous start, previous end), the previous one cut at the same
    point as today is in the current one."""
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    year_start = date_(today.year, 1, 1)
    return {
        "week": (week_start, today, week_start - timedelta(days=7), today - timedelta(days=7)),
        "month": (
            month_start,
            today,
            prev_month_start,
            _same_day_in(prev_month_start.year, prev_month_start.month, today.day),
        ),
        "year": (year_start, today, date_(today.year - 1, 1, 1), _same_day_in(today.year - 1, today.month, today.day)),
    }


def tiles(workouts: list[TrainrWorkout], today: date_) -> list[TrainrPeriodTile]:
    out = [
        TrainrPeriodTile(
            key=key,
            date_from=start,
            date_to=end,
            current=totals(_between(workouts, start, end)),
            previous=totals(_between(workouts, prev_start, prev_end)),
        )
        for key, (start, end, prev_start, prev_end) in period_bounds(today).items()
    ]
    out.append(TrainrPeriodTile(key="all", date_from=None, date_to=today, current=totals(_between(workouts, None, today)), previous=None))
    return out


def _point(period_start: date_, workouts: list[TrainrWorkout]) -> TrainrSeriesPoint:
    t = totals(workouts)
    distance, seconds = _timed(workouts)
    return TrainrSeriesPoint(
        period_start=period_start,
        workouts=t.workouts,
        duration_seconds=t.duration_seconds,
        distance_km=t.distance_km,
        avg_speed_kmh=t.avg_speed_kmh,
        pace_seconds_per_km=pace_seconds_per_km(distance, seconds),
        volume_kg=t.volume_kg,
        calories_kcal=t.calories_kcal,
        avg_heart_rate_bpm=t.avg_heart_rate_bpm,
    )


def monthly_series(workouts: list[TrainrWorkout], today: date_, months: int = 12) -> list[TrainrSeriesPoint]:
    starts = []
    year, month = today.year, today.month
    for _ in range(months):
        starts.append(date_(year, month, 1))
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    starts.reverse()
    by_month: dict[date_, list[TrainrWorkout]] = {s: [] for s in starts}
    for w in workouts:
        key = w.date.replace(day=1)
        if key in by_month and w.date <= today:
            by_month[key].append(w)
    return [_point(s, by_month[s]) for s in starts]


def yearly_series(workouts: list[TrainrWorkout], today: date_) -> list[TrainrSeriesPoint]:
    past = [w for w in workouts if w.date <= today]
    first_year = min((w.date.year for w in past), default=today.year)
    return [_point(date_(y, 1, 1), [w for w in past if w.date.year == y]) for y in range(first_year, today.year + 1)]


def _best(workouts: Iterable[TrainrWorkout], key, lowest: bool = False) -> tuple[TrainrWorkout, Decimal] | None:
    """The workout with the highest (or lowest) value of `key`, the earliest on a tie."""
    best: tuple[TrainrWorkout, Decimal] | None = None
    for w in workouts:
        value = key(w)
        if value is None:
            continue
        if best is None or (value < best[1] if lowest else value > best[1]):
            best = (w, Decimal(value))
    return best


def records(activity_type: TrainrActivityType, workouts: list[TrainrWorkout]) -> list[TrainrRecord]:
    out: list[TrainrRecord] = []

    def add(kind: str, found: tuple[TrainrWorkout, Decimal] | None, detail: str | None = None) -> None:
        if found is not None:
            out.append(TrainrRecord(kind=kind, value=found[1], workout_id=found[0].id, date=found[0].date, detail=detail))

    if activity_type in DISTANCE_ACTIVITIES:
        add("longest_distance", _best(workouts, lambda w: w.distance_km))
        add("longest_duration", _best(workouts, lambda w: w.duration_seconds))
        threshold = MIN_DISTANCE_FOR_SPEED_RECORD.get(activity_type, Decimal(0))
        eligible = [w for w in workouts if w.distance_km and w.distance_km >= threshold and w.duration_seconds]
        if activity_type == TrainrActivityType.RUNNING:
            add("best_pace", _best(eligible, lambda w: pace_seconds_per_km(w.distance_km, w.duration_seconds), lowest=True))
        else:
            add("fastest_avg_speed", _best(eligible, lambda w: avg_speed_kmh(w.distance_km, w.duration_seconds)))
        return out

    if activity_type in MATCH_ACTIVITIES:
        add("longest_duration", _best(workouts, lambda w: w.duration_seconds))
        add("most_calories", _best(workouts, lambda w: w.calories_kcal))
        add("highest_heart_rate", _best(workouts, lambda w: w.max_heart_rate_bpm))
        return out

    heaviest: tuple[TrainrWorkout, Decimal, str] | None = None
    for w in workouts:
        for e in w.entries:
            if e.weight_kg is not None and (heaviest is None or e.weight_kg > heaviest[1]):
                heaviest = (w, e.weight_kg, e.exercise.name)
    if heaviest is not None:
        add("heaviest_lift", (heaviest[0], heaviest[1]), detail=heaviest[2])
    add("biggest_volume", _best(workouts, workout_volume_kg))
    add("longest_duration", _best(workouts, lambda w: w.duration_seconds))
    return out


def muscle_groups(workouts: list[TrainrWorkout]) -> list[TrainrMuscleGroupShare]:
    """Sets and volume per muscle group, most sets first. An entry without a set count still
    counts as one set: it was done."""
    sets: dict = {}
    volume: dict = {}
    for w in workouts:
        for e in w.entries:
            group = e.exercise.muscle_group
            sets[group] = sets.get(group, 0) + (e.sets or 1)
            v = entry_volume_kg(e)
            if v is not None:
                volume[group] = volume.get(group, Decimal(0)) + v
    rows = [TrainrMuscleGroupShare(muscle_group=g, sets=n, volume_kg=volume.get(g)) for g, n in sets.items()]
    return sorted(rows, key=lambda r: (-r.sets, r.muscle_group.value))


def exercise_progress(workouts: list[TrainrWorkout]) -> list[TrainrExerciseProgress]:
    """Per exercise, one point per session it was done in: the heaviest weight and the volume.
    Most-done exercise first."""
    by_exercise: dict[int, dict] = {}
    for w in workouts:
        per_session: dict[int, list] = {}
        for e in w.entries:
            per_session.setdefault(e.exercise_id, []).append(e)
        for exercise_id, entries in per_session.items():
            weights = [e.weight_kg for e in entries if e.weight_kg is not None]
            volumes = [v for v in (entry_volume_kg(e) for e in entries) if v is not None]
            row = by_exercise.setdefault(exercise_id, {"name": entries[0].exercise.name, "points": []})
            row["points"].append(
                TrainrExerciseProgressPoint(
                    date=w.date,
                    max_weight_kg=max(weights) if weights else None,
                    volume_kg=sum(volumes, Decimal(0)) if volumes else None,
                )
            )
    out = []
    for exercise_id, row in by_exercise.items():
        weights = [p.max_weight_kg for p in row["points"] if p.max_weight_kg is not None]
        out.append(
            TrainrExerciseProgress(
                exercise_id=exercise_id,
                name=row["name"],
                sessions=len(row["points"]),
                best_weight_kg=max(weights) if weights else None,
                points=row["points"],
            )
        )
    return sorted(out, key=lambda r: (-r.sessions, r.name))


def overview(activity_type: TrainrActivityType, workouts: list[TrainrWorkout], today: date_) -> TrainrOverviewOut:
    """`workouts` are the activity's done workouts, oldest first (trainr_workout_repo.list_completed)."""
    is_gym = activity_type in SET_ACTIVITIES
    return TrainrOverviewOut(
        activity_type=activity_type,
        today=today,
        tiles=tiles(workouts, today),
        monthly=monthly_series(workouts, today),
        yearly=yearly_series(workouts, today),
        records=records(activity_type, workouts),
        muscle_groups=muscle_groups(workouts) if is_gym else [],
        exercises=exercise_progress(workouts) if is_gym else [],
    )
