"""Covers the Journal tab: notes aggregated across every position, and labels.

A note can be written from a position's own Notes tab (assets.router, linked to that one asset)
or from the Journal (journal.router, linked to one or more assets) -- these tests mount both
routers together to prove a note written through one surface is immediately visible through the
other, since they're the same table with no sync step (see PositionNote's own docstring).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.asset import Asset
from app.routers import assets as assets_router
from app.routers import journal as journal_router


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(assets_router.router)
    app.include_router(journal_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def asset(db_session) -> Asset:
    a = Asset(ticker="ACME", name="Acme Inc", asset_class="equity", native_currency="EUR")
    db_session.add(a)
    db_session.flush()
    db_session.commit()
    return a


def test_a_note_added_via_the_position_view_shows_up_in_the_journal(client, asset):
    client.post(f"/api/assets/{asset.id}/notes", json={"title": "Thesis", "body": "Long-term hold."})

    journal = client.get("/api/journal/notes").json()

    assert len(journal) == 1
    assert journal[0]["title"] == "Thesis"
    assert journal[0]["assets"] == [{"id": asset.id, "ticker": "ACME", "name": "Acme Inc"}]


def test_a_note_added_via_the_journal_shows_up_on_the_position(client, asset):
    client.post("/api/journal/notes", json={"title": "Earnings beat", "body": "Q3 was strong.", "asset_ids": [asset.id]})

    position_notes = client.get(f"/api/assets/{asset.id}/notes").json()

    assert [n["title"] for n in position_notes] == ["Earnings beat"]


def test_journal_lists_notes_across_multiple_positions_newest_first(client, db_session):
    a = Asset(ticker="AAA", name="Alpha", asset_class="equity", native_currency="EUR")
    b = Asset(ticker="BBB", name="Beta", asset_class="equity", native_currency="EUR")
    db_session.add_all([a, b])
    db_session.flush()
    db_session.commit()
    client.post(f"/api/assets/{a.id}/notes", json={"title": "First", "body": "..."})
    client.post(f"/api/assets/{b.id}/notes", json={"title": "Second", "body": "..."})

    titles = [n["title"] for n in client.get("/api/journal/notes").json()]

    assert titles == ["Second", "First"]


def test_creating_a_note_with_labels_attaches_them(client, asset):
    label = client.post("/api/journal/labels", json={"name": "Thesis"}).json()

    note = client.post(
        f"/api/assets/{asset.id}/notes", json={"title": "T", "body": "B", "label_ids": [label["id"]]}
    ).json()

    assert [l["name"] for l in note["labels"]] == ["Thesis"]
    journal = client.get("/api/journal/notes").json()
    assert [l["name"] for l in journal[0]["labels"]] == ["Thesis"]


def test_omitting_label_ids_on_update_leaves_labels_alone(client, asset):
    label = client.post("/api/journal/labels", json={"name": "Risk"}).json()
    note = client.post(
        f"/api/assets/{asset.id}/notes", json={"title": "T", "body": "B", "label_ids": [label["id"]]}
    ).json()

    updated = client.put(f"/api/assets/{asset.id}/notes/{note['id']}", json={"title": "T2"}).json()

    assert updated["title"] == "T2"
    assert [l["name"] for l in updated["labels"]] == ["Risk"]


def test_sending_an_empty_label_ids_list_clears_labels(client, asset):
    label = client.post("/api/journal/labels", json={"name": "Risk"}).json()
    note = client.post(
        f"/api/assets/{asset.id}/notes", json={"title": "T", "body": "B", "label_ids": [label["id"]]}
    ).json()

    updated = client.put(f"/api/assets/{asset.id}/notes/{note['id']}", json={"label_ids": []}).json()

    assert updated["labels"] == []


def test_creating_a_label_with_an_existing_name_returns_that_label(client):
    first = client.post("/api/journal/labels", json={"name": "Thesis"}).json()
    second = client.post("/api/journal/labels", json={"name": "Thesis"}).json()

    assert second["id"] == first["id"]


def test_reordering_labels(client):
    first = client.post("/api/journal/labels", json={"name": "A"}).json()
    second = client.post("/api/journal/labels", json={"name": "B"}).json()

    client.put("/api/journal/labels/reorder", json={"label_ids": [second["id"], first["id"]]})

    names = [l["name"] for l in client.get("/api/journal/labels").json()]
    assert names == ["B", "A"]


def test_archiving_a_label_hides_it_by_default(client):
    label = client.post("/api/journal/labels", json={"name": "Old"}).json()

    client.put(f"/api/journal/labels/{label['id']}", json={"is_archived": True})

    assert client.get("/api/journal/labels").json() == []
    assert len(client.get("/api/journal/labels?include_archived=true").json()) == 1


# -- one note, several positions -----------------------------------------------------------------


def make_asset(db_session, ticker, name) -> Asset:
    a = Asset(ticker=ticker, name=name, asset_class="equity", native_currency="USD")
    db_session.add(a)
    db_session.commit()
    return a


def test_a_journal_note_can_be_about_several_positions_and_shows_on_each(client, db_session):
    amzn = make_asset(db_session, "AMZN", "Amazon.com Inc")
    googl = make_asset(db_session, "GOOGL", "Alphabet Inc Class A")
    other = make_asset(db_session, "NU", "Nu Holdings Ltd.")

    note = client.post(
        "/api/journal/notes", json={"title": "Cloud capex", "body": "...", "asset_ids": [googl.id, amzn.id]}
    ).json()

    assert [a["ticker"] for a in note["assets"]] == ["AMZN", "GOOGL"]
    assert [n["title"] for n in client.get(f"/api/assets/{amzn.id}/notes").json()] == ["Cloud capex"]
    assert [n["title"] for n in client.get(f"/api/assets/{googl.id}/notes").json()] == ["Cloud capex"]
    assert client.get(f"/api/assets/{other.id}/notes").json() == []
    assert len(client.get("/api/journal/notes").json()) == 1


def test_relinking_a_note_moves_it_between_positions(client, db_session):
    amzn = make_asset(db_session, "AMZN", "Amazon.com Inc")
    googl = make_asset(db_session, "GOOGL", "Alphabet Inc Class A")
    note = client.post("/api/journal/notes", json={"title": "T", "body": "B", "asset_ids": [amzn.id]}).json()

    updated = client.put(f"/api/journal/notes/{note['id']}", json={"asset_ids": [googl.id]}).json()

    assert [a["ticker"] for a in updated["assets"]] == ["GOOGL"]
    assert client.get(f"/api/assets/{amzn.id}/notes").json() == []


def test_editing_a_journal_note_without_asset_ids_keeps_its_positions(client, db_session):
    amzn = make_asset(db_session, "AMZN", "Amazon.com Inc")
    note = client.post("/api/journal/notes", json={"title": "T", "body": "B", "asset_ids": [amzn.id]}).json()

    updated = client.put(f"/api/journal/notes/{note['id']}", json={"title": "T2"}).json()

    assert updated["title"] == "T2"
    assert [a["ticker"] for a in updated["assets"]] == ["AMZN"]


def test_a_journal_note_needs_at_least_one_real_position(client, db_session):
    amzn = make_asset(db_session, "AMZN", "Amazon.com Inc")

    assert client.post("/api/journal/notes", json={"title": "T", "body": "B", "asset_ids": []}).status_code == 422
    assert client.post("/api/journal/notes", json={"title": "T", "body": "B", "asset_ids": [amzn.id, 9999]}).status_code == 400
    note = client.post("/api/journal/notes", json={"title": "T", "body": "B", "asset_ids": [amzn.id]}).json()
    assert client.put(f"/api/journal/notes/{note['id']}", json={"asset_ids": []}).status_code == 422


def test_deleting_a_shared_note_removes_it_everywhere(client, db_session):
    amzn = make_asset(db_session, "AMZN", "Amazon.com Inc")
    googl = make_asset(db_session, "GOOGL", "Alphabet Inc Class A")
    note = client.post("/api/journal/notes", json={"title": "T", "body": "B", "asset_ids": [amzn.id, googl.id]}).json()

    assert client.delete(f"/api/assets/{amzn.id}/notes/{note['id']}").status_code == 204

    assert client.get(f"/api/assets/{googl.id}/notes").json() == []
    assert client.get("/api/journal/notes").json() == []


def test_a_position_can_only_edit_notes_linked_to_it(client, db_session):
    amzn = make_asset(db_session, "AMZN", "Amazon.com Inc")
    googl = make_asset(db_session, "GOOGL", "Alphabet Inc Class A")
    note = client.post("/api/journal/notes", json={"title": "T", "body": "B", "asset_ids": [amzn.id]}).json()

    assert client.put(f"/api/assets/{googl.id}/notes/{note['id']}", json={"title": "X"}).status_code == 404
    assert client.delete(f"/api/assets/{googl.id}/notes/{note['id']}").status_code == 404
    assert client.put(f"/api/assets/{amzn.id}/notes/{note['id']}", json={"title": "X"}).status_code == 200


def test_the_journal_delete_endpoint_removes_the_note(client, db_session):
    amzn = make_asset(db_session, "AMZN", "Amazon.com Inc")
    note = client.post("/api/journal/notes", json={"title": "T", "body": "B", "asset_ids": [amzn.id]}).json()

    assert client.delete(f"/api/journal/notes/{note['id']}").status_code == 204
    assert client.delete(f"/api/journal/notes/{note['id']}").status_code == 404
