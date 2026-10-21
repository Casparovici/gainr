from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app import config
from app.db import get_db
from app.models.listr_category import ListrCategory
from app.models.listr_item import ListrItem
from app.repositories import listr_list_repo, listr_meal_plan_repo, listr_recipe_category_repo, listr_recipe_repo
from app.routers import listr as listr_router


def make_category(db, name="Groente & Fruit") -> ListrCategory:
    category = ListrCategory(name=name)
    db.add(category)
    db.flush()
    return category


def make_item(db, name="Aardappelen", category=None, default_unit="kg") -> ListrItem:
    category = category or make_category(db)
    item = ListrItem(name=name, category_id=category.id, default_unit=default_unit)
    db.add(item)
    db.flush()
    return item


def make_recipe(db, title="Stamppot"):
    recipe = listr_recipe_repo.create_recipe(db, title=title, servings=None, instructions="", notes=None)
    db.flush()
    return recipe


def make_recipe_with_ingredient(db, title, item, quantity, unit):
    recipe = make_recipe(db, title)
    listr_recipe_repo.add_ingredient(
        db, recipe_id=recipe.id, grocery_item_id=item.id, quantity=Decimal(quantity), unit=unit, sort_order=0
    )
    db.flush()
    return recipe


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(listr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


# -- recipe categories (multi-tag) ---------------------------------------------------------------


def test_a_recipe_can_carry_several_categories_at_once(client, db_session):
    italian = listr_recipe_category_repo.create_category(db_session, name="Italiaans", sort_order=0)
    veggie = listr_recipe_category_repo.create_category(db_session, name="Vegetarisch", sort_order=1)
    db_session.commit()

    response = client.post(
        "/api/listr/recipes",
        json={"title": "Pasta pomodoro", "category_ids": [italian.id, veggie.id]},
    )

    assert response.status_code == 200
    names = {c["name"] for c in response.json()["categories"]}
    assert names == {"Italiaans", "Vegetarisch"}


def test_filtering_recipes_by_category_returns_only_tagged_ones(client, db_session):
    italian = listr_recipe_category_repo.create_category(db_session, name="Italiaans", sort_order=0)
    asian = listr_recipe_category_repo.create_category(db_session, name="Aziatisch", sort_order=1)
    db_session.commit()
    client.post("/api/listr/recipes", json={"title": "Pasta", "category_ids": [italian.id]})
    client.post("/api/listr/recipes", json={"title": "Pad Thai", "category_ids": [asian.id]})

    response = client.get(f"/api/listr/recipes?category_id={italian.id}")

    assert response.status_code == 200
    titles = [r["title"] for r in response.json()]
    assert titles == ["Pasta"]


# -- meal plan upsert ------------------------------------------------------------------------


def test_setting_a_day_creates_then_updates_in_place(db_session):
    recipe = make_recipe(db_session)
    db_session.commit()
    day = date(2026, 9, 14)

    listr_meal_plan_repo.upsert(db_session, day, recipe_id=recipe.id, is_cooked=False, notes=None)
    db_session.commit()
    entries = listr_meal_plan_repo.list_range(db_session, day, day)
    assert len(entries) == 1
    assert entries[0].is_cooked is False

    listr_meal_plan_repo.upsert(db_session, day, recipe_id=recipe.id, is_cooked=True, notes="lekker")
    db_session.commit()
    entries = listr_meal_plan_repo.list_range(db_session, day, day)
    assert len(entries) == 1
    assert entries[0].is_cooked is True
    assert entries[0].notes == "lekker"


def test_a_note_only_day_needs_no_recipe(client, db_session):
    response = client.put("/api/listr/meal-plan/2026-09-15", json={"notes": "uit eten"})

    assert response.status_code == 200
    body = response.json()
    assert body["recipe_id"] is None
    assert body["notes"] == "uit eten"


def test_clearing_a_day_removes_it(db_session):
    day = date(2026, 9, 16)
    listr_meal_plan_repo.upsert(db_session, day, recipe_id=None, is_cooked=False, notes="restjes")
    db_session.commit()

    removed = listr_meal_plan_repo.clear(db_session, day)
    db_session.commit()

    assert removed is True
    assert listr_meal_plan_repo.list_range(db_session, day, day) == []


def test_moving_a_day_re_dates_it_and_frees_the_old_day(client, db_session):
    recipe = make_recipe(db_session)
    listr_meal_plan_repo.upsert(db_session, date(2026, 9, 17), recipe_id=recipe.id, is_cooked=True, notes="lekker")
    db_session.commit()

    response = client.post("/api/listr/meal-plan/2026-09-17/move", json={"to": "2026-09-19"})

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-09-19"
    assert body["recipe_id"] == recipe.id
    assert body["is_cooked"] is True
    assert body["notes"] == "lekker"
    assert listr_meal_plan_repo.get_by_date(db_session, date(2026, 9, 17)) is None


def test_moving_a_day_onto_a_planned_day_is_refused_and_changes_nothing(client, db_session):
    listr_meal_plan_repo.upsert(db_session, date(2026, 9, 17), recipe_id=None, is_cooked=False, notes="a")
    listr_meal_plan_repo.upsert(db_session, date(2026, 9, 18), recipe_id=None, is_cooked=False, notes="b")
    db_session.commit()

    response = client.post("/api/listr/meal-plan/2026-09-17/move", json={"to": "2026-09-18"})

    assert response.status_code == 409
    assert listr_meal_plan_repo.get_by_date(db_session, date(2026, 9, 17)).notes == "a"
    assert listr_meal_plan_repo.get_by_date(db_session, date(2026, 9, 18)).notes == "b"


def test_moving_an_empty_day_is_a_404(client):
    response = client.post("/api/listr/meal-plan/2026-09-17/move", json={"to": "2026-09-18"})

    assert response.status_code == 404


def test_moving_a_day_to_itself_changes_nothing(client, db_session):
    listr_meal_plan_repo.upsert(db_session, date(2026, 9, 17), recipe_id=None, is_cooked=False, notes="a")
    db_session.commit()

    response = client.post("/api/listr/meal-plan/2026-09-17/move", json={"to": "2026-09-17"})

    assert response.status_code == 200
    assert response.json()["date"] == "2026-09-17"


# -- popularity -------------------------------------------------------------------------------


def test_popularity_only_counts_cooked_entries_with_a_recipe(client, db_session):
    cooked = make_recipe(db_session, "Stamppot")
    planned_not_cooked = make_recipe(db_session, "Lasagne")
    db_session.commit()

    client.put("/api/listr/meal-plan/2026-09-14", json={"recipe_id": cooked.id, "is_cooked": True})
    client.put("/api/listr/meal-plan/2026-09-15", json={"recipe_id": cooked.id, "is_cooked": True})
    client.put("/api/listr/meal-plan/2026-09-16", json={"recipe_id": planned_not_cooked.id, "is_cooked": False})
    client.put("/api/listr/meal-plan/2026-09-17", json={"notes": "uit eten", "is_cooked": True})

    response = client.get("/api/listr/meal-plan/popular")

    assert response.status_code == 200
    ranking = response.json()
    assert len(ranking) == 1
    assert ranking[0]["title"] == "Stamppot"
    assert ranking[0]["times_cooked"] == 2


# -- recipe delete unlinks meal-plan history instead of destroying it -----------------------------


def test_deleting_a_recipe_unlinks_but_keeps_its_meal_plan_history(client, db_session):
    recipe = make_recipe(db_session, "Chili sin carne")
    db_session.commit()
    client.put("/api/listr/meal-plan/2026-09-18", json={"recipe_id": recipe.id, "is_cooked": True, "notes": "top"})

    response = client.delete(f"/api/listr/recipes/{recipe.id}")
    assert response.status_code == 204

    day = client.get("/api/listr/meal-plan?date_from=2026-09-18&date_to=2026-09-18").json()
    assert len(day) == 1
    assert day[0]["recipe_id"] is None
    assert day[0]["is_cooked"] is True
    assert day[0]["notes"] == "top"


# -- ICS feed -----------------------------------------------------------------------------------


def test_ics_feed_404s_when_no_token_is_configured(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "LISTR_ICS_TOKEN", None)

    response = client.get("/api/listr/meal-plan.ics", params={"token": "anything"})

    assert response.status_code == 404


def test_ics_feed_404s_on_a_wrong_token(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "LISTR_ICS_TOKEN", "correct-token")

    response = client.get("/api/listr/meal-plan.ics", params={"token": "wrong-token"})

    assert response.status_code == 404


def test_ics_feed_lists_cooked_and_note_only_days_with_the_right_content_type(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "LISTR_ICS_TOKEN", "correct-token")
    recipe = make_recipe(db_session, "Chili sin carne")
    db_session.commit()
    client.put("/api/listr/meal-plan/2026-09-14", json={"recipe_id": recipe.id, "is_cooked": True})
    client.put("/api/listr/meal-plan/2026-09-15", json={"notes": "uit eten", "is_cooked": False})

    response = client.get("/api/listr/meal-plan.ics", params={"token": "correct-token"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/calendar; charset=utf-8"
    body = response.text
    assert "BEGIN:VCALENDAR" in body
    assert "SUMMARY:✓ Chili sin carne" in body
    assert "SUMMARY:uit eten" in body
    # RFC 5545 requires every VEVENT to carry a DTSTAMP -- Google Calendar accepts a feed
    # missing it (the VCALENDAR itself is still valid) but silently drops every event that
    # lacks one, which is exactly what an empty-looking subscribed calendar looks like.
    assert body.count("DTSTAMP:") == 2


# -- bulk add-to-list from the weekplanner -------------------------------------------------------


def test_add_meal_plan_to_list_merges_ingredients_across_recipes(client, db_session):
    onions = make_item(db_session, "Uien", default_unit="kg")
    stamppot = make_recipe_with_ingredient(db_session, "Stamppot", onions, "1", "kg")
    soep = make_recipe_with_ingredient(db_session, "Uiensoep", onions, "0.5", "kg")
    db_session.commit()
    client.put("/api/listr/meal-plan/2026-09-14", json={"recipe_id": stamppot.id})
    client.put("/api/listr/meal-plan/2026-09-15", json={"recipe_id": soep.id})

    response = client.post(
        "/api/listr/meal-plan/add-to-list",
        json={"dates": ["2026-09-14", "2026-09-15"], "new_list_name": "Weekboodschappen"},
    )

    assert response.status_code == 200
    new_list_id = response.json()["id"]
    lines = client.get(f"/api/listr/lists/{new_list_id}").json()["items"]
    assert len(lines) == 1
    assert lines[0]["grocery_item_name"] == "Uien"
    assert lines[0]["quantity"] == "1.500"


def test_add_meal_plan_to_list_skips_note_only_and_missing_days(client, db_session):
    item = make_item(db_session, "Aardappelen")
    recipe = make_recipe_with_ingredient(db_session, "Aardappelpuree", item, "2", "kg")
    db_session.commit()
    client.put("/api/listr/meal-plan/2026-09-16", json={"recipe_id": recipe.id})
    client.put("/api/listr/meal-plan/2026-09-17", json={"notes": "uit eten"})
    # 2026-09-18 has no meal-plan entry at all.

    response = client.post(
        "/api/listr/meal-plan/add-to-list",
        json={"dates": ["2026-09-16", "2026-09-17", "2026-09-18"], "new_list_name": "Weekboodschappen"},
    )

    assert response.status_code == 200
    lines = client.get(f"/api/listr/lists/{response.json()['id']}").json()["items"]
    assert [l["grocery_item_name"] for l in lines] == ["Aardappelen"]


def test_add_meal_plan_to_list_onto_an_existing_list(client, db_session):
    item = make_item(db_session, "Wortelen", default_unit="kg")
    recipe = make_recipe_with_ingredient(db_session, "Wortelsoep", item, "1", "kg")
    db_session.commit()
    existing = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    db_session.commit()
    client.put("/api/listr/meal-plan/2026-09-19", json={"recipe_id": recipe.id})

    response = client.post(
        "/api/listr/meal-plan/add-to-list", json={"dates": ["2026-09-19"], "list_id": existing.id}
    )

    assert response.status_code == 200
    assert response.json()["id"] == existing.id
    lines = client.get(f"/api/listr/lists/{existing.id}").json()["items"]
    assert [l["grocery_item_name"] for l in lines] == ["Wortelen"]
