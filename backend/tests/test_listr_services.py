from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.listr_category import ListrCategory
from app.models.listr_item import ListrItem
from app.repositories import listr_list_repo
from app.routers import listr as listr_router
from app.services import listr_list_service
from app.services.listr_list_service import IngredientLine


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


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(listr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


# -- add_ingredients_to_list ------------------------------------------------------------------


def test_add_ingredients_creates_a_new_line_when_none_exists(db_session):
    item = make_item(db_session)
    grocery_list = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    db_session.commit()

    listr_list_service.add_ingredients_to_list(
        db_session, grocery_list.id, [IngredientLine(item.id, Decimal("2"), "kg")]
    )
    db_session.commit()

    lines = listr_list_repo.list_items(db_session, grocery_list.id)
    assert len(lines) == 1
    assert lines[0].quantity == Decimal("2")
    assert lines[0].unit == "kg"


def test_add_ingredients_merges_quantity_for_the_same_item_and_unit(db_session):
    item = make_item(db_session)
    grocery_list = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    db_session.commit()
    listr_list_service.add_ingredients_to_list(
        db_session, grocery_list.id, [IngredientLine(item.id, Decimal("2"), "kg")]
    )
    db_session.commit()

    listr_list_service.add_ingredients_to_list(
        db_session, grocery_list.id, [IngredientLine(item.id, Decimal("3"), "kg")]
    )
    db_session.commit()

    lines = listr_list_repo.list_items(db_session, grocery_list.id)
    assert len(lines) == 1
    assert lines[0].quantity == Decimal("5")


def test_add_ingredients_keeps_a_different_unit_as_a_separate_line(db_session):
    item = make_item(db_session)
    grocery_list = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    db_session.commit()
    listr_list_service.add_ingredients_to_list(
        db_session, grocery_list.id, [IngredientLine(item.id, Decimal("2"), "kg")]
    )
    db_session.commit()

    # Same item, different unit -- must not be silently combined with the kg line.
    listr_list_service.add_ingredients_to_list(
        db_session, grocery_list.id, [IngredientLine(item.id, Decimal("1"), "stuks")]
    )
    db_session.commit()

    lines = listr_list_repo.list_items(db_session, grocery_list.id)
    assert len(lines) == 2
    units = {line.unit: line.quantity for line in lines}
    assert units == {"kg": Decimal("2"), "stuks": Decimal("1")}


def test_add_ingredients_selecting_only_some_skips_the_rest(db_session):
    category = make_category(db_session)
    potatoes = make_item(db_session, "Aardappelen", category)
    onions = make_item(db_session, "Uien", category, default_unit="kg")
    grocery_list = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    db_session.commit()

    # Only add potatoes, as if the caller only selected that one ingredient from a recipe.
    listr_list_service.add_ingredients_to_list(
        db_session, grocery_list.id, [IngredientLine(potatoes.id, Decimal("1"), "kg")]
    )
    db_session.commit()

    lines = listr_list_repo.list_items(db_session, grocery_list.id)
    assert [l.grocery_item_id for l in lines] == [potatoes.id]
    assert onions.id not in [l.grocery_item_id for l in lines]


# -- clear_checked / duplicate_list ------------------------------------------------------------


def test_clear_checked_removes_only_checked_lines(db_session):
    category = make_category(db_session)
    a = make_item(db_session, "Aardappelen", category)
    b = make_item(db_session, "Uien", category)
    grocery_list = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    db_session.commit()
    listr_list_repo.create_list_item(
        db_session, list_id=grocery_list.id, grocery_item_id=a.id, quantity=Decimal(1), unit="kg", is_checked=True
    )
    line_b = listr_list_repo.create_list_item(
        db_session, list_id=grocery_list.id, grocery_item_id=b.id, quantity=Decimal(1), unit="kg", is_checked=False
    )
    db_session.commit()

    removed = listr_list_service.clear_checked(db_session, grocery_list.id)
    db_session.commit()

    assert removed == 1
    remaining = listr_list_repo.list_items(db_session, grocery_list.id)
    assert [l.id for l in remaining] == [line_b.id]


def test_duplicate_list_copies_items_as_unchecked(db_session):
    item = make_item(db_session)
    source = listr_list_repo.create_list(db_session, name="Weekboodschappen")
    db_session.commit()
    listr_list_repo.create_list_item(
        db_session, list_id=source.id, grocery_item_id=item.id, quantity=Decimal(2), unit="kg", is_checked=True
    )
    db_session.commit()

    new_list = listr_list_service.duplicate_list(db_session, source.id, "Weekboodschappen (kopie)")
    db_session.commit()

    assert new_list.name == "Weekboodschappen (kopie)"
    copied = listr_list_repo.list_items(db_session, new_list.id)
    assert len(copied) == 1
    assert copied[0].quantity == Decimal(2)
    assert copied[0].is_checked is False
    # The original is untouched.
    original = listr_list_repo.list_items(db_session, source.id)
    assert original[0].is_checked is True


# -- router: catalog get-or-create --------------------------------------------------------------


def test_creating_an_item_with_an_existing_name_returns_that_item(client, db_session):
    category = make_category(db_session)
    db_session.commit()

    first = client.post(
        "/api/listr/items", json={"name": "Aardappelen", "category_id": category.id, "default_unit": "kg"}
    )
    second = client.post(
        "/api/listr/items", json={"name": "Aardappelen", "category_id": category.id, "default_unit": "stuks"}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["default_unit"] == "kg"  # the original row, unchanged


# -- router: recipe with ingredients, add-to-list -----------------------------------------------


def test_recipe_ingredients_default_to_the_items_own_unit_when_omitted(client, db_session):
    category = make_category(db_session)
    item = make_item(db_session, "Aardappelen", category, default_unit="kg")
    db_session.commit()

    response = client.post(
        "/api/listr/recipes",
        json={
            "title": "Aardappelpuree",
            "servings": 4,
            "instructions": "Kook de aardappelen.",
            "ingredients": [{"grocery_item_id": item.id, "quantity": "1.5"}],
        },
    )

    assert response.status_code == 200
    ingredient = response.json()["ingredients"][0]
    assert ingredient["unit"] == "kg"
    assert ingredient["quantity"] == "1.500"


def test_add_recipe_to_a_new_list_with_only_some_ingredients_selected(client, db_session):
    category = make_category(db_session)
    potatoes = make_item(db_session, "Aardappelen", category)
    onions = make_item(db_session, "Uien", category)
    db_session.commit()

    recipe = client.post(
        "/api/listr/recipes",
        json={
            "title": "Stamppot",
            "ingredients": [
                {"grocery_item_id": potatoes.id, "quantity": "1", "unit": "kg"},
                {"grocery_item_id": onions.id, "quantity": "2", "unit": "stuks"},
            ],
        },
    ).json()
    potato_ingredient_id = recipe["ingredients"][0]["id"]

    response = client.post(
        f"/api/listr/recipes/{recipe['id']}/add-to-list",
        json={"new_list_name": "Stamppotavond", "ingredient_ids": [potato_ingredient_id]},
    )

    assert response.status_code == 200
    new_list_id = response.json()["id"]
    lines = client.get(f"/api/listr/lists/{new_list_id}").json()["items"]
    assert [l["grocery_item_name"] for l in lines] == ["Aardappelen"]


# -- router: inventory (see docs/adr/0015-listr-inventory.md) -----------------------------------


def test_untracked_items_are_excluded_from_the_inventory_list(client, db_session):
    category = make_category(db_session)
    make_item(db_session, "Aardappelen", category)
    db_session.commit()

    response = client.get("/api/listr/inventory")

    assert response.status_code == 200
    assert response.json() == []


def test_tracking_an_item_computes_its_initial_status(client, db_session):
    category = make_category(db_session)
    item = make_item(db_session, "Aardappelen", category)
    db_session.commit()

    set_response = client.put(f"/api/listr/items/{item.id}/inventory", json={"tracked": True})
    assert set_response.status_code == 200
    # Fresh item: count 0 -- always out, per _compute_inventory_status.
    assert set_response.json()["inventory_status"] == "out"

    listed = client.get("/api/listr/inventory").json()
    assert [i["name"] for i in listed] == ["Aardappelen"]


def test_untracking_an_item_clears_its_status_but_keeps_its_count(client, db_session):
    category = make_category(db_session)
    item = make_item(db_session, "Aardappelen", category)
    db_session.commit()
    client.put(f"/api/listr/items/{item.id}/inventory", json={"tracked": True})
    client.post(f"/api/listr/items/{item.id}/inventory/count", json={"delta": 5})

    response = client.put(f"/api/listr/items/{item.id}/inventory", json={"tracked": False})

    assert response.json()["inventory_status"] is None
    assert response.json()["inventory_count"] == 5
    assert client.get("/api/listr/inventory").json() == []


def test_status_follows_count_against_minimum_once_tracked(client, db_session):
    """The user's rule: >= minimum is in_stock, below it is low, 0 left is always out
    regardless of minimum."""
    category = make_category(db_session)
    item = make_item(db_session, "Aardappelen", category)
    db_session.commit()
    client.put(f"/api/listr/items/{item.id}/inventory", json={"tracked": True})
    client.post(f"/api/listr/items/{item.id}/inventory/minimum", json={"delta": 5})

    def status_after(count):
        client.post(f"/api/listr/items/{item.id}/inventory/count", json={"delta": count})
        status = client.get("/api/listr/inventory").json()[0]["inventory_status"]
        client.post(f"/api/listr/items/{item.id}/inventory/count", json={"delta": -count})
        return status

    assert status_after(10) == "in_stock"  # 10 >= 5
    assert status_after(3) == "low"  # 0 < 3 < 5
    assert status_after(1) == "low"  # 0 < 1 < 5, no floor override
    assert status_after(0) == "out"


def test_a_minimum_of_one_is_in_stock_at_count_one_not_out(client, db_session):
    """Regression: the earlier "0 or 1 is always out" floor overrode a minimum of 1 itself,
    permanently red-flagging fully-stocked single-unit items (reported against the freezer
    category, where several items are legitimately tracked at a minimum of 1)."""
    category = make_category(db_session)
    item = make_item(db_session, "Ovenfrites", category)
    db_session.commit()
    client.put(f"/api/listr/items/{item.id}/inventory", json={"tracked": True})
    client.post(f"/api/listr/items/{item.id}/inventory/minimum", json={"delta": 1})

    response = client.post(f"/api/listr/items/{item.id}/inventory/count", json={"delta": 1})

    assert response.json()["inventory_status"] == "in_stock"


def test_raising_the_minimum_can_tip_an_already_tracked_item_into_low(client, db_session):
    category = make_category(db_session)
    item = make_item(db_session, "Aardappelen", category)
    db_session.commit()
    client.put(f"/api/listr/items/{item.id}/inventory", json={"tracked": True})
    client.post(f"/api/listr/items/{item.id}/inventory/count", json={"delta": 3})
    assert client.get("/api/listr/inventory").json()[0]["inventory_status"] == "in_stock"

    response = client.post(f"/api/listr/items/{item.id}/inventory/minimum", json={"delta": 10})

    assert response.json()["inventory_status"] == "low"


def test_setting_a_minimum_while_untracked_is_remembered_but_has_no_status_yet(client, db_session):
    category = make_category(db_session)
    item = make_item(db_session, "Aardappelen", category)
    db_session.commit()

    response = client.post(f"/api/listr/items/{item.id}/inventory/minimum", json={"delta": 5})

    assert response.json()["inventory_status"] is None
    assert response.json()["inventory_minimum"] == 5


def test_inventory_minimum_never_goes_below_zero(client, db_session):
    category = make_category(db_session)
    item = make_item(db_session, "Aardappelen", category)
    db_session.commit()

    response = client.post(f"/api/listr/items/{item.id}/inventory/minimum", json={"delta": -1})

    assert response.json()["inventory_minimum"] == 0


def test_add_inventory_items_to_a_new_list_at_quantity_one(client, db_session):
    category = make_category(db_session)
    potatoes = make_item(db_session, "Aardappelen", category, default_unit="kg")
    onions = make_item(db_session, "Uien", category, default_unit="stuks")
    db_session.commit()
    client.put(f"/api/listr/items/{potatoes.id}/inventory", json={"tracked": True})
    client.put(f"/api/listr/items/{onions.id}/inventory", json={"tracked": True})

    response = client.post(
        "/api/listr/inventory/add-to-list",
        json={"new_list_name": "Aanvullen", "item_ids": [potatoes.id, onions.id]},
    )

    assert response.status_code == 200
    lines = client.get(f"/api/listr/lists/{response.json()['id']}").json()["items"]
    by_name = {l["grocery_item_name"]: l for l in lines}
    assert by_name["Aardappelen"]["quantity"] == "1.000"
    assert by_name["Aardappelen"]["unit"] == "kg"
    assert by_name["Uien"]["unit"] == "stuks"


def test_a_new_item_starts_at_inventory_count_zero(client, db_session):
    category = make_category(db_session)
    make_item(db_session, "Aardappelen", category)
    db_session.commit()

    assert client.get(f"/api/listr/items?category_id={category.id}").json()[0]["inventory_count"] == 0


def test_inventory_count_increments_and_decrements_by_delta(client, db_session):
    category = make_category(db_session)
    item = make_item(db_session, "Aardappelen", category)
    db_session.commit()

    up = client.post(f"/api/listr/items/{item.id}/inventory/count", json={"delta": 1})
    assert up.json()["inventory_count"] == 1
    up_again = client.post(f"/api/listr/items/{item.id}/inventory/count", json={"delta": 1})
    assert up_again.json()["inventory_count"] == 2
    down = client.post(f"/api/listr/items/{item.id}/inventory/count", json={"delta": -1})
    assert down.json()["inventory_count"] == 1


def test_inventory_count_never_goes_below_zero(client, db_session):
    category = make_category(db_session)
    item = make_item(db_session, "Aardappelen", category)
    db_session.commit()

    response = client.post(f"/api/listr/items/{item.id}/inventory/count", json={"delta": -1})

    assert response.json()["inventory_count"] == 0
