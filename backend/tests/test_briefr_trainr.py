from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.trainr_exercise import TrainrEquipment as Eq, TrainrExercise, TrainrMuscleGroup as G
from app.models.trainr_workout import TrainrActivityType as A, TrainrWorkout, TrainrWorkoutEntry
from app.repositories import briefr_report_repo, trainr_workout_repo
from app.services import briefr_trainr_service, trainr_plan_service
from scripts import briefr_trainr_plan

D = Decimal
SUNDAY = date(2026, 10, 25)
MONDAY = date(2026, 10, 26)
NOW = datetime(2026, 10, 25, 11, 0)


@pytest.fixture()
def gym(db_session):
    names = {
        G.CHEST: ["Dumbbell press", "Push-up"], G.BACK: ["One-arm dumbbell row", "Pull-up"],
        G.SHOULDERS: ["Dumbbell shoulder press", "Lateral raise"], G.ARMS: ["Hammer curl", "Triceps kickback"],
        G.LEGS: ["Goblet squat", "Dumbbell lunge", "Romanian deadlift", "Calf raise"], G.CORE: ["Plank", "Crunch"],
    }
    exercises = {}
    for group, group_names in names.items():
        for name in group_names:
            equipment = Eq.BODYWEIGHT if name in ("Push-up", "Plank", "Crunch") else (
                Eq.PULL_UP_BAR if name == "Pull-up" else Eq.DUMBBELL)
            exercises[name] = TrainrExercise(name=name, muscle_group=group, equipment=equipment)
    db_session.add_all(exercises.values())
    db_session.flush()

    def session(day, *entries, completed=True, activity=A.HOME_GYM, ref=None):
        workout = TrainrWorkout(activity_type=activity, date=day, is_completed=completed, source_ref=ref)
        workout.entries = [TrainrWorkoutEntry(exercise_id=exercises[n].id, sort_order=i, sets=s, reps=r,
                                              weight_kg=D(kg) if kg else None, duration_seconds=sec)
                           for i, (n, s, r, kg, sec) in enumerate(entries)]
        db_session.add(workout)
        db_session.flush()
        return workout

    session(date(2026, 10, 13), ("Dumbbell press", 3, 10, 16, None), ("Goblet squat", 3, 12, 20, None))
    session(date(2026, 10, 20), ("Dumbbell press", 3, 11, 16, None), ("Dumbbell press", 1, 6, 12, None),
            ("Plank", 3, None, None, 40))
    session(date(2026, 10, 23), ("Dumbbell press", 3, 12, 16, None))
    session(date(2026, 9, 1), ("Hammer curl", 3, 10, 10, None))  # older than three weeks: ignored
    session(MONDAY.replace(day=27), activity=A.PADEL, completed=False)  # padel on Tuesday
    return exercises, session


def planned(db):
    week = trainr_workout_repo.list_range(db, MONDAY, date(2026, 11, 1), A.HOME_GYM, completed=False)
    return {w.date: w for w in week}


def test_sunday_plans_three_sessions_into_the_planner_around_padel(db_session, gym):
    plan, added, outcome = briefr_trainr_service.run(db_session, SUNDAY, NOW)

    assert (added, outcome) == (3, "created")
    sessions = planned(db_session)
    assert len(sessions) == 3 and date(2026, 10, 27) not in sessions  # no gym on padel day
    leg_day = next(s.day for s in plan.sessions if s.kind.key == "B")
    assert leg_day != MONDAY  # no legs the day before padel
    assert all(w.source_ref.startswith("briefr:weekplan:2026-10-26:") for w in sessions.values())

    upper = next(w for w in sessions.values() if w.source_ref.endswith(":A"))
    press = next(e for e in upper.entries if e.exercise.name == "Dumbbell press")
    # Hit 12 reps at 16 kg: up to 18 kg. Chest is behind too, but back and shoulders (none at all)
    # are further behind and get the extra set.
    assert (press.sets, press.reps, press.weight_kg) == (3, 8, D(18))
    assert press.notes == "Vorige keer (23-10): +2 kg"
    plank = next(e for e in upper.entries if e.exercise.name == "Plank")
    assert plank.duration_seconds == 45 and plank.reps is None


def test_the_report_explains_the_weeks_plan_in_dutch(db_session, gym):
    briefr_trainr_service.run(db_session, SUNDAY, NOW)
    report = briefr_report_repo.get_by_source_path(db_session, "server/trainr-weekplan/2026-10-26")

    assert report.agent == "trainr-weekplan"
    assert report.title.startswith("Weekplan 26 okt – 1 nov: ")
    assert report.summary.startswith("3 sessies van zo'n 45 minuten staan in je planner.")
    assert "3 gym-sessies, gemiddeld 1 per week." in report.body
    assert "| Oefening | Deze keer | Vorige keer | Verandering |\n|---|---|---|---|" in report.body
    assert "| **Dumbbell press** | 3 × 8 × 18 kg | 3 × 12 × 16 kg | +2 kg |" in report.body
    assert "| **Pull-up** | 4 × 10 | – | nieuw |" in report.body  # bodyweight: no weight to choose
    assert "| **One-arm dumbbell row** | 4 × 10 | – | nieuw: kies een startgewicht |" in report.body
    assert "- Dinsdag 27 okt: padel" in report.body
    assert report.attention.value == "watch"
    assert [i.headline for i in report.items] == [
        "Rug: 0 sets per week, het plan geeft 9", "Schouders: 0 sets per week, het plan geeft 6",
    ]
    assert "Het verst achter: rug en schouders, die krijgen een set extra." in report.summary


def test_a_second_run_adds_nothing_and_keeps_your_changes(db_session, gym):
    briefr_trainr_service.run(db_session, SUNDAY, NOW)
    first = planned(db_session)
    moved = next(iter(first.values()))
    moved.notes = "verzet naar zaterdag"

    _, added, outcome = briefr_trainr_service.run(db_session, SUNDAY, datetime(2026, 10, 25, 13, 0))

    assert (added, outcome) == (0, "updated")  # the summary now says the sessions were already there
    assert len(planned(db_session)) == 3 and moved.notes == "verzet naar zaterdag"


def test_your_own_planned_gym_session_stays_and_counts(db_session, gym):
    _, session = gym
    session(date(2026, 10, 28), ("Goblet squat", 3, 10, 20, None), completed=False)

    plan, added, _ = briefr_trainr_service.run(db_session, SUNDAY, NOW)

    assert added == 2 and plan.taken_days == [date(2026, 10, 28)]
    assert len(planned(db_session)) == 3


def test_an_empty_history_still_plans_and_says_so(db_session):
    db_session.add_all([TrainrExercise(name=f"{g.value}", muscle_group=g, equipment=Eq.DUMBBELL)
                        for g in (G.CHEST, G.BACK, G.SHOULDERS, G.ARMS, G.LEGS, G.CORE)])
    db_session.flush()
    plan, added, _ = briefr_trainr_service.run(db_session, SUNDAY, NOW)
    report = briefr_report_repo.get_by_source_path(db_session, "server/trainr-weekplan/2026-10-26")

    assert added == 3 and plan.sessions_done == 0
    assert report.items[0].headline == "Geen gym-sessies in de afgelopen 3 weken"
    entry = planned(db_session)[MONDAY].entries[0]
    assert (entry.sets, entry.reps, entry.weight_kg) == (3, 10, None)
    assert entry.notes.startswith("Nieuw: kies een gewicht")


def test_next_monday_is_always_the_coming_week():
    assert trainr_plan_service.next_monday(SUNDAY) == MONDAY
    assert trainr_plan_service.next_monday(MONDAY) == date(2026, 11, 2)


def test_the_script_plans_the_week_after_the_given_day(db_session, gym, monkeypatch, capsys):
    class Unclosed:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            pass

    monkeypatch.setattr(briefr_trainr_plan, "SessionLocal", Unclosed)
    assert briefr_trainr_plan.main(["--date", "2026-10-25"], now=NOW) == 0
    out = capsys.readouterr().out
    assert out.startswith("trainr weekplan for the week of 2026-10-26: ") and "3 added to the planner; report created" in out
