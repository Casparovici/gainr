"""briefr's home chef: recipe suggestions in a report, and planning one in listr (ADR 0054)."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.listr_category import ListrCategory
from app.models.listr_item import ListrItem
from app.repositories import briefr_report_repo, listr_meal_plan_repo, listr_recipe_repo
from app.routers import briefr as briefr_router
from app.services import briefr_chef_service, briefr_context_service, briefr_report_service
from app.services.briefr_report_service import InvalidReport, parse_report
from app.services.errors import Conflict, InvalidRequest
from app.services.listr_catalog_service import match_product

PATH = "reports/home-chef/2026-10-23.md"
URL = "https://www.leukerecepten.nl/recepten/pasta-met-spinazie-en-zalm/"

REPORT = f"""+++
agent = "home-chef"
run_at = 2026-10-23T07:00:00+02:00
title = "5 recepten voor week 44"

[[items]]
verdict = "watch"
headline = "Pasta met spinazie en zalm"
detail = "Snel doordeweeks: klaar in 25 minuten."
sources = ["{URL}"]

[items.recipe]
url = "{URL}"
servings = 4
minutes = 25
steps = ["Kook de pasta.", "Bak de  zalm\\nen voeg de spinazie toe."]

[[items.recipe.ingredients]]
name = "Penne"
quantity = 400
unit = "gram"

[[items.recipe.ingredients]]
name = "tomaat"
quantity = 2
note = "in blokjes"

[[items.recipe.ingredients]]
name = "Sojasaus"
quantity = 1.5
unit = "el"

[[items.recipe.ingredients]]
name = "Zout en peper"

[[items]]
verdict = "watch"
headline = "Gewoon een tip zonder recept"
+++
Vijf recepten voor volgende week.
"""


@pytest.fixture()
def catalog(db_session):
    category = ListrCategory(name="Groente & Fruit")
    db_session.add(category)
    db_session.flush()
    items = {
        name: ListrItem(name=name, category_id=category.id, default_unit=unit)
        for name, unit in [("Penne", "pak"), ("Tomaten", "stuks"), ("Gearchiveerd", "stuks")]
    }
    items["Gearchiveerd"].is_archived = True
    db_session.add_all(items.values())
    db_session.flush()
    return items


@pytest.fixture()
def report(db_session):
    briefr_report_service.save_report(db_session, PATH, "hash", parse_report(PATH, REPORT))
    db_session.flush()
    return briefr_report_repo.get_by_source_path(db_session, PATH)


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(briefr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


# -- the report file -------------------------------------------------------------------------------


def test_a_finding_can_carry_a_recipe():
    parsed = parse_report(PATH, REPORT)
    recipe = parsed.items[0].recipe

    assert recipe is not None
    assert (recipe.url, recipe.servings, recipe.minutes) == (URL, 4, 25)
    assert recipe.steps == ["Kook de pasta.", "Bak de zalm en voeg de spinazie toe."]
    assert [(i.name, i.quantity, i.unit, i.note) for i in recipe.ingredients] == [
        ("Penne", Decimal(400), "gram", None),
        ("tomaat", Decimal(2), None, "in blokjes"),
        ("Sojasaus", Decimal("1.5"), "el", None),
        ("Zout en peper", None, None, None),
    ]
    assert parsed.items[1].recipe is None


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ((f'url = "{URL}"', 'url = "javascript:alert(1)"'), "not an http(s) link"),
        (('servings = 4', 'servings = 0'), "servings"),
        (('steps = ["Kook de pasta.", "Bak de  zalm\\nen voeg de spinazie toe."]', "steps = []"), "steps"),
        (('steps = ["Kook de pasta.",', 'steps = ["   ",'), "a step must not be blank"),
        (('name = "Penne"', 'name = "  "'), "name"),
        (('quantity = 400', 'quantity = -1'), "quantity"),
    ],
)
def test_a_recipe_that_breaks_the_contract_says_why(change, problem):
    with pytest.raises(InvalidReport) as raised:
        parse_report(PATH, REPORT.replace(*change))
    assert problem in str(raised.value)


def test_a_recipe_needs_ingredients():
    without = REPORT.split("[[items.recipe.ingredients]]")[0] + "[[items]]" + REPORT.split("[[items]]")[2]
    with pytest.raises(InvalidReport, match="ingredients"):
        parse_report(PATH, without)


def test_the_report_shows_the_recipe_and_that_it_isnt_planned_yet(client, report):
    detail = client.get(f"/api/briefr/reports/{report.id}").json()

    suggestion, tip = detail["items"]
    assert suggestion["recipe"]["url"] == URL
    assert suggestion["recipe"]["ingredients"][2] == {"name": "Sojasaus", "quantity": "1.5", "unit": "el", "note": None}
    assert (suggestion["recipe"]["listr_recipe_id"], suggestion["recipe"]["planned_on"]) == (None, [])
    assert tip["recipe"] is None


# -- matching ingredients to products ---------------------------------------------------------------


def test_an_ingredient_matches_a_product_by_its_name_or_plural_only(catalog):
    by_name = {item.name.casefold(): item for item in catalog.values()}

    assert match_product("penne", by_name) is catalog["Penne"]
    assert match_product("Tomaat", by_name) is catalog["Tomaten"]
    assert match_product("rijpe tomaten", by_name) is None  # nothing looser than the name
    assert match_product("   ", by_name) is None


# -- planning a suggestion -------------------------------------------------------------------------


def test_planning_a_suggestion_makes_it_a_listr_recipe_on_that_day(db_session, catalog, report):
    item = report.items[0]

    entry = briefr_chef_service.plan_suggestion(db_session, item, date(2026, 10, 26), replace=False)

    recipe = listr_recipe_repo.get_recipe(db_session, entry.recipe_id)
    assert (entry.date, entry.is_cooked) == (date(2026, 10, 26), False)
    assert (recipe.title, recipe.servings, recipe.source_url) == ("Pasta met spinazie en zalm", 4, URL)
    assert recipe.instructions == "1. Kook de pasta.\n2. Bak de zalm en voeg de spinazie toe."
    assert [(i.grocery_item.name, i.quantity, i.unit) for i in recipe.ingredients] == [
        ("Penne", Decimal(400), "gram"),
        ("Tomaten", Decimal(2), "stuks"),  # no unit given: the product's own
    ]
    assert "Snel doordeweeks" in recipe.notes
    assert "Bereidingstijd: 25 minuten" in recipe.notes
    assert "- Tomaten: in blokjes" in recipe.notes
    assert "**Ingrediënten zonder product**\n- 1,5 el Sojasaus\n- Zout en peper" in recipe.notes
    assert URL in recipe.notes


def test_planning_it_again_reuses_the_recipe(db_session, catalog, report):
    item = report.items[0]
    first = briefr_chef_service.plan_suggestion(db_session, item, date(2026, 10, 26), replace=False)
    listr_recipe_repo.update_recipe(db_session, first.recipe, title="Mijn pasta")

    again = briefr_chef_service.plan_suggestion(db_session, item, date(2026, 10, 28), replace=False)
    same_day = briefr_chef_service.plan_suggestion(db_session, item, date(2026, 10, 28), replace=False)

    assert again.recipe_id == first.recipe_id == same_day.recipe_id
    assert again.recipe.title == "Mijn pasta"
    states = briefr_chef_service.recipe_states(db_session, report.items, since=date(2026, 10, 23))
    assert states == {item.id: (first.recipe_id, [date(2026, 10, 26), date(2026, 10, 28)])}
    assert briefr_chef_service.recipe_states(db_session, report.items, since=date(2026, 10, 27)) == {
        item.id: (first.recipe_id, [date(2026, 10, 28)]),
    }


def test_a_planned_day_is_only_replaced_when_asked(db_session, catalog, report):
    other = listr_recipe_repo.create_recipe(db_session, title="Stamppot", servings=None, instructions="", notes=None)
    listr_meal_plan_repo.upsert(db_session, date(2026, 10, 26), recipe_id=other.id, is_cooked=False, notes=None)

    with pytest.raises(Conflict):
        briefr_chef_service.plan_suggestion(db_session, report.items[0], date(2026, 10, 26), replace=False)
    assert listr_recipe_repo.get_by_source_urls(db_session, [URL]) == {}  # nothing made for a refused plan

    entry = briefr_chef_service.plan_suggestion(db_session, report.items[0], date(2026, 10, 26), replace=True)
    assert entry.recipe.source_url == URL


def test_only_a_recipe_suggestion_can_be_planned(db_session, report):
    with pytest.raises(InvalidRequest):
        briefr_chef_service.plan_suggestion(db_session, report.items[1], date(2026, 10, 26), replace=False)


def test_a_long_headline_is_cut_to_a_recipe_title(db_session, catalog):
    parsed = parse_report(PATH, REPORT.replace('headline = "Pasta met spinazie en zalm"', f'headline = "{"a" * 300}"'))
    report, _ = briefr_report_service.save_report(db_session, PATH, "hash", parsed)

    entry = briefr_chef_service.plan_suggestion(db_session, report.items[0], date(2026, 10, 26), replace=False)

    assert len(entry.recipe.title) == briefr_chef_service.TITLE_MAX and entry.recipe.title.endswith("…")


def test_the_plan_endpoint(client, db_session, catalog, report):
    item_id = report.items[0].id

    planned = client.post(f"/api/briefr/items/{item_id}/plan", json={"date": "2026-10-26"})
    assert planned.status_code == 200
    assert planned.json()["recipe"]["planned_on"] == ["2026-10-26"]
    assert planned.json()["recipe"]["listr_recipe_id"] is not None

    other = listr_recipe_repo.create_recipe(db_session, title="Stamppot", servings=None, instructions="", notes=None)
    listr_meal_plan_repo.upsert(db_session, date(2026, 10, 27), recipe_id=other.id, is_cooked=False, notes=None)
    db_session.commit()
    assert client.post(f"/api/briefr/items/{item_id}/plan", json={"date": "2026-10-27"}).status_code == 409
    replaced = client.post(f"/api/briefr/items/{item_id}/plan", json={"date": "2026-10-27", "replace": True})
    assert replaced.json()["recipe"]["planned_on"] == ["2026-10-26", "2026-10-27"]

    detail = client.get(f"/api/briefr/reports/{report.id}").json()
    assert detail["items"][0]["recipe"]["planned_on"] == ["2026-10-26", "2026-10-27"]

    assert client.post(f"/api/briefr/items/{report.items[1].id}/plan", json={"date": "2026-10-26"}).status_code == 400
    assert client.post("/api/briefr/items/9999/plan", json={"date": "2026-10-26"}).status_code == 404


# -- the context the agent reads -------------------------------------------------------------------


def test_the_product_catalog_goes_to_the_agents_per_category(db_session, catalog):
    text = briefr_context_service.products_markdown(db_session)

    assert text.startswith("# listr products")
    assert "## Groente & Fruit\n\n- Penne (pak)\n- Tomaten (stuks)\n" in text
    assert "Gearchiveerd" not in text


def test_the_report_run_date_is_what_planned_days_count_from(report):
    assert report.run_at == datetime(2026, 10, 23, 5, 0)
