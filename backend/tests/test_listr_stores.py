"""listr's supermarkets: each is an order of the categories (its aisles), and a list set to one shows
its groups in that order (docs/adr/0052-listr-store-order.md)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.routers import listr as listr_router
from tests.test_listr_router import make_category, make_item, make_list


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(listr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def make_store(client, name="Jumbo", **extra) -> dict:
    response = client.post("/api/listr/stores", json={"name": name, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def categories(client, *names) -> dict[str, int]:
    return {name: make_category(client, name) for name in names}


def order(client, list_id) -> list[int]:
    return client.get(f"/api/listr/lists/{list_id}").json()["category_order"]


# -- stores ---------------------------------------------------------------------------------


def test_a_store_is_created_trimmed_and_listed(client):
    store = make_store(client, "  Jumbo  ")

    assert store["name"] == "Jumbo"
    assert store["category_ids"] == [] and store["is_archived"] is False
    assert [s["name"] for s in client.get("/api/listr/stores").json()] == ["Jumbo"]


def test_stores_are_listed_in_the_order_they_were_added(client):
    for name in ("Jumbo", "Albert Heijn", "Markt"):
        make_store(client, name)

    assert [s["name"] for s in client.get("/api/listr/stores").json()] == ["Jumbo", "Albert Heijn", "Markt"]


def test_a_store_needs_a_name_and_a_name_only_once(client):
    make_store(client, "Jumbo")

    assert client.post("/api/listr/stores", json={"name": "   "}).status_code in (400, 422)
    assert client.post("/api/listr/stores", json={"name": "Jumbo"}).status_code == 409
    other = make_store(client, "Lidl")
    assert client.put(f"/api/listr/stores/{other['id']}", json={"name": "Jumbo"}).status_code == 409


def test_a_store_can_be_renamed_and_archived(client):
    store = make_store(client, "Jumbo")

    renamed = client.put(f"/api/listr/stores/{store['id']}", json={"name": "Jumbo Zuid"}).json()
    client.put(f"/api/listr/stores/{store['id']}", json={"is_archived": True})

    assert renamed["name"] == "Jumbo Zuid"
    assert client.get("/api/listr/stores").json() == []
    assert len(client.get("/api/listr/stores", params={"include_archived": True}).json()) == 1
    assert client.put("/api/listr/stores/99", json={"name": "x"}).status_code == 404


def test_keeping_its_own_name_is_not_a_clash(client):
    store = make_store(client, "Jumbo")

    assert client.put(f"/api/listr/stores/{store['id']}", json={"name": "Jumbo", "is_archived": False}).status_code == 200


# -- the aisle order ------------------------------------------------------------------------


def test_the_aisles_of_a_store_are_set_in_walking_order(client):
    c = categories(client, "Zuivel", "Groente", "Brood")
    store = make_store(client)

    done = client.put(f"/api/listr/stores/{store['id']}/order", json={"category_ids": [c["Brood"], c["Zuivel"]]}).json()

    assert done["category_ids"] == [c["Brood"], c["Zuivel"]]
    # what an editor lists: the arranged aisles, then the rest in the global order
    assert done["category_order"] == [c["Brood"], c["Zuivel"], c["Groente"]]
    assert client.get("/api/listr/stores").json()[0]["category_ids"] == [c["Brood"], c["Zuivel"]]


def test_setting_the_order_again_replaces_it_and_ignores_repeats(client):
    c = categories(client, "Zuivel", "Groente")
    store = make_store(client)
    client.put(f"/api/listr/stores/{store['id']}/order", json={"category_ids": [c["Zuivel"], c["Groente"]]})

    done = client.put(
        f"/api/listr/stores/{store['id']}/order", json={"category_ids": [c["Groente"], c["Zuivel"], c["Groente"]]}
    ).json()

    assert done["category_ids"] == [c["Groente"], c["Zuivel"]]


def test_an_order_with_an_unknown_category_is_refused_and_changes_nothing(client):
    c = categories(client, "Zuivel")
    store = make_store(client)
    client.put(f"/api/listr/stores/{store['id']}/order", json={"category_ids": [c["Zuivel"]]})

    assert client.put(f"/api/listr/stores/{store['id']}/order", json={"category_ids": [999]}).status_code == 400
    assert client.get("/api/listr/stores").json()[0]["category_ids"] == [c["Zuivel"]]
    assert client.put("/api/listr/stores/99/order", json={"category_ids": []}).status_code == 404


def test_a_new_store_can_start_from_another_stores_order(client):
    c = categories(client, "Zuivel", "Groente", "Brood")
    jumbo = make_store(client, "Jumbo")
    client.put(f"/api/listr/stores/{jumbo['id']}/order", json={"category_ids": [c["Brood"], c["Groente"], c["Zuivel"]]})

    copy = make_store(client, "Jumbo Noord", copy_order_from_id=jumbo["id"])

    assert copy["category_ids"] == [c["Brood"], c["Groente"], c["Zuivel"]]
    # a copy, not a link: arranging it leaves the original alone
    client.put(f"/api/listr/stores/{copy['id']}/order", json={"category_ids": [c["Zuivel"]]})
    assert client.get("/api/listr/stores").json()[0]["category_ids"] == [c["Brood"], c["Groente"], c["Zuivel"]]
    assert client.post("/api/listr/stores", json={"name": "X", "copy_order_from_id": 99}).status_code == 404


# -- a list follows its store ---------------------------------------------------------------


def test_a_list_without_a_store_follows_the_global_category_order(client):
    c = categories(client, "Zuivel", "Groente", "Brood")
    list_id = make_list(client)

    # a new category goes last, so until someone arranges them it's the order they were made in
    assert order(client, list_id) == [c["Zuivel"], c["Groente"], c["Brood"]]
    client.put("/api/listr/categories/reorder", json={"category_ids": [c["Zuivel"], c["Brood"], c["Groente"]]})
    assert order(client, list_id) == [c["Zuivel"], c["Brood"], c["Groente"]]


def test_a_list_set_to_a_store_shows_the_stores_aisles_first_then_the_rest(client):
    c = categories(client, "Zuivel", "Groente", "Brood", "Diepvries")
    store = make_store(client)
    client.put(f"/api/listr/stores/{store['id']}/order", json={"category_ids": [c["Groente"], c["Zuivel"]]})
    list_id = make_list(client)

    updated = client.put(f"/api/listr/lists/{list_id}", json={"store_id": store["id"]}).json()

    assert updated["store_id"] == store["id"]
    # Brood and Diepvries aren't arranged yet: after the aisles, in the global order
    assert order(client, list_id) == [c["Groente"], c["Zuivel"], c["Brood"], c["Diepvries"]]
    assert client.get(f"/api/listr/lists/{list_id}").json()["store_id"] == store["id"]


def test_a_category_added_later_slots_in_after_the_stores_aisles(client):
    c = categories(client, "Zuivel", "Groente")
    store = make_store(client)
    client.put(f"/api/listr/stores/{store['id']}/order", json={"category_ids": [c["Groente"], c["Zuivel"]]})
    list_id = make_list(client)
    client.put(f"/api/listr/lists/{list_id}", json={"store_id": store["id"]})

    new = make_category(client, "Bakkerij")

    assert order(client, list_id) == [c["Groente"], c["Zuivel"], new]


def test_an_archived_category_keeps_its_place_so_its_lines_still_group(client):
    c = categories(client, "Zuivel", "Groente")
    item = make_item(client, "Melk", category_id=c["Zuivel"])
    list_id = make_list(client)
    client.post(f"/api/listr/lists/{list_id}/items", json={"grocery_item_id": item["id"]})
    client.put(f"/api/listr/categories/{c['Zuivel']}", json={"is_archived": True})

    assert c["Zuivel"] in order(client, list_id)


def test_the_store_can_be_changed_and_cleared_on_a_list(client):
    c = categories(client, "Zuivel", "Groente")
    store = make_store(client)
    client.put(f"/api/listr/stores/{store['id']}/order", json={"category_ids": [c["Groente"], c["Zuivel"]]})
    list_id = make_list(client)
    client.put(f"/api/listr/lists/{list_id}", json={"store_id": store["id"]})
    assert order(client, list_id) == [c["Groente"], c["Zuivel"]]

    client.put(f"/api/listr/lists/{list_id}", json={"store_id": None})

    assert client.get(f"/api/listr/lists/{list_id}").json()["store_id"] is None
    assert order(client, list_id) == [c["Zuivel"], c["Groente"]]


def test_a_list_cannot_follow_a_store_that_does_not_exist(client):
    list_id = make_list(client)

    assert client.put(f"/api/listr/lists/{list_id}", json={"store_id": 99}).status_code == 404
    assert client.get(f"/api/listr/lists/{list_id}").json()["store_id"] is None


def test_renaming_a_list_leaves_its_store_alone(client):
    store = make_store(client)
    list_id = make_list(client)
    client.put(f"/api/listr/lists/{list_id}", json={"store_id": store["id"]})

    client.put(f"/api/listr/lists/{list_id}", json={"name": "BBQ"})

    assert client.get(f"/api/listr/lists/{list_id}").json()["store_id"] == store["id"]


def test_the_lists_overview_carries_each_lists_store(client):
    store = make_store(client)
    list_id = make_list(client)
    client.put(f"/api/listr/lists/{list_id}", json={"store_id": store["id"]})

    assert client.get("/api/listr/lists").json()[0]["store_id"] == store["id"]


def test_a_duplicated_list_keeps_the_store(client):
    store = make_store(client)
    list_id = make_list(client)
    client.put(f"/api/listr/lists/{list_id}", json={"store_id": store["id"]})

    copy = client.post(f"/api/listr/lists/{list_id}/duplicate", json={"name": "Volgende week"}).json()

    assert copy["store_id"] == store["id"]


def test_deleting_a_store_sends_its_lists_back_to_the_global_order(client):
    c = categories(client, "Zuivel", "Groente")
    store = make_store(client)
    client.put(f"/api/listr/stores/{store['id']}/order", json={"category_ids": [c["Zuivel"]]})
    list_id = make_list(client)
    client.put(f"/api/listr/lists/{list_id}", json={"store_id": store["id"]})

    assert client.delete(f"/api/listr/stores/{store['id']}").status_code == 204

    assert client.get("/api/listr/stores", params={"include_archived": True}).json() == []
    assert client.get(f"/api/listr/lists/{list_id}").json()["store_id"] is None
    assert client.delete(f"/api/listr/stores/{store['id']}").status_code == 404
