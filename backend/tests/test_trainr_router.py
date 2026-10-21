import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.routers import trainr as trainr_router


@pytest.fixture()
def client(db_session):
    # Only the router under test, rather than app.main -- importing that would run create_all
    # against the real portfolio.db.
    app = FastAPI()
    app.include_router(trainr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def make_exercise(client, name="Dumbbell press", muscle_group="chest") -> int:
    resp = client.post("/api/trainr/exercises", json={"name": name, "muscle_group": muscle_group})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def make_gym_workout(client, exercise_id, date="2026-10-05", completed=True, weight=12.5):
    resp = client.post(
        "/api/trainr/workouts",
        json={
            "activity_type": "home_gym",
            "date": date,
            "is_completed": completed,
            "duration_seconds": 2700,
            "entries": [{"exercise_id": exercise_id, "sets": 3, "reps": 10, "weight_kg": weight}],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_a_run_comes_back_with_derived_speed_and_pace(client):
    resp = client.post(
        "/api/trainr/workouts",
        json={"activity_type": "running", "date": "2026-10-05", "is_completed": True, "distance_km": 10, "duration_seconds": 3000, "max_speed_kmh": 16.2},
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["avg_speed_kmh"] == "12.0"
    assert body["pace_seconds_per_km"] == 300
    assert body["max_speed_kmh"] == "16.2"
    assert body["entries"] == []


def test_a_gym_session_records_exercises_with_their_weight(client):
    press = make_exercise(client)
    body = make_gym_workout(client, press)

    assert body["entries"][0]["exercise_name"] == "Dumbbell press"
    assert body["entries"][0]["weight_kg"] == "12.50"
    assert body["volume_kg"] == "375.00"


def test_a_run_with_exercises_is_rejected(client):
    press = make_exercise(client)
    resp = client.post(
        "/api/trainr/workouts",
        json={"activity_type": "running", "date": "2026-10-05", "entries": [{"exercise_id": press}]},
    )
    assert resp.status_code == 422


def test_an_unknown_exercise_is_rejected(client):
    resp = client.post(
        "/api/trainr/workouts",
        json={"activity_type": "home_gym", "date": "2026-10-05", "entries": [{"exercise_id": 999}]},
    )
    assert resp.status_code == 422


def test_update_replaces_the_entry_list(client):
    press, squat = make_exercise(client), make_exercise(client, "Goblet squat", "legs")
    workout = make_gym_workout(client, press)

    resp = client.put(
        f"/api/trainr/workouts/{workout['id']}",
        json={
            "activity_type": "home_gym",
            "date": "2026-10-05",
            "is_completed": True,
            "entries": [{"exercise_id": squat, "sets": 4, "reps": 8, "weight_kg": 20}, {"exercise_id": press, "sets": 3, "reps": 12}],
        },
    )

    assert resp.status_code == 200
    assert [e["exercise_name"] for e in resp.json()["entries"]] == ["Goblet squat", "Dumbbell press"]


def test_planner_range_and_ticking_a_planned_workout_off(client):
    planned = client.post("/api/trainr/workouts", json={"activity_type": "cycling", "date": "2026-10-07", "distance_km": 40}).json()
    client.post("/api/trainr/workouts", json={"activity_type": "running", "date": "2026-10-20"})

    week = client.get("/api/trainr/workouts", params={"date_from": "2026-10-05", "date_to": "2026-10-11"}).json()
    assert [w["id"] for w in week] == [planned["id"]]
    assert week[0]["is_completed"] is False

    resp = client.put(f"/api/trainr/workouts/{planned['id']}/completed", json={"is_completed": True})
    assert resp.json()["is_completed"] is True
    done = client.get("/api/trainr/workouts", params={"date_from": "2026-10-01", "date_to": "2026-10-31", "completed": True}).json()
    assert [w["id"] for w in done] == [planned["id"]]


def test_summary_counts_completed_workouts_only(client):
    press = make_exercise(client)
    make_gym_workout(client, press, completed=True)
    make_gym_workout(client, press, completed=False)
    client.post(
        "/api/trainr/workouts",
        json={"activity_type": "running", "date": "2026-10-06", "is_completed": True, "distance_km": 5, "duration_seconds": 1500},
    )

    summary = client.get("/api/trainr/summary", params={"date_from": "2026-10-01", "date_to": "2026-10-31"}).json()

    assert summary["workouts"] == 2
    assert summary["total_duration_seconds"] == 2700 + 1500
    assert {a["activity_type"]: a["workouts"] for a in summary["by_activity"]} == {"home_gym": 1, "running": 1}


def test_a_backwards_or_huge_range_is_rejected(client):
    assert client.get("/api/trainr/workouts", params={"date_from": "2026-10-31", "date_to": "2026-10-01"}).status_code == 422
    assert client.get("/api/trainr/summary", params={"date_from": "2000-01-01", "date_to": "2026-10-01"}).status_code == 422


def test_exercise_list_carries_last_time_and_hides_archived(client):
    press = make_exercise(client)
    make_gym_workout(client, press, date="2026-10-01", weight=12)
    make_gym_workout(client, press, date="2026-10-08", weight=14)
    make_gym_workout(client, press, date="2026-10-15", completed=False, weight=30)  # planned: ignored

    row = next(e for e in client.get("/api/trainr/exercises").json() if e["id"] == press)
    assert row["last_performed_on"] == "2026-10-08"
    assert row["last_weight_kg"] == "14.00"
    assert row["best_weight_kg"] == "14.00"
    assert row["times_performed"] == 2

    client.put(f"/api/trainr/exercises/{press}", json={"is_archived": True})
    assert all(e["id"] != press for e in client.get("/api/trainr/exercises").json())
    assert any(e["id"] == press for e in client.get("/api/trainr/exercises", params={"include_archived": True}).json())


def test_exercise_names_are_unique_ignoring_case(client):
    make_exercise(client, "Dumbbell press")
    resp = client.post("/api/trainr/exercises", json={"name": "dumbbell press ", "muscle_group": "chest"})
    assert resp.status_code == 409


def test_a_used_exercise_cannot_be_deleted_but_an_unused_one_can(client):
    used, unused = make_exercise(client), make_exercise(client, "Plank", "core")
    make_gym_workout(client, used)

    assert client.delete(f"/api/trainr/exercises/{used}").status_code == 409
    assert client.delete(f"/api/trainr/exercises/{unused}").status_code == 204


def test_deleting_a_workout(client):
    press = make_exercise(client)
    workout = make_gym_workout(client, press)

    assert client.delete(f"/api/trainr/workouts/{workout['id']}").status_code == 204
    assert client.get(f"/api/trainr/workouts/{workout['id']}").status_code == 404


def test_overview_endpoint(client):
    client.post(
        "/api/trainr/workouts",
        json={"activity_type": "cycling", "date": "2026-01-05", "is_completed": True, "distance_km": 40, "duration_seconds": 4800},
    )
    client.post("/api/trainr/workouts", json={"activity_type": "cycling", "date": "2026-01-06", "distance_km": 99})  # planned

    body = client.get("/api/trainr/overview", params={"activity_type": "cycling"}).json()

    all_time = next(t for t in body["tiles"] if t["key"] == "all")
    assert all_time["current"]["workouts"] == 1
    assert all_time["current"]["distance_km"] == "40.00"
    assert len(body["monthly"]) == 12
    assert {r["kind"] for r in body["records"]} == {"longest_distance", "longest_duration", "fastest_avg_speed"}
    assert client.get("/api/trainr/overview", params={"activity_type": "swimming"}).status_code == 422


def test_renaming_an_exercise_keeps_names_unique_and_required(client):
    press, row = make_exercise(client, "Dumbbell press"), make_exercise(client, "Dumbbell row", "back")

    assert client.put(f"/api/trainr/exercises/{row}", json={"name": " Dumbbell press"}).status_code == 409
    assert client.put(f"/api/trainr/exercises/{row}", json={"name": "   "}).status_code == 422
    assert client.put(f"/api/trainr/exercises/{row}", json={"name": None}).status_code == 422
    renamed = client.put(f"/api/trainr/exercises/{press}", json={"name": " Dumbbell press "})  # its own name
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Dumbbell press"
    assert client.put("/api/trainr/exercises/999", json={"name": "x"}).status_code == 404


def test_a_null_for_a_required_exercise_field_leaves_it_alone(client):
    press = make_exercise(client, "Dumbbell press", "chest")
    updated = client.put(f"/api/trainr/exercises/{press}", json={"muscle_group": None, "is_archived": None}).json()
    assert updated["muscle_group"] == "chest"
    assert updated["is_archived"] is False


def test_a_blank_new_exercise_name_is_refused(client):
    assert client.post("/api/trainr/exercises", json={"name": "   ", "muscle_group": "chest"}).status_code == 422


def test_a_padel_match_round_trips_with_calories_and_heart_rate(client):
    created = client.post(
        "/api/trainr/workouts",
        json={
            "activity_type": "padel", "date": "2026-10-10", "is_completed": True, "duration_seconds": 4500,
            "calories_kcal": 640, "avg_heart_rate_bpm": 138, "max_heart_rate_bpm": 171,
        },
    )

    assert created.status_code == 200
    body = created.json()
    assert (body["calories_kcal"], body["avg_heart_rate_bpm"], body["max_heart_rate_bpm"]) == (640, 138, 171)
    assert body["distance_km"] is None and body["entries"] == []

    updated = client.put(f"/api/trainr/workouts/{body['id']}", json={"activity_type": "padel", "date": "2026-10-10", "is_completed": True, "calories_kcal": 700})
    assert updated.json()["calories_kcal"] == 700 and updated.json()["max_heart_rate_bpm"] is None


def test_calories_on_a_run_or_an_average_above_the_maximum_are_rejected(client):
    run = {"activity_type": "running", "date": "2026-10-10", "calories_kcal": 500}
    assert client.post("/api/trainr/workouts", json=run).status_code == 422
    football = {"activity_type": "football", "date": "2026-10-10", "avg_heart_rate_bpm": 180, "max_heart_rate_bpm": 170}
    assert client.post("/api/trainr/workouts", json=football).status_code == 422
    out_of_range = {"activity_type": "football", "date": "2026-10-10", "max_heart_rate_bpm": 400}
    assert client.post("/api/trainr/workouts", json=out_of_range).status_code == 422


def test_football_has_its_own_summary_and_overview(client):
    client.post(
        "/api/trainr/workouts",
        json={"activity_type": "football", "date": "2026-10-06", "is_completed": True, "duration_seconds": 5400, "calories_kcal": 900, "avg_heart_rate_bpm": 150, "max_heart_rate_bpm": 188},
    )

    summary = client.get("/api/trainr/summary", params={"date_from": "2026-10-01", "date_to": "2026-10-31"}).json()
    (football,) = summary["by_activity"]
    assert (football["activity_type"], football["total_calories_kcal"], football["avg_heart_rate_bpm"]) == ("football", 900, 150)

    overview = client.get("/api/trainr/overview", params={"activity_type": "football"}).json()
    assert {r["kind"] for r in overview["records"]} == {"longest_duration", "most_calories", "highest_heart_rate"}
