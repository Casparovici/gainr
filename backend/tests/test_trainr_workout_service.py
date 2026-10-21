from datetime import date
from decimal import Decimal

import pytest

from app.models.trainr_exercise import TrainrEquipment, TrainrExercise, TrainrMuscleGroup
from app.models.trainr_workout import TrainrActivityType, TrainrWorkout, TrainrWorkoutEntry
from app.schemas.trainr import TrainrWorkoutEntryIn, TrainrWorkoutIn
from app.services import trainr_workout_service as svc


def make_workout(activity=TrainrActivityType.RUNNING, distance=None, duration=None, entries=(), day=date(2026, 10, 1)):
    w = TrainrWorkout(activity_type=activity, date=day, is_completed=True, distance_km=distance, duration_seconds=duration)
    w.entries = list(entries)
    return w


def make_entry(exercise_id=1, sets=None, reps=None, weight=None, workout_id=1):
    return TrainrWorkoutEntry(exercise_id=exercise_id, workout_id=workout_id, sets=sets, reps=reps, weight_kg=weight)


def make_exercise(id_=1, name="Dumbbell press"):
    return TrainrExercise(id=id_, name=name, muscle_group=TrainrMuscleGroup.CHEST, equipment=TrainrEquipment.DUMBBELL, is_archived=False)


def test_avg_speed_is_distance_over_time_in_kmh():
    assert svc.avg_speed_kmh(Decimal("10"), 3000) == Decimal("12.0")  # 10 km in 50 min
    assert svc.avg_speed_kmh(Decimal("42.2"), 3 * 3600 + 30 * 60) == Decimal("12.1")


def test_avg_speed_and_pace_need_both_distance_and_time():
    assert svc.avg_speed_kmh(None, 3000) is None
    assert svc.avg_speed_kmh(Decimal("5"), None) is None
    assert svc.pace_seconds_per_km(Decimal("0"), 3000) is None
    assert svc.pace_seconds_per_km(Decimal("5"), 0) is None


def test_pace_is_whole_seconds_per_km():
    assert svc.pace_seconds_per_km(Decimal("5"), 1500) == 300  # 5:00 /km
    assert svc.pace_seconds_per_km(Decimal("3"), 1000) == 333  # 5:33.3 rounds to 5:33


def test_volume_sums_sets_reps_weight_and_skips_incomplete_entries():
    workout = make_workout(
        TrainrActivityType.HOME_GYM,
        entries=[
            make_entry(sets=3, reps=10, weight=Decimal("12.5")),  # 375
            make_entry(sets=4, reps=8, weight=Decimal("20")),  # 640
            make_entry(sets=3, reps=15),  # push-ups, no weight
        ],
    )
    assert svc.workout_volume_kg(workout) == Decimal("1015.00")


def test_volume_is_none_without_any_weighted_entry():
    assert svc.workout_volume_kg(make_workout(TrainrActivityType.HOME_GYM, entries=[make_entry(sets=3, reps=15)])) is None


def test_validate_rejects_distance_on_home_gym_and_exercises_on_a_run():
    with pytest.raises(svc.TrainrValidationError):
        svc.validate(TrainrWorkoutIn(activity_type="home_gym", date=date(2026, 10, 1), distance_km=Decimal("5")))
    with pytest.raises(svc.TrainrValidationError):
        svc.validate(
            TrainrWorkoutIn(activity_type="running", date=date(2026, 10, 1), entries=[TrainrWorkoutEntryIn(exercise_id=1)])
        )
    # The matching combinations pass.
    svc.validate(TrainrWorkoutIn(activity_type="cycling", date=date(2026, 10, 1), distance_km=Decimal("40"), max_speed_kmh=Decimal("45.5")))
    svc.validate(TrainrWorkoutIn(activity_type="home_gym", date=date(2026, 10, 1), entries=[TrainrWorkoutEntryIn(exercise_id=1)]))


def test_summarize_totals_per_activity_in_enum_order():
    workouts = [
        make_workout(TrainrActivityType.CYCLING, Decimal("40"), 5400),
        make_workout(TrainrActivityType.RUNNING, Decimal("10"), 3000),
        make_workout(TrainrActivityType.RUNNING, Decimal("5"), 1500),
        make_workout(TrainrActivityType.RUNNING, Decimal("3"), None),  # no time: counts for distance, not speed
        make_workout(TrainrActivityType.HOME_GYM, None, 2700, entries=[make_entry(sets=3, reps=10, weight=Decimal("10"))]),
    ]

    summary = svc.summarize(workouts, date(2026, 10, 1), date(2026, 10, 31))

    assert summary.workouts == 5
    assert summary.total_duration_seconds == 5400 + 3000 + 1500 + 2700
    assert [a.activity_type for a in summary.by_activity] == [
        TrainrActivityType.HOME_GYM,
        TrainrActivityType.RUNNING,
        TrainrActivityType.CYCLING,
    ]
    gym, running, cycling = summary.by_activity
    assert gym.total_volume_kg == Decimal("300.00") and gym.total_distance_km is None
    assert running.workouts == 3
    assert running.total_distance_km == Decimal("18")
    assert running.avg_speed_kmh == Decimal("12.0")  # 15 km in 75 min; the untimed 3 km left out
    assert cycling.avg_speed_kmh == Decimal("26.7")


def test_summarize_with_no_workouts_is_empty():
    summary = svc.summarize([], date(2026, 10, 1), date(2026, 10, 31))
    assert summary.workouts == 0 and summary.by_activity == []


def test_exercise_stats_last_time_and_best_weight():
    press, squat, unused = make_exercise(1), make_exercise(2, "Goblet squat"), make_exercise(3, "Plank")
    entries = [  # newest first, as the repo returns them
        (make_entry(1, 3, 10, Decimal("14"), workout_id=3), date(2026, 10, 10)),
        (make_entry(1, 2, 6, Decimal("16"), workout_id=3), date(2026, 10, 10)),
        (make_entry(2, 3, 12, Decimal("20"), workout_id=2), date(2026, 10, 5)),
        (make_entry(1, 3, 10, Decimal("12"), workout_id=1), date(2026, 10, 1)),
    ]

    rows = {r.id: r for r in svc.exercise_stats([press, squat, unused], entries)}

    assert rows[1].last_performed_on == date(2026, 10, 10)
    assert (rows[1].last_sets, rows[1].last_reps, rows[1].last_weight_kg) == (3, 10, Decimal("14"))
    assert rows[1].best_weight_kg == Decimal("16")
    assert rows[1].times_performed == 2  # two sessions, not three entries
    assert rows[2].times_performed == 1
    assert rows[3].times_performed == 0 and rows[3].last_performed_on is None


def match(activity=TrainrActivityType.FOOTBALL, duration=None, kcal=None, avg=None, peak=None):
    w = make_workout(activity, duration=duration)
    w.calories_kcal, w.avg_heart_rate_bpm, w.max_heart_rate_bpm = kcal, avg, peak
    return w


def test_football_and_padel_take_time_calories_and_heart_rate():
    for activity in ("football", "padel"):
        svc.validate(
            TrainrWorkoutIn(
                activity_type=activity, date=date(2026, 10, 1), duration_seconds=5400,
                calories_kcal=820, avg_heart_rate_bpm=148, max_heart_rate_bpm=187,
            )
        )


def test_football_and_padel_reject_distance_speed_and_exercises():
    for extra in ({"distance_km": Decimal("5")}, {"max_speed_kmh": Decimal("20")}, {"entries": [TrainrWorkoutEntryIn(exercise_id=1)]}):
        with pytest.raises(svc.TrainrValidationError):
            svc.validate(TrainrWorkoutIn(activity_type="padel", date=date(2026, 10, 1), **extra))


def test_calories_and_heart_rate_are_only_for_football_and_padel():
    for activity in ("running", "cycling", "home_gym"):
        with pytest.raises(svc.TrainrValidationError):
            svc.validate(TrainrWorkoutIn(activity_type=activity, date=date(2026, 10, 1), calories_kcal=500))
        with pytest.raises(svc.TrainrValidationError):
            svc.validate(TrainrWorkoutIn(activity_type=activity, date=date(2026, 10, 1), avg_heart_rate_bpm=140))


def test_the_average_heart_rate_cannot_exceed_the_maximum():
    with pytest.raises(svc.TrainrValidationError):
        svc.validate(TrainrWorkoutIn(activity_type="football", date=date(2026, 10, 1), avg_heart_rate_bpm=170, max_heart_rate_bpm=150))
    svc.validate(TrainrWorkoutIn(activity_type="football", date=date(2026, 10, 1), avg_heart_rate_bpm=150, max_heart_rate_bpm=150))


def test_average_heart_rate_is_weighted_by_time_and_skips_untimed_sessions():
    sessions = [
        match(duration=5400, avg=150),  # 90 min
        match(duration=1800, avg=130),  # 30 min
        match(avg=200),  # no time: left out
        match(duration=3600),  # no heart rate: left out
    ]
    assert svc.weighted_avg_heart_rate(sessions) == 145  # (150*90 + 130*30) / 120
    assert svc.weighted_avg_heart_rate([match(duration=3600)]) is None


def test_calories_and_peak_heart_rate_are_none_when_nothing_was_recorded():
    assert svc.total_calories([match(), match()]) is None
    assert svc.peak_heart_rate([match(), match()]) is None
    assert svc.total_calories([match(kcal=500), match(kcal=300), match()]) == 800
    assert svc.peak_heart_rate([match(peak=180), match(peak=191)]) == 191


def test_summarize_includes_match_figures_after_the_distance_activities():
    workouts = [
        match(TrainrActivityType.PADEL, duration=3600, kcal=600, avg=140, peak=170),
        match(TrainrActivityType.FOOTBALL, duration=5400, kcal=900, avg=150, peak=188),
        match(TrainrActivityType.FOOTBALL, duration=5400, kcal=700, avg=140, peak=181),
    ]

    football, padel = svc.summarize(workouts, date(2026, 10, 1), date(2026, 10, 31)).by_activity

    assert (football.activity_type, padel.activity_type) == (TrainrActivityType.FOOTBALL, TrainrActivityType.PADEL)
    assert football.workouts == 2 and football.total_calories_kcal == 1600
    assert football.avg_heart_rate_bpm == 145 and football.max_heart_rate_bpm == 188
    assert football.total_distance_km is None and football.total_volume_kg is None
    assert padel.total_calories_kcal == 600 and padel.max_heart_rate_bpm == 170
