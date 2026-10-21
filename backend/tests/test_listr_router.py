"""listr's HTTP surface: catalog, lists, recipes and the three "add to a list" actions. Written
against behaviour, so the router can move its logic into services underneath without these
changing."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models import GriprAccount, GriprAccountType, GriprBalanceMode
from app.routers import listr as listr_router

DAY = date(2026, 10, 12)


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(listr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def make_category(client, name="Zuivel") -> int:
    return client.post("/api/listr/categories", json={"name": name}).json()["id"]


def make_item(client, name="Melk", unit="liter", category_id=None) -> dict:
    category_id = category_id or make_category(client)
    response = client.post("/api/listr/items", json={"name": name, "category_id": category_id, "default_unit": unit})
    assert response.status_code == 200
    return response.json()


def make_list(client, name="Weekboodschappen") -> int:
    return client.post("/api/listr/lists", json={"name": name}).json()["id"]


def make_recipe(client, title="Pannenkoeken", ingredients=(), category_ids=()) -> dict:
    response = client.post(
        "/api/listr/recipes",
        json={"title": title, "servings": 4, "ingredients": list(ingredients), "category_ids": list(category_ids)},
    )
    assert response.status_code == 200
    return response.json()


def list_lines(client, list_id) -> list[tuple[str, Decimal, str]]:
    items = client.get(f"/api/listr/lists/{list_id}").json()["items"]
    return sorted((i["grocery_item_name"], Decimal(i["quantity"]), i["unit"]) for i in items)


# -- categories and catalog ------------------------------------------------------------------


def test_categories_are_created_reordered_and_updated(client):
    first, second = make_category(client, "Zuivel"), make_category(client, "Groente")
    assert client.put("/api/listr/categories/reorder", json={"category_ids": [second, first]}).status_code == 204
    assert [c["name"] for c in client.get("/api/listr/categories").json()] == ["Groente", "Zuivel"]

    updated = client.put(f"/api/listr/categories/{first}", json={"is_archived": True}).json()
    assert updated["is_archived"] is True
    assert [c["name"] for c in client.get("/api/listr/categories").json()] == ["Groente"]
    assert client.put("/api/listr/categories/999", json={"is_archived": True}).status_code == 404


def test_adding_a_product_that_exists_returns_it_instead_of_a_second(client):
    melk = make_item(client)
    again = client.post(
        "/api/listr/items", json={"name": "Melk", "category_id": melk["category_id"], "default_unit": "pak"}
    ).json()
    assert again["id"] == melk["id"]
    assert again["default_unit"] == "liter"
    assert len(client.get("/api/listr/items").json()) == 1


def test_a_product_needs_an_existing_category(client):
    response = client.post("/api/listr/items", json={"name": "Melk", "category_id": 999, "default_unit": "liter"})
    assert response.status_code == 404


def test_updating_a_product(client):
    melk = make_item(client)
    updated = client.put(f"/api/listr/items/{melk['id']}", json={"default_unit": "pak"}).json()
    assert updated["default_unit"] == "pak"
    assert client.put("/api/listr/items/999", json={"default_unit": "pak"}).status_code == 404


def test_a_picnic_mapping_stores_the_price_in_euros_and_a_pick_without_one_clears_it(client):
    melk = make_item(client)
    mapped = client.put(
        f"/api/listr/items/{melk['id']}/picnic-mapping",
        json={"picnic_product_id": "s100", "picnic_product_name": "Halfvolle melk", "display_price": 129,
              "unit_quantity": "1 liter", "image_id": "abc"},
    ).json()
    assert mapped["picnic_product_id"] == "s100"
    assert Decimal(mapped["picnic_price"]) == Decimal("1.29")
    assert mapped["picnic_price_at"] is not None
    assert mapped["picnic_image_url"]

    remapped = client.put(
        f"/api/listr/items/{melk['id']}/picnic-mapping",
        json={"picnic_product_id": "s200", "picnic_product_name": "Volle melk"},
    ).json()
    assert remapped["picnic_price"] is None
    assert remapped["picnic_price_at"] is None
    assert client.put(
        "/api/listr/items/999/picnic-mapping", json={"picnic_product_id": "s1", "picnic_product_name": "x"}
    ).status_code == 404


def test_tracking_a_product_in_voorraad_computes_its_status(client):
    melk = make_item(client)
    tracked = client.put(f"/api/listr/items/{melk['id']}/inventory", json={"tracked": True}).json()
    assert tracked["inventory_status"] is not None
    assert [i["id"] for i in client.get("/api/listr/inventory").json()] == [melk["id"]]

    untracked = client.put(f"/api/listr/items/{melk['id']}/inventory", json={"tracked": False}).json()
    assert untracked["inventory_status"] is None
    assert client.put("/api/listr/items/999/inventory", json={"tracked": True}).status_code == 404


# -- lists -------------------------------------------------------------------------------------


def test_lists_are_renamed_duplicated_and_deleted_with_their_items(client):
    list_id = make_list(client)
    melk = make_item(client)
    client.post(f"/api/listr/lists/{list_id}/items", json={"grocery_item_id": melk["id"], "quantity": "2"})

    renamed = client.put(f"/api/listr/lists/{list_id}", json={"name": "Zaterdag"}).json()
    assert renamed["name"] == "Zaterdag"
    assert renamed["item_count"] == 1

    copy = client.post(f"/api/listr/lists/{list_id}/duplicate", json={"name": "Kopie"}).json()
    assert copy["name"] == "Kopie"
    assert list_lines(client, copy["id"]) == [("Melk", Decimal("2"), "liter")]

    assert client.delete(f"/api/listr/lists/{list_id}").status_code == 204
    assert client.get(f"/api/listr/lists/{list_id}").status_code == 404
    assert [l["id"] for l in client.get("/api/listr/lists").json()] == [copy["id"]]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/listr/lists/999", None),
        ("put", "/api/listr/lists/999", {"name": "x"}),
        ("delete", "/api/listr/lists/999", None),
        ("post", "/api/listr/lists/999/duplicate", {"name": "x"}),
        ("post", "/api/listr/lists/999/clear-checked", None),
        ("post", "/api/listr/lists/999/items", {"grocery_item_id": 1}),
    ],
)
def test_a_missing_list_is_a_404(client, method, path, body):
    response = client.request(method, path, json=body)
    assert response.status_code == 404


def test_adding_the_same_product_twice_merges_into_one_line(client):
    list_id = make_list(client)
    melk = make_item(client)
    client.post(f"/api/listr/lists/{list_id}/items", json={"grocery_item_id": melk["id"]})
    line = client.post(f"/api/listr/lists/{list_id}/items", json={"grocery_item_id": melk["id"], "quantity": "2"}).json()
    assert Decimal(line["quantity"]) == Decimal("3")
    assert list_lines(client, list_id) == [("Melk", Decimal("3"), "liter")]
    assert client.post(f"/api/listr/lists/{list_id}/items", json={"grocery_item_id": 999}).status_code == 404


def test_a_list_line_is_checked_cleared_and_only_reachable_through_its_own_list(client):
    list_id, other_id = make_list(client), make_list(client, "Ander")
    melk = make_item(client)
    line = client.post(f"/api/listr/lists/{list_id}/items", json={"grocery_item_id": melk["id"]}).json()

    assert client.put(f"/api/listr/lists/{other_id}/items/{line['id']}", json={"is_checked": True}).status_code == 404
    assert client.delete(f"/api/listr/lists/{other_id}/items/{line['id']}").status_code == 404

    checked = client.put(f"/api/listr/lists/{list_id}/items/{line['id']}", json={"is_checked": True}).json()
    assert checked["is_checked"] is True
    assert client.post(f"/api/listr/lists/{list_id}/clear-checked").status_code == 204
    assert list_lines(client, list_id) == []


def test_deleting_a_list_line(client):
    list_id = make_list(client)
    line = client.post(f"/api/listr/lists/{list_id}/items", json={"grocery_item_id": make_item(client)["id"]}).json()
    assert client.delete(f"/api/listr/lists/{list_id}/items/{line['id']}").status_code == 204
    assert list_lines(client, list_id) == []


# -- recipe categories and recipes ------------------------------------------------------------


def test_recipe_categories_are_created_reordered_and_updated(client):
    first = client.post("/api/listr/recipe-categories", json={"name": "Italiaans"}).json()["id"]
    second = client.post("/api/listr/recipe-categories", json={"name": "Soep"}).json()["id"]
    assert client.put("/api/listr/recipe-categories/reorder", json={"category_ids": [second, first]}).status_code == 204
    assert [c["name"] for c in client.get("/api/listr/recipe-categories").json()] == ["Soep", "Italiaans"]
    assert client.put(f"/api/listr/recipe-categories/{first}", json={"color": "#ff0000"}).json()["color"] == "#ff0000"
    assert client.put("/api/listr/recipe-categories/999", json={"color": "#ff0000"}).status_code == 404


def test_a_recipe_keeps_its_ingredients_in_order_with_the_products_default_unit(client):
    category_id = make_category(client)
    melk, eieren = make_item(client, "Melk", "liter", category_id), make_item(client, "Eieren", "stuks", category_id)
    italiaans = client.post("/api/listr/recipe-categories", json={"name": "Italiaans"}).json()["id"]

    recipe = make_recipe(
        client,
        ingredients=[{"grocery_item_id": melk["id"], "quantity": "0.5"},
                     {"grocery_item_id": eieren["id"], "quantity": "3", "unit": "stuk"}],
        category_ids=[italiaans],
    )

    assert [(i["grocery_item_name"], i["unit"]) for i in recipe["ingredients"]] == [("Melk", "liter"), ("Eieren", "stuk")]
    assert [c["name"] for c in recipe["categories"]] == ["Italiaans"]
    assert client.get(f"/api/listr/recipes/{recipe['id']}").json()["title"] == "Pannenkoeken"


def test_a_recipe_with_an_unknown_product_is_refused(client):
    response = client.post(
        "/api/listr/recipes", json={"title": "x", "ingredients": [{"grocery_item_id": 999, "quantity": "1"}]}
    )
    assert response.status_code == 404


def test_updating_a_recipe_replaces_its_ingredients_and_categories(client):
    category_id = make_category(client)
    melk, bloem = make_item(client, "Melk", "liter", category_id), make_item(client, "Bloem", "gram", category_id)
    soep = client.post("/api/listr/recipe-categories", json={"name": "Soep"}).json()["id"]
    recipe = make_recipe(client, ingredients=[{"grocery_item_id": melk["id"], "quantity": "1"}])

    updated = client.put(
        f"/api/listr/recipes/{recipe['id']}",
        json={"title": "Flensjes", "ingredients": [{"grocery_item_id": bloem["id"], "quantity": "250"}],
              "category_ids": [soep]},
    ).json()

    assert updated["title"] == "Flensjes"
    assert [(i["grocery_item_name"], Decimal(i["quantity"]), i["sort_order"]) for i in updated["ingredients"]] == [
        ("Bloem", Decimal("250"), 0)
    ]
    assert [c["name"] for c in updated["categories"]] == ["Soep"]


def test_updating_only_a_recipes_title_leaves_its_ingredients(client):
    melk = make_item(client)
    recipe = make_recipe(client, ingredients=[{"grocery_item_id": melk["id"], "quantity": "1"}])
    updated = client.put(f"/api/listr/recipes/{recipe['id']}", json={"title": "Andere naam"}).json()
    assert [i["grocery_item_name"] for i in updated["ingredients"]] == ["Melk"]


def test_a_missing_recipe_is_a_404(client):
    assert client.get("/api/listr/recipes/999").status_code == 404
    assert client.put("/api/listr/recipes/999", json={"title": "x"}).status_code == 404
    assert client.delete("/api/listr/recipes/999").status_code == 404
    assert client.post("/api/listr/recipes/999/add-to-list", json={"new_list_name": "x", "ingredient_ids": [1]}).status_code == 404


def test_updating_a_recipe_with_an_unknown_product_is_refused(client):
    recipe = make_recipe(client)
    response = client.put(
        f"/api/listr/recipes/{recipe['id']}", json={"ingredients": [{"grocery_item_id": 999, "quantity": "1"}]}
    )
    assert response.status_code == 404


def test_deleting_a_recipe_keeps_the_days_and_leftovers_it_was_on(client):
    recipe = make_recipe(client)
    client.put(f"/api/listr/meal-plan/{DAY}", json={"recipe_id": recipe["id"], "is_cooked": False})
    leftover = client.post(
        "/api/listr/leftovers", json={"name": "Restje", "recipe_id": recipe["id"], "meals": 1, "location": "fridge"}
    ).json()

    assert client.delete(f"/api/listr/recipes/{recipe['id']}").status_code == 204

    day = client.get("/api/listr/meal-plan", params={"date_from": DAY, "date_to": DAY}).json()
    assert day == [] or day[0]["recipe_id"] is None
    assert next(l for l in client.get("/api/listr/leftovers").json() if l["id"] == leftover["id"])["recipe_id"] is None


# -- the three "add to a list" actions --------------------------------------------------------


def test_a_recipes_chosen_ingredients_go_onto_a_new_list(client):
    category_id = make_category(client)
    melk, eieren = make_item(client, "Melk", "liter", category_id), make_item(client, "Eieren", "stuks", category_id)
    recipe = make_recipe(
        client,
        ingredients=[{"grocery_item_id": melk["id"], "quantity": "0.5"}, {"grocery_item_id": eieren["id"], "quantity": "3"}],
    )
    chosen = [recipe["ingredients"][1]["id"]]

    created = client.post(
        f"/api/listr/recipes/{recipe['id']}/add-to-list", json={"new_list_name": "Pannenkoeken", "ingredient_ids": chosen}
    ).json()

    assert created["name"] == "Pannenkoeken"
    assert list_lines(client, created["id"]) == [("Eieren", Decimal("3"), "stuks")]


def test_an_ingredient_from_another_recipe_is_refused(client):
    melk = make_item(client)
    recipe = make_recipe(client, ingredients=[{"grocery_item_id": melk["id"], "quantity": "1"}])
    other = make_recipe(client, "Ander", ingredients=[{"grocery_item_id": melk["id"], "quantity": "1"}])
    response = client.post(
        f"/api/listr/recipes/{recipe['id']}/add-to-list",
        json={"new_list_name": "x", "ingredient_ids": [other["ingredients"][0]["id"]]},
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "path",
    ["/api/listr/inventory/add-to-list", "/api/listr/meal-plan/add-to-list", "/api/listr/recipes/{recipe}/add-to-list"],
)
def test_every_add_to_list_needs_a_list_or_a_name_and_an_existing_list(client, path):
    melk = make_item(client)
    recipe = make_recipe(client, ingredients=[{"grocery_item_id": melk["id"], "quantity": "1"}])
    path = path.format(recipe=recipe["id"])
    body = {"item_ids": [melk["id"]], "dates": [str(DAY)], "ingredient_ids": [recipe["ingredients"][0]["id"]]}

    assert client.post(path, json=body).status_code == 400
    assert client.post(path, json={**body, "list_id": 999}).status_code == 404
    list_id = make_list(client)
    assert client.post(path, json={**body, "list_id": list_id}).json()["id"] == list_id


def test_restocking_from_voorraad_adds_one_of_each_to_an_existing_list(client):
    category_id = make_category(client)
    melk, kaas = make_item(client, "Melk", "liter", category_id), make_item(client, "Kaas", "plak", category_id)
    list_id = make_list(client)

    result = client.post(
        "/api/listr/inventory/add-to-list", json={"item_ids": [melk["id"], kaas["id"]], "list_id": list_id}
    ).json()

    assert result["item_count"] == 2
    assert list_lines(client, list_id) == [("Kaas", Decimal("1"), "plak"), ("Melk", Decimal("1"), "liter")]
    missing = client.post("/api/listr/inventory/add-to-list", json={"item_ids": [999], "list_id": list_id})
    assert missing.status_code == 404


def test_a_planned_week_lands_on_one_list_with_shared_ingredients_summed(client):
    category_id = make_category(client)
    ui = make_item(client, "Ui", "stuks", category_id)
    soep = make_recipe(client, "Soep", ingredients=[{"grocery_item_id": ui["id"], "quantity": "2"}])
    curry = make_recipe(client, "Curry", ingredients=[{"grocery_item_id": ui["id"], "quantity": "1"}])
    client.put("/api/listr/meal-plan/2026-10-12", json={"recipe_id": soep["id"], "is_cooked": False})
    client.put("/api/listr/meal-plan/2026-10-13", json={"recipe_id": curry["id"], "is_cooked": False})

    created = client.post(
        "/api/listr/meal-plan/add-to-list",
        json={"dates": ["2026-10-12", "2026-10-13", "2026-10-14"], "new_list_name": "Week 42"},
    ).json()

    assert list_lines(client, created["id"]) == [("Ui", Decimal("3"), "stuks")]


# -- meal plan and leftovers ------------------------------------------------------------------


def test_a_day_needs_a_known_recipe_and_cant_carry_a_leftover_too(client):
    assert client.put(f"/api/listr/meal-plan/{DAY}", json={"recipe_id": 999, "is_cooked": False}).status_code == 404
    assert client.put(f"/api/listr/meal-plan/{DAY}", json={"leftover_id": 999, "is_cooked": False}).status_code == 404
    recipe = make_recipe(client)
    leftover = client.post("/api/listr/leftovers", json={"name": "Soep", "meals": 1, "location": "fridge"}).json()
    both = client.put(
        f"/api/listr/meal-plan/{DAY}", json={"recipe_id": recipe["id"], "leftover_id": leftover["id"], "is_cooked": False}
    )
    assert both.status_code == 400


def test_popular_recipes_count_cooked_days(client):
    recipe = make_recipe(client)
    client.put("/api/listr/meal-plan/2026-10-12", json={"recipe_id": recipe["id"], "is_cooked": True})
    client.put("/api/listr/meal-plan/2026-10-13", json={"recipe_id": recipe["id"], "is_cooked": True})
    popular = client.get("/api/listr/meal-plan/popular").json()
    assert popular[0]["recipe_id"] == recipe["id"]
    assert popular[0]["times_cooked"] >= 1


def test_a_leftover_needs_a_known_recipe(client):
    response = client.post("/api/listr/leftovers", json={"name": "x", "recipe_id": 999, "meals": 1, "location": "fridge"})
    assert response.status_code == 404


def test_patching_a_leftover_ignores_nulls_except_servings(client):
    leftover = client.post(
        "/api/listr/leftovers", json={"name": "Soep", "meals": 2, "servings_per_meal": 2, "location": "fridge"}
    ).json()
    patched = client.patch(
        f"/api/listr/leftovers/{leftover['id']}", json={"name": None, "servings_per_meal": None, "location": "freezer"}
    ).json()
    assert patched["name"] == "Soep"
    assert patched["servings_per_meal"] is None
    assert patched["location"] == "freezer"
    assert client.patch("/api/listr/leftovers/999", json={"name": "x"}).status_code == 404
    assert client.post("/api/listr/leftovers/999/meals", json={"delta": 1}).status_code == 404
    assert client.delete("/api/listr/leftovers/999").status_code == 404


# -- picnic sync settings ---------------------------------------------------------------------


def test_picnic_sync_settings_refuse_an_unknown_gripr_account_or_category(client, db_session):
    assert client.put("/api/listr/picnic/sync-settings", json={"enabled": True, "gripr_account_id": 999}).status_code == 400
    assert client.put("/api/listr/picnic/sync-settings", json={"enabled": True, "gripr_category_id": 999}).status_code == 400

    account = GriprAccount(name="ING", type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db_session.add(account)
    db_session.flush()
    saved = client.put(
        "/api/listr/picnic/sync-settings", json={"enabled": True, "gripr_account_id": account.id, "since": "2026-10-01"}
    ).json()
    assert saved["enabled"] is True
    assert saved["gripr_account_id"] == account.id
    assert client.get("/api/listr/picnic/sync-settings").json()["since"] == "2026-10-01"
