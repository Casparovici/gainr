from datetime import date, timedelta
from decimal import Decimal

from app.models.trainr_exercise import TrainrEquipment as Eq, TrainrMuscleGroup as G
from app.models.trainr_workout import TrainrActivityType as A
from app.services.trainr_plan import PLANNED_SETS, Exercise, Performance, choose_days, next_target, plan_week

D = Decimal
MONDAY = date(2026, 10, 26)
PRESS = Exercise(1, "Dumbbell press", G.CHEST, Eq.DUMBBELL)
SQUAT = Exercise(2, "Barbell back squat", G.LEGS, Eq.BARBELL)
PUSHUP = Exercise(3, "Push-up", G.CHEST, Eq.BODYWEIGHT)
PLANK = Exercise(4, "Plank", G.CORE, Eq.BODYWEIGHT)


def perf(reps=None, kg=None, sets=3, seconds=None, day=date(2026, 10, 20)):
    return Performance(day=day, sets=sets, reps=reps, weight_kg=D(kg) if kg is not None else None, duration_seconds=seconds)


def test_weighted_exercises_follow_double_progression_between_8_and_12():
    assert (t := next_target(PRESS, [perf(10, 16)], False)).reps == 11 and t.weight_kg == D(16) and t.change == "+1 herhaling"
    assert (t := next_target(PRESS, [perf(12, 16)], False)).reps == 8 and t.weight_kg == D(18) and t.change == "+2 kg"
    assert (t := next_target(SQUAT, [perf(12, 40)], False)).weight_kg == D("42.5") and t.change == "+2,5 kg"
    assert (t := next_target(PRESS, [perf(6, 20)], False)).reps == 8 and t.weight_kg == D(20)
    assert next_target(PRESS, [perf(10, 16)], True).sets == 4  # a lagging group gets an extra set


def test_bodyweight_adds_reps_then_a_set_and_holds_add_seconds():
    assert next_target(PUSHUP, [perf(12)], False).reps == 13
    assert (t := next_target(PUSHUP, [perf(15)], False)).sets == 4 and t.reps == 15 and t.change == "+1 set"
    assert (t := next_target(PLANK, [perf(seconds=40)], False)).duration_seconds == 45 and t.change == "+5 s"
    assert next_target(PLANK, [perf(seconds=90)], False).change == "zelfde"


def test_a_new_exercise_starts_at_three_by_ten_or_a_30_second_hold():
    assert (t := next_target(PRESS, [], False)).reps == 10 and t.weight_kg is None and t.change == "nieuw"
    assert next_target(PLANK, [], False).duration_seconds == 30


def test_sessions_avoid_sport_days_and_legs_the_day_before_one():
    padel_tuesday = [(MONDAY + timedelta(days=1), A.PADEL)]
    placed = {kind.key: day for kind, day in choose_days(MONDAY, padel_tuesday, [], 3)}
    assert MONDAY + timedelta(days=1) not in placed.values()
    assert placed["B"] != MONDAY  # the leg session isn't the day before padel
    days = sorted(placed.values())
    assert all((b - a).days > 1 for a, b in zip(days, days[1:]))  # a rest day between gym days


def test_an_upper_body_session_may_go_the_day_before_a_sport():
    padel_tuesday = [(MONDAY + timedelta(days=1), A.PADEL)]
    placed = choose_days(MONDAY, padel_tuesday, [], 3)
    assert placed[0][1] == MONDAY and placed[0][0].key == "A"


def test_a_quiet_week_gets_monday_wednesday_friday_and_taken_days_count():
    assert [d.weekday() for _, d in choose_days(MONDAY, [], [], 3)] == [0, 2, 4]
    placed = choose_days(MONDAY, [], [MONDAY + timedelta(days=2)], 2)
    assert len(placed) == 2 and MONDAY + timedelta(days=2) not in [d for _, d in placed]
    assert choose_days(MONDAY, [], [], 0) == []


def catalogue():
    exercises, n = [], 10
    for group in (G.CHEST, G.BACK, G.SHOULDERS, G.ARMS, G.LEGS, G.CORE):
        for i in range(4):
            n += 1
            exercises.append(Exercise(n, f"{group.value} {i}", group, Eq.DUMBBELL))
    return [*exercises, Exercise(99, "Burpee", G.FULL_BODY, Eq.BODYWEIGHT)]


def test_the_plan_prefers_familiar_exercises_never_repeats_one_and_skips_conditioning_moves():
    exercises = catalogue()
    chest_2 = next(e for e in exercises if e.name == "chest 2")
    history = {chest_2.id: [perf(10, 14), perf(9, 14, day=date(2026, 10, 13))]}

    plan = plan_week(MONDAY, exercises, history, 2, [], [])

    assert [s.kind.key for s in plan.sessions] == ["A", "B", "C"]
    picked = [t.exercise for s in plan.sessions for t in s.targets]
    assert picked[0] == chest_2  # the chest exercise you actually do comes first
    assert len({e.id for e in picked}) == len(picked)
    assert all(e.muscle_group != G.FULL_BODY for e in picked)
    assert sum(len(s.targets) for s in plan.sessions) == 17


def test_the_two_groups_furthest_behind_get_an_extra_set_and_three_equal_sessions_are_a_plateau():
    exercises = catalogue()
    by_group = {g: [e for e in exercises if e.muscle_group == g] for g in G}
    same = [perf(10, 20, day=date(2026, 10, d)) for d in (20, 13, 6)]
    history = {
        by_group[G.LEGS][0].id: same,  # 9 sets: 3 a week against 12
        by_group[G.CHEST][0].id: [perf(10, 14, sets=6, day=date(2026, 10, d)) for d in (20, 13, 6)],  # 6 a week: on plan
        by_group[G.BACK][0].id: [perf(10, 14, sets=6, day=date(2026, 10, d)) for d in (20, 13, 6)],  # 6 against 9
        by_group[G.SHOULDERS][0].id: [perf(10, 8, sets=4, day=date(2026, 10, d)) for d in (20, 13, 6)],  # 4 against 6
        by_group[G.ARMS][0].id: [perf(10, 8, sets=6, day=date(2026, 10, d)) for d in (20, 13, 6)],  # 6 against 9
        by_group[G.CORE][0].id: [perf(12, sets=7, day=date(2026, 10, d)) for d in (20, 13, 6)],  # 7 against 9
    }
    plan = plan_week(MONDAY, exercises, history, 3, [], [])

    assert plan.sets_per_week[G.LEGS] == D(3) and PLANNED_SETS[G.LEGS] == 12
    # Furthest behind first: legs at 25% of plan; back, shoulders and arms tie at 67% (list order).
    assert plan.lagging == [G.LEGS, G.BACK, G.SHOULDERS, G.ARMS, G.CORE]
    assert G.CHEST not in plan.lagging
    assert plan.boosted == plan.lagging[:2]
    sets_by_group = {t.exercise.muscle_group: t.sets for s in plan.sessions for t in s.targets}
    assert sets_by_group[G.LEGS] == 4 and sets_by_group[G.CHEST] == 3 and sets_by_group[G.CORE] == 3
    assert (by_group[G.LEGS][0], same[0]) in plan.plateaus


def test_without_any_history_nothing_is_lagging_and_a_missing_group_is_noted():
    plan = plan_week(MONDAY, [e for e in catalogue() if e.muscle_group != G.CORE], {}, 0, [], [])
    assert plan.lagging == []
    assert plan.notes == ["Geen oefening voor core in je lijst: dat onderdeel valt weg."]
