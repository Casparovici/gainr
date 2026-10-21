from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.routers import trainr as trainr_router
from app.services import trainr_exercise_demo_provider as demos

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEMOS_REVISION = "f2b8d4a6c1e7"


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(trainr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


# -- the catalogue ----------------------------------------------------------------------------


def test_a_demo_has_its_photos_pinned_to_one_commit_and_its_steps():
    demo = demos.get_demo("Dumbbell_Bench_Press")

    assert demo.name == "Dumbbell Bench Press"
    assert len(demo.image_urls) == 2
    assert all(url.startswith("https://cdn.jsdelivr.net/gh/yuhonas/free-exercise-db@") for url in demo.image_urls)
    assert demo.image_urls[0].endswith("/exercises/Dumbbell_Bench_Press/0.jpg")
    assert demo.instructions


def test_an_unknown_or_missing_demo_id_is_no_demo():
    assert demos.get_demo("Not_An_Exercise") is None
    assert demos.get_demo(None) is None


def test_search_puts_the_exact_name_first_then_the_shortest():
    names = [d.name for d in demos.search("barbell curl", limit=5)]

    assert names[0] == "Barbell Curl"
    assert all("barbell" in n.lower() and "curl" in n.lower() for n in names)  # full matches before partial ones


def test_search_ignores_punctuation_case_and_a_plural():
    assert demos.search("PUSH-UPS")[0].id == "Pushups"
    assert "Hammer_Curls" in [d.id for d in demos.search("hammer curl")]


def test_search_still_finds_the_rest_of_a_name_with_a_typo_in_it():
    assert "Dumbbell_Shoulder_Press" in [d.id for d in demos.search("Dumbell Shoulder Press", limit=3)]


def test_search_with_no_words_finds_nothing():
    assert demos.search("  -  ") == []


# -- linking an exercise ----------------------------------------------------------------------


def test_an_exercise_links_a_demo_and_lists_it_resolved(client):
    created = client.post("/api/trainr/exercises", json={"name": "Dumbbell press", "muscle_group": "chest", "demo_id": "Dumbbell_Bench_Press"})
    assert created.status_code == 200, created.text

    row = client.get("/api/trainr/exercises").json()[0]
    assert row["demo_id"] == "Dumbbell_Bench_Press"
    assert row["demo"]["name"] == "Dumbbell Bench Press"
    assert len(row["demo"]["image_urls"]) == 2


def test_a_demo_can_be_changed_and_unlinked(client):
    exercise_id = client.post("/api/trainr/exercises", json={"name": "Curl", "muscle_group": "arms"}).json()["id"]

    linked = client.put(f"/api/trainr/exercises/{exercise_id}", json={"demo_id": "Hammer_Curls"}).json()
    assert linked["demo"]["id"] == "Hammer_Curls"

    renamed = client.put(f"/api/trainr/exercises/{exercise_id}", json={"name": "Hammer curl"}).json()
    assert renamed["demo_id"] == "Hammer_Curls"  # a field left out leaves the demo alone

    unlinked = client.put(f"/api/trainr/exercises/{exercise_id}", json={"demo_id": None}).json()
    assert unlinked["demo_id"] is None
    assert unlinked["demo"] is None


def test_a_demo_that_is_not_in_the_catalogue_is_refused(client):
    resp = client.post("/api/trainr/exercises", json={"name": "Mystery", "muscle_group": "core", "demo_id": "../../etc/passwd"})

    assert resp.status_code == 422


def test_the_search_endpoint_returns_demos_to_pick_from(client):
    body = client.get("/api/trainr/exercise-demos", params={"q": "plank", "limit": 3}).json()

    assert body[0]["id"] == "Plank"
    assert len(body) <= 3
    assert set(body[0]) == {"id", "name", "equipment", "image_urls", "instructions"}


# -- the migration ----------------------------------------------------------------------------


def _alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = url
    return config


def test_the_migration_links_the_seeded_and_renamed_suggestions_but_keeps_a_users_pick(tmp_path):
    url = f"sqlite:///{tmp_path / 'trainr.db'}"
    config = _alembic_config(url)
    command.upgrade(config, "e5a1c7d9b3f4")  # the ADR 0037 seed is in
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE trainr_exercises SET name = 'Push Up' WHERE name = 'Push-up'"))
        connection.execute(sa.text("UPDATE trainr_exercises SET name = 'Dumbbell Bicep Curl' WHERE name = 'Dumbbell biceps curl'"))
        connection.execute(sa.text("INSERT INTO trainr_exercises (name, muscle_group, equipment, is_archived) VALUES ('Zercher squat', 'LEGS', 'BARBELL', 0)"))

    command.upgrade(config, DEMOS_REVISION)

    with engine.connect() as connection:
        linked = dict(connection.execute(sa.text("SELECT name, demo_id FROM trainr_exercises")).all())
    assert linked["Push Up"] == "Pushups"
    assert linked["Dumbbell Bicep Curl"] == "Dumbbell_Bicep_Curl"
    assert linked["Plank"] == "Plank"
    assert linked["Burpee"] is None
    assert linked["Zercher squat"] is None
    # Every id the migration writes exists in the vendored catalogue.
    assert all(demos.get_demo(d) is not None for d in linked.values() if d)

    # Run again over a database that already has the column (as create_all builds it): a demo the
    # user picked stays, an unlinked suggestion is still linked.
    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE trainr_exercises SET demo_id = 'Incline_Push-Up' WHERE name = 'Push Up'"))
        connection.execute(sa.text("UPDATE trainr_exercises SET demo_id = NULL WHERE name = 'Plank'"))
    command.stamp(config, "e5a1c7d9b3f4")
    command.upgrade(config, DEMOS_REVISION)
    with engine.connect() as connection:
        again = dict(connection.execute(sa.text("SELECT name, demo_id FROM trainr_exercises")).all())
    assert again["Push Up"] == "Incline_Push-Up"
    assert again["Plank"] == "Plank"
