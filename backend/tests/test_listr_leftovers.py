from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.db import get_db
from app.routers import listr as listr_router
from app.services import listr_leftover_service


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(listr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def make_leftover(client, **overrides):
    body = {"name": "Bolognese", "meals": 2, "servings_per_meal": 4, "location": "freezer"}
    body.update(overrides)
    response = client.post("/api/listr/leftovers", json=body)
    assert response.status_code == 200
    return response.json()


def plan_day(client, day, **body):
    body.setdefault("is_cooked", False)
    return client.put(f"/api/listr/meal-plan/{day}", json=body)


def meals_of(client, leftover_id):
    return next((l["meals"] for l in client.get("/api/listr/leftovers").json() if l["id"] == leftover_id), 0)


def test_use_by_defaults_from_the_location():
    stored = date(2026, 10, 11)
    assert listr_leftover_service.default_use_by("fridge", stored) == stored + timedelta(days=3)
    assert listr_leftover_service.default_use_by("freezer", stored) == stored + timedelta(days=90)


def test_creating_a_leftover_fills_in_today_and_a_use_by(client):
    leftover = make_leftover(client)
    assert leftover["stored_on"] == date.today().isoformat()
    assert leftover["use_by"] == (date.today() + timedelta(days=90)).isoformat()


def test_an_explicit_use_by_wins(client):
    leftover = make_leftover(client, use_by="2026-12-24")
    assert leftover["use_by"] == "2026-12-24"


def test_the_list_is_soonest_use_by_first_and_hides_used_up_batches(client):
    later = make_leftover(client, name="Soep", use_by="2027-01-01")
    sooner = make_leftover(client, name="Lasagne", use_by="2026-11-01")
    gone = make_leftover(client, name="Chili", meals=1)
    client.post(f"/api/listr/leftovers/{gone['id']}/meals", json={"delta": -1})

    names = [l["name"] for l in client.get("/api/listr/leftovers").json()]
    assert names == ["Lasagne", "Soep"]
    assert sooner["id"] and later["id"]


def test_meals_never_go_below_zero(client):
    leftover = make_leftover(client, meals=1)
    response = client.post(f"/api/listr/leftovers/{leftover['id']}/meals", json={"delta": -5})
    assert response.json()["meals"] == 0


def test_marking_a_leftover_day_cooked_takes_one_meal_off(client):
    leftover = make_leftover(client)
    planned = plan_day(client, "2026-10-14", leftover_id=leftover["id"])
    assert planned.json()["leftover_name"] == "Bolognese"
    assert meals_of(client, leftover["id"]) == 2  # planning alone doesn't eat it

    plan_day(client, "2026-10-14", leftover_id=leftover["id"], is_cooked=True)
    assert meals_of(client, leftover["id"]) == 1


def test_saving_a_cooked_day_twice_deducts_once(client):
    leftover = make_leftover(client)
    for _ in range(2):
        plan_day(client, "2026-10-14", leftover_id=leftover["id"], is_cooked=True)
    assert meals_of(client, leftover["id"]) == 1


def test_uncooking_or_clearing_a_day_gives_the_meal_back(client):
    leftover = make_leftover(client)
    plan_day(client, "2026-10-14", leftover_id=leftover["id"], is_cooked=True)
    plan_day(client, "2026-10-14", leftover_id=leftover["id"], is_cooked=False)
    assert meals_of(client, leftover["id"]) == 2

    plan_day(client, "2026-10-14", leftover_id=leftover["id"], is_cooked=True)
    client.delete("/api/listr/meal-plan/2026-10-14")
    assert meals_of(client, leftover["id"]) == 2


def test_switching_a_cooked_day_to_another_leftover_moves_the_meal(client):
    first = make_leftover(client, name="Bolognese")
    second = make_leftover(client, name="Soep")
    plan_day(client, "2026-10-14", leftover_id=first["id"], is_cooked=True)
    plan_day(client, "2026-10-14", leftover_id=second["id"], is_cooked=True)
    assert meals_of(client, first["id"]) == 2
    assert meals_of(client, second["id"]) == 1


def test_eating_the_last_meal_is_allowed_but_a_further_one_is_refused(client):
    leftover = make_leftover(client, meals=1)
    assert plan_day(client, "2026-10-14", leftover_id=leftover["id"], is_cooked=True).status_code == 200
    assert meals_of(client, leftover["id"]) == 0  # used up, so it drops off the list

    refused = plan_day(client, "2026-10-15", leftover_id=leftover["id"], is_cooked=True)
    assert refused.status_code == 409
    # the used-up day can still be un-cooked, which brings the batch back
    plan_day(client, "2026-10-14", leftover_id=leftover["id"], is_cooked=False)
    assert meals_of(client, leftover["id"]) == 1


def test_a_day_cannot_carry_a_recipe_and_a_leftover(client):
    leftover = make_leftover(client)
    recipe = client.post("/api/listr/recipes", json={"title": "Pasta"}).json()
    response = plan_day(client, "2026-10-14", recipe_id=recipe["id"], leftover_id=leftover["id"])
    assert response.status_code == 400


def test_deleting_a_leftover_keeps_the_day_and_does_not_refund(client):
    leftover = make_leftover(client)
    plan_day(client, "2026-10-14", leftover_id=leftover["id"], is_cooked=True, notes="lekker")
    assert client.delete(f"/api/listr/leftovers/{leftover['id']}").status_code == 204

    day = client.get("/api/listr/meal-plan?date_from=2026-10-14&date_to=2026-10-14").json()[0]
    assert day["leftover_id"] is None and day["is_cooked"] is True


def test_a_leftover_day_adds_nothing_to_the_shopping_list(client):
    leftover = make_leftover(client)
    plan_day(client, "2026-10-14", leftover_id=leftover["id"])
    response = client.post(
        "/api/listr/meal-plan/add-to-list", json={"dates": ["2026-10-14"], "new_list_name": "Boodschappen"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Boodschappen"


def test_a_leftover_can_be_edited_including_clearing_servings(client):
    leftover = make_leftover(client)
    response = client.patch(
        f"/api/listr/leftovers/{leftover['id']}", json={"use_by": "2026-11-30", "servings_per_meal": None}
    )
    body = response.json()
    assert body["use_by"] == "2026-11-30" and body["servings_per_meal"] is None and body["name"] == "Bolognese"
