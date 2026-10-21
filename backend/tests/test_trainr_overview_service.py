from datetime import date
from decimal import Decimal

from app.models.trainr_exercise import TrainrEquipment, TrainrExercise, TrainrMuscleGroup
from app.models.trainr_workout import TrainrActivityType, TrainrWorkout, TrainrWorkoutEntry
from app.services import trainr_overview_service as svc

TODAY = date(2026, 10, 14)  # a Wednesday

_ids = iter(range(1, 10_000))


def ride(day, km=None, seconds=None, activity=TrainrActivityType.CYCLING):
    w = TrainrWorkout(
        id=next(_ids), activity_type=activity, date=day, is_completed=True,
        distance_km=Decimal(km) if km is not None else None, duration_seconds=seconds,
    )
    w.entries = []
    return w


def run(day, km, seconds):
    return ride(day, km, seconds, TrainrActivityType.RUNNING)


PRESS = TrainrExercise(id=1, name="Dumbbell press", muscle_group=TrainrMuscleGroup.CHEST, equipment=TrainrEquipment.DUMBBELL)
SQUAT = TrainrExercise(id=2, name="Goblet squat", muscle_group=TrainrMuscleGroup.LEGS, equipment=TrainrEquipment.DUMBBELL)
PLANK = TrainrExercise(id=3, name="Plank", muscle_group=TrainrMuscleGroup.CORE, equipment=TrainrEquipment.BODYWEIGHT)


def gym(day, *entries, seconds=None):
    w = ride(day, None, seconds, TrainrActivityType.HOME_GYM)
    w.entries = [
        TrainrWorkoutEntry(exercise_id=ex.id, exercise=ex, sets=sets, reps=reps, weight_kg=Decimal(kg) if kg is not None else None)
        for ex, sets, reps, kg in entries
    ]
    return w


def tile(tiles, key):
    return next(t for t in tiles if t.key == key)


def test_period_bounds_cut_the_previous_period_at_the_same_point():
    bounds = svc.period_bounds(TODAY)
    assert bounds["week"] == (date(2026, 10, 12), TODAY, date(2026, 10, 5), date(2026, 10, 7))
    assert bounds["month"] == (date(2026, 10, 1), TODAY, date(2026, 9, 1), date(2026, 9, 14))
    assert bounds["year"] == (date(2026, 1, 1), TODAY, date(2025, 1, 1), date(2025, 10, 14))


def test_period_bounds_clamp_to_a_shorter_previous_month_and_leap_day():
    assert svc.period_bounds(date(2026, 3, 31))["month"][3] == date(2026, 2, 28)
    assert svc.period_bounds(date(2028, 2, 29))["year"][3] == date(2027, 2, 28)


def test_tiles_total_km_per_period_against_the_same_point_last_time():
    workouts = [
        ride(date(2025, 6, 1), "50", 7200),  # last year, before 14 Oct
        ride(date(2025, 11, 1), "80", 10800),  # last year, after 14 Oct: not in "year" previous
        ride(date(2026, 9, 10), "40", 5400),  # last month, before the 14th
        ride(date(2026, 10, 6), "30", 3600),  # last week, Tuesday
        ride(date(2026, 10, 9), "20", 2400),  # last week, Friday: after Wednesday
        ride(date(2026, 10, 13), "25", 3000),  # this week
        ride(date(2026, 10, 20), "99", 9000),  # done-but-future-dated: ignored everywhere
    ]

    tiles = svc.tiles(workouts, TODAY)

    week, month, year, all_time = (tile(tiles, k) for k in ("week", "month", "year", "all"))
    assert week.current.distance_km == Decimal("25") and week.previous.distance_km == Decimal("30")
    assert month.current.distance_km == Decimal("75")  # 30 + 20 + 25
    assert month.previous.distance_km == Decimal("40")
    assert year.current.distance_km == Decimal("115")
    assert year.previous.distance_km == Decimal("50")
    assert all_time.current.distance_km == Decimal("245") and all_time.previous is None
    assert all_time.current.workouts == 6
    assert week.current.avg_speed_kmh == Decimal("30.0")


def test_totals_without_distance_or_weight_are_none_not_zero():
    t = svc.totals([ride(TODAY)])
    assert t.distance_km is None and t.volume_kg is None and t.avg_speed_kmh is None
    assert t.workouts == 1


def test_monthly_series_covers_twelve_months_with_empty_ones():
    workouts = [ride(date(2025, 11, 3), "40", 5400), ride(date(2026, 10, 1), "20", 2700), ride(date(2025, 10, 31), "99", 1)]

    series = svc.monthly_series(workouts, TODAY)

    assert [p.period_start for p in series][:2] == [date(2025, 11, 1), date(2025, 12, 1)]
    assert series[-1].period_start == date(2026, 10, 1)
    assert len(series) == 12
    assert series[0].distance_km == Decimal("40")  # October 2025 falls outside the window
    assert series[1].workouts == 0 and series[1].distance_km is None


def test_yearly_series_runs_from_the_first_workout_to_this_year():
    series = svc.yearly_series([ride(date(2023, 5, 1), "10", 1800), ride(date(2026, 1, 2), "12", 2000)], TODAY)
    assert [p.period_start.year for p in series] == [2023, 2024, 2025, 2026]
    assert [p.workouts for p in series] == [1, 0, 0, 1]


def test_yearly_series_with_nothing_is_just_this_year():
    assert [p.period_start.year for p in svc.yearly_series([], TODAY)] == [2026]


def test_running_records_use_pace_and_ignore_a_short_blip():
    workouts = [
        run(date(2026, 1, 1), "10", 3300),  # 5:30 /km, longest
        run(date(2026, 2, 1), "5", 1400),  # 4:40 /km
        run(date(2026, 3, 1), "0.5", 100),  # 3:20 /km but only 500 m
        run(date(2026, 4, 1), "8", 3600),  # longest time
    ]

    records = {r.kind: r for r in svc.records(TrainrActivityType.RUNNING, workouts)}

    assert records["longest_distance"].value == Decimal("10")
    assert records["longest_duration"].value == 3600
    assert records["best_pace"].value == 280
    assert records["best_pace"].date == date(2026, 2, 1)
    assert "fastest_avg_speed" not in records


def test_cycling_records_fastest_average_over_twenty_km():
    workouts = [ride(date(2026, 1, 1), "40", 4800), ride(date(2026, 2, 1), "15", 1500), ride(date(2026, 3, 1), "60", 9000)]
    records = {r.kind: r for r in svc.records(TrainrActivityType.CYCLING, workouts)}
    assert records["fastest_avg_speed"].value == Decimal("30.0")  # the 36 km/h 15 km ride doesn't count
    assert records["longest_distance"].value == Decimal("60")


def test_gym_records_split_and_progress():
    workouts = [
        gym(date(2026, 9, 1), (PRESS, 3, 10, "12"), (SQUAT, 3, 12, "20"), seconds=2400),
        gym(date(2026, 9, 8), (PRESS, 3, 10, "14"), (PRESS, 2, 6, "16"), (PLANK, None, None, None)),
    ]

    records = {r.kind: r for r in svc.records(TrainrActivityType.HOME_GYM, workouts)}
    assert records["heaviest_lift"].value == Decimal("20") and records["heaviest_lift"].detail == "Goblet squat"
    assert records["biggest_volume"].value == Decimal("1080.00")  # 360 + 720
    assert records["longest_duration"].value == 2400

    split = svc.muscle_groups(workouts)
    assert [(s.muscle_group, s.sets) for s in split] == [
        (TrainrMuscleGroup.CHEST, 8),
        (TrainrMuscleGroup.LEGS, 3),
        (TrainrMuscleGroup.CORE, 1),  # no set count still counts once
    ]
    assert split[2].volume_kg is None

    progress = svc.exercise_progress(workouts)
    assert [p.name for p in progress] == ["Dumbbell press", "Goblet squat", "Plank"]
    press = progress[0]
    assert press.sessions == 2 and press.best_weight_kg == Decimal("16")
    assert [(p.date, p.max_weight_kg, p.volume_kg) for p in press.points] == [
        (date(2026, 9, 1), Decimal("12"), Decimal("360")),
        (date(2026, 9, 8), Decimal("16"), Decimal("612")),
    ]
    assert progress[2].best_weight_kg is None


def test_overview_bundles_gym_extras_only_for_gym():
    cycling = svc.overview(TrainrActivityType.CYCLING, [ride(TODAY, "20", 2400)], TODAY)
    assert cycling.muscle_groups == [] and cycling.exercises == []
    assert [t.key for t in cycling.tiles] == ["week", "month", "year", "all"]

    home = svc.overview(TrainrActivityType.HOME_GYM, [gym(TODAY, (PRESS, 3, 10, "12"))], TODAY)
    assert home.exercises[0].name == "Dumbbell press"
    assert home.tiles[0].current.volume_kg == Decimal("360.00")


def match(day, activity=TrainrActivityType.FOOTBALL, seconds=None, kcal=None, avg=None, peak=None):
    w = ride(day, None, seconds, activity)
    w.calories_kcal, w.avg_heart_rate_bpm, w.max_heart_rate_bpm = kcal, avg, peak
    return w


def test_match_records_are_the_longest_session_most_calories_and_highest_heart_rate():
    workouts = [
        match(date(2026, 9, 1), seconds=3600, kcal=600, avg=140, peak=175),
        match(date(2026, 9, 8), seconds=5400, kcal=550, avg=150, peak=190),
        match(date(2026, 9, 15), seconds=4500, kcal=900, avg=145, peak=182),
    ]

    records = {r.kind: r for r in svc.records(TrainrActivityType.FOOTBALL, workouts)}

    assert set(records) == {"longest_duration", "most_calories", "highest_heart_rate"}
    assert records["longest_duration"].value == 5400 and records["longest_duration"].date == date(2026, 9, 8)
    assert records["most_calories"].value == 900 and records["most_calories"].date == date(2026, 9, 15)
    assert records["highest_heart_rate"].value == 190


def test_match_records_skip_what_was_never_recorded():
    assert svc.records(TrainrActivityType.PADEL, [match(date(2026, 9, 1), TrainrActivityType.PADEL)]) == []


def test_match_tiles_carry_calories_and_heart_rate_against_the_same_point_last_week():
    workouts = [
        match(date(2026, 10, 12), seconds=3600, kcal=500, avg=140, peak=170),  # this week (Mon)
        match(date(2026, 10, 13), seconds=3600, kcal=700, avg=160, peak=185),
        match(date(2026, 10, 5), seconds=3600, kcal=400, avg=130, peak=160),  # last week (Mon)
    ]

    week = tile(svc.tiles(workouts, TODAY), "week")

    assert (week.current.workouts, week.current.calories_kcal) == (2, 1200)
    assert (week.current.avg_heart_rate_bpm, week.current.max_heart_rate_bpm) == (150, 185)
    assert (week.previous.workouts, week.previous.calories_kcal, week.previous.avg_heart_rate_bpm) == (1, 400, 130)


def test_a_match_overview_has_no_gym_extras():
    overview = svc.overview(TrainrActivityType.PADEL, [match(date(2026, 10, 12), TrainrActivityType.PADEL, seconds=3600, kcal=500)], TODAY)

    assert overview.muscle_groups == [] and overview.exercises == []
    assert overview.monthly[-1].calories_kcal == 500
