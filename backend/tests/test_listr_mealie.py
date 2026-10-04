import json
from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.listr_category import ListrCategory
from app.models.listr_item import ListrItem
from app.models.listr_mealie_food import ListrMealieFood
from app.repositories import listr_recipe_repo
from app.routers import listr as listr_router
from app.services.listr_mealie_service import ListrMealieService, UnmappedMealieFoods, _suggest
from app.services.mealie_provider import (
    MealieAuthError,
    MealieIngredient,
    MealieProvider,
    MealieRecipe,
    MealieRecipeSummary,
)

# -- fakes ---------------------------------------------------------------------------------------


def ingredient(food_id, food_name, quantity="1", unit=None, note="", display=""):
    return MealieIngredient(
        quantity=Decimal(quantity) if quantity else None, unit=unit, food_id=food_id, food_name=food_name,
        note=note, display=display or food_name or "",
    )


class FakeMealie:
    """Stands in for MealieProvider: recipes keyed by slug, plus how often details were fetched."""

    def __init__(self, recipes: list[MealieRecipe]):
        self.recipes = {r.slug: r for r in recipes}
        self.fetched: list[str] = []

    def list_recipes(self):
        return [MealieRecipeSummary(id=r.id, slug=r.slug, name=r.name, updated_at=r.updated_at) for r in self.recipes.values()]

    def get_recipe(self, slug):
        self.fetched.append(slug)
        return self.recipes[slug]

    def close(self):
        pass


def frikandelbroodjes(updated_at="2026-09-29T12:00:00"):
    return MealieRecipe(
        id="m-1", slug="frikandelbroodjes", name="Frikandelbroodjes", updated_at=updated_at, servings=8,
        description="Snel en makkelijk.",
        ingredients=[
            ingredient("f-blad", "bladerdeeg", "8", "stuks", note="uit de vriezer"),
            ingredient("f-frik", "frikandel", "4"),
            ingredient("f-ei", "ei", "1", "stuks"),
            ingredient(None, None, None, display="snufje peper"),
        ],
        instructions=[("Bereiding", "Laat het bladerdeeg ontdooien."), ("", "Bak 20 minuten\nop 200 graden.")],
        categories=["Snacks"],
    )


@pytest.fixture()
def catalog(db_session):
    category = ListrCategory(name="Diepvries")
    db_session.add(category)
    db_session.flush()
    items = {
        name: ListrItem(name=name, category_id=category.id, default_unit="stuks")
        for name in ("Bladerdeeg", "Frikandel", "Eieren")
    }
    db_session.add_all(items.values())
    db_session.flush()
    return items


# -- service -------------------------------------------------------------------------------------


def test_preview_lists_new_recipes_and_foods_without_a_product(db_session, catalog):
    fake = FakeMealie([frikandelbroodjes()])
    preview = ListrMealieService(lambda: fake).preview(db_session)

    assert [(r.name, r.status) for r in preview.recipes] == [("Frikandelbroodjes", "new")]
    # "bladerdeeg"/"frikandel" match their catalog names regardless of case; "ei" doesn't match
    # "Eieren", and the unparsed "snufje peper" is never a product question.
    assert [(f.food_id, f.name, f.recipe_names) for f in preview.unmatched_foods] == [("f-ei", "ei", ["Frikandelbroodjes"])]


@pytest.mark.parametrize(
    ("food", "catalog_name"),
    [
        ("aardappel", "Aardappelen"),
        ("tomaat", "Tomaten"),
        ("sperzieboon", "Sperziebonen"),
        ("ui", "Uien"),
        ("ei", "Eieren"),
        ("kip", "Kippen"),
        ("peterselie", "Platte peterselie"),
        ("kerrie", "Kerriepoeder"),
    ],
)
def test_suggests_the_plural_or_a_close_catalog_name(food, catalog_name):
    items = [ListrItem(id=i, name=n) for i, n in enumerate([catalog_name, "Druiven", "Prei", "Jong belegen kaas"])]
    assert _suggest(food, items).name == catalog_name


def test_suggests_nothing_rather_than_something_loosely_related():
    items = [ListrItem(id=1, name="Jong belegen kaas"), ListrItem(id=2, name="Druiven"), ListrItem(id=3, name="Currypasta")]
    assert _suggest("parmesaanse kaas", items) is None
    assert _suggest("ui", items) is None  # not "Druiven" just because it contains "ui"
    assert _suggest("currysaus", items) is None


def test_import_refuses_while_a_food_is_unmatched(db_session, catalog):
    service = ListrMealieService(lambda: FakeMealie([frikandelbroodjes()]))
    with pytest.raises(UnmappedMealieFoods) as exc:
        service.import_recipes(db_session, {})
    assert [f.food_id for f in exc.value.foods] == ["f-ei"]
    assert listr_recipe_repo.mealie_sources(db_session) == {}


def test_import_creates_the_recipe_and_remembers_the_food_choice(db_session, catalog):
    service = ListrMealieService(lambda: FakeMealie([frikandelbroodjes()]))
    result = service.import_recipes(db_session, {"f-ei": catalog["Eieren"].id})

    assert (result.created, result.updated, result.unchanged) == (1, 0, 0)
    recipe = listr_recipe_repo.get_by_mealie_id(db_session, "m-1")
    assert recipe.title == "Frikandelbroodjes" and recipe.servings == 8
    assert [(i.grocery_item.name, i.quantity, i.unit) for i in recipe.ingredients] == [
        ("Bladerdeeg", Decimal("8"), "stuks"),
        ("Frikandel", Decimal("4"), "stuks"),  # no unit in Mealie -> the product's default
        ("Eieren", Decimal("1"), "stuks"),
    ]
    assert recipe.instructions == "### Bereiding\n1. Laat het bladerdeeg ontdooien.\n2. Bak 20 minuten op 200 graden."
    # Nothing Mealie had is dropped: description, the ingredient note, the unparsed line.
    assert "Snel en makkelijk." in recipe.notes
    assert "- Bladerdeeg: uit de vriezer" in recipe.notes
    assert "- snufje peper" in recipe.notes
    assert [c.name for c in recipe.categories] == ["Snacks"]
    assert db_session.get(ListrMealieFood, "f-ei").grocery_item_id == catalog["Eieren"].id


def test_a_second_recipe_reuses_the_remembered_food_choice(db_session, catalog):
    ListrMealieService(lambda: FakeMealie([frikandelbroodjes()])).import_recipes(db_session, {"f-ei": catalog["Eieren"].id})

    omelet = MealieRecipe(
        id="m-2", slug="omelet", name="Omelet", updated_at="2026-09-30T08:00:00", servings=1, description="",
        ingredients=[ingredient("f-ei", "ei", "3", "stuks")],
    )
    preview = ListrMealieService(lambda: FakeMealie([frikandelbroodjes(), omelet])).preview(db_session)
    assert preview.unmatched_foods == []


def test_reimport_updates_changed_recipes_and_skips_unchanged_ones(db_session, catalog):
    ListrMealieService(lambda: FakeMealie([frikandelbroodjes()])).import_recipes(db_session, {"f-ei": catalog["Eieren"].id})

    unchanged = FakeMealie([frikandelbroodjes()])
    result = ListrMealieService(lambda: unchanged).import_recipes(db_session, {})
    assert (result.created, result.updated, result.unchanged) == (0, 0, 1)
    assert unchanged.fetched == []  # an unchanged recipe isn't even fetched

    edited = frikandelbroodjes(updated_at="2026-10-01T09:00:00")
    edited.name = "Frikandelbroodjes (airfryer)"
    edited.ingredients = edited.ingredients[:2]
    result = ListrMealieService(lambda: FakeMealie([edited])).import_recipes(db_session, {})
    assert (result.created, result.updated, result.unchanged) == (0, 1, 0)

    recipe = listr_recipe_repo.get_by_mealie_id(db_session, "m-1")
    assert recipe.title == "Frikandelbroodjes (airfryer)"
    assert [i.grocery_item.name for i in recipe.ingredients] == ["Bladerdeeg", "Frikandel"]


def test_import_rejects_a_mapping_to_a_product_that_doesnt_exist(db_session, catalog):
    service = ListrMealieService(lambda: FakeMealie([frikandelbroodjes()]))
    with pytest.raises(ValueError):
        service.import_recipes(db_session, {"f-ei": 9999})


# -- provider (parsing what Mealie actually sends) -----------------------------------------------


def mealie_transport(routes: dict[str, httpx.Response]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        return routes.get(request.url.path, httpx.Response(404))

    return httpx.MockTransport(handler)


def test_provider_parses_and_sanitises_a_recipe():
    detail = {
        "id": "m-1", "slug": "frikandelbroodjes", "name": "  Frikandelbroodjes  ", "updatedAt": "2026-09-29T12:00:00",
        "recipeServings": 8.0, "description": "x" * 9000,
        "recipeIngredient": [
            {"quantity": 8.0, "unit": {"name": "eetlepel", "abbreviation": "el"}, "food": {"id": "f-1", "name": "currysaus"}, "note": ""},
            {"quantity": "nonsense", "unit": None, "food": None, "note": "", "display": "snufje zout"},
            {"quantity": -2, "food": {"id": "f-2", "name": "ui"}},
            "not-a-dict",
        ],
        "recipeInstructions": [{"title": "Bereiding", "text": "Stap een."}, {"text": ""}],
        "recipeCategory": [{"name": "Snacks"}], "tags": [{"name": "snacks"}, {"name": "Snacks"}],
        "notes": [{"title": "Tip", "text": "Lekker met mayo."}],
    }
    provider = MealieProvider(
        "http://mealie.local:9000/", "test-key",
        transport=mealie_transport({"/api/recipes/frikandelbroodjes": httpx.Response(200, json=detail)}),
    )
    recipe = provider.get_recipe("frikandelbroodjes")

    assert recipe.name == "Frikandelbroodjes" and recipe.servings == 8
    assert len(recipe.description) == 5000
    assert [(i.quantity, i.unit, i.food_id, i.food_name) for i in recipe.ingredients] == [
        (Decimal("8.000"), "el", "f-1", "currysaus"),
        (None, None, None, None),
        (None, None, "f-2", "ui"),  # a negative quantity is dropped, not imported
    ]
    assert recipe.ingredients[1].display == "snufje zout"
    assert recipe.instructions == [("Bereiding", "Stap een.")]
    assert recipe.categories == ["Snacks", "snacks"]
    assert recipe.notes == ["**Tip**\nLekker met mayo."]


def test_provider_pages_through_the_recipe_list():
    pages = {
        1: {"items": [{"id": "a", "slug": "a", "name": "A", "updatedAt": "t1"}], "total_pages": 2},
        2: {"items": [{"id": "b", "slug": "b", "name": "B", "dateUpdated": "t2"}], "total_pages": 2},
    }

    def handler(request):
        return httpx.Response(200, json=pages[int(request.url.params["page"])])

    summaries = MealieProvider("http://m", "k", transport=httpx.MockTransport(handler)).list_recipes()
    assert [(s.id, s.updated_at) for s in summaries] == [("a", "t1"), ("b", "t2")]


def test_provider_reports_a_rejected_key_distinctly():
    provider = MealieProvider("http://m", "test-key", transport=mealie_transport({"/api/recipes": httpx.Response(401)}))
    with pytest.raises(MealieAuthError):
        provider.list_recipes()


def test_provider_quotes_the_slug_into_the_path():
    seen = []

    def handler(request):
        seen.append(request.url.raw_path)
        return httpx.Response(404)

    provider = MealieProvider("http://m", "k", transport=httpx.MockTransport(handler))
    with pytest.raises(Exception):
        provider.get_recipe("../users/self")
    assert seen == [b"/api/recipes/..%2Fusers%2Fself"]


# -- router --------------------------------------------------------------------------------------


@pytest.fixture()
def client(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(listr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_import_endpoint_asks_for_the_missing_foods_then_imports(client, db_session, catalog, monkeypatch):
    monkeypatch.setattr(listr_router, "listr_mealie_service", ListrMealieService(lambda: FakeMealie([frikandelbroodjes()])))

    preview = client.get("/api/listr/mealie/preview").json()
    assert preview["unmatched_foods"] == [
        {
            "food_id": "f-ei", "name": "ei", "recipe_names": ["Frikandelbroodjes"],
            "suggested_item_id": catalog["Eieren"].id, "suggested_item_name": "Eieren",
        }
    ]

    refused = client.post("/api/listr/mealie/import", json={"mappings": []})
    assert refused.status_code == 409
    assert refused.json()["detail"]["unmatched_foods"][0]["food_id"] == "f-ei"

    done = client.post("/api/listr/mealie/import", json={"mappings": [{"food_id": "f-ei", "grocery_item_id": catalog["Eieren"].id}]})
    assert done.json() == {"created": 1, "updated": 0, "unchanged": 0}
    recipes = client.get("/api/listr/recipes").json()
    assert [(r["title"], r["mealie_id"]) for r in recipes] == [("Frikandelbroodjes", "m-1")]


def test_endpoints_report_an_unconfigured_mealie(client, monkeypatch):
    monkeypatch.setattr("app.config.MEALIE_URL", None)
    monkeypatch.setattr(listr_router, "listr_mealie_service", ListrMealieService())

    assert client.get("/api/listr/mealie/status").json() == {"configured": False}
    response = client.get("/api/listr/mealie/preview")
    assert response.status_code == 409


def test_a_rejected_key_becomes_a_readable_502_without_the_key(client, monkeypatch):
    def rejecting():
        return MealieProvider("http://m", "secret-key-123", transport=httpx.MockTransport(lambda r: httpx.Response(401)))

    monkeypatch.setattr(listr_router, "listr_mealie_service", ListrMealieService(rejecting))
    response = client.get("/api/listr/mealie/preview")
    assert response.status_code == 502
    assert "API-sleutel" in response.json()["detail"]
    assert "secret-key-123" not in json.dumps(response.json())
