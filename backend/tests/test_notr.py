"""notr: notes with labels, links to positions, plants and recipes, and pictures.

gainr's Journal is a view of the same rows (positions_only), and a position's, plant's or
recipe's own Notes are filtered views too -- these tests mount the routers together to prove one
note written anywhere shows everywhere (docs/adr/0050-notr-notes.md).
"""

import io
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.db import get_db
from app.models.asset import Asset
from app.models.notr_note_image import NotrNoteImage
from app.routers import gardnr as gardnr_router
from app.routers import listr as listr_router
from app.routers import notr as notr_router
from app.services import notr_note_service

NOW = datetime(2026, 10, 20, 12, 0)


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(notr_router.router)
    app.include_router(gardnr_router.router)
    app.include_router(listr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def asset(db_session) -> Asset:
    a = Asset(ticker="ACME", name="Acme Inc", asset_class="equity", native_currency="EUR")
    db_session.add(a)
    db_session.flush()
    db_session.commit()
    return a


def make_asset(db_session, ticker) -> Asset:
    a = Asset(ticker=ticker, name=f"{ticker} Inc", asset_class="equity", native_currency="EUR")
    db_session.add(a)
    db_session.flush()
    db_session.commit()
    return a


def make_plant(client, name="Japanese Maple") -> int:
    area = client.post("/api/gardnr/areas", json={"name": "Back yard"}).json()["id"]
    return client.post("/api/gardnr/plants", json={"area_id": area, "name": name, "type": "tree"}).json()["id"]


def make_recipe(client, title="Pannenkoeken") -> int:
    return client.post("/api/listr/recipes", json={"title": title, "servings": 4, "ingredients": [], "category_ids": []}).json()["id"]


def note(client, **fields) -> dict:
    response = client.post("/api/notr/notes", json={"title": "A note", "body": "Some text.", **fields})
    assert response.status_code == 200, response.text
    return response.json()


def image_bytes(size=(10, 10), fmt="PNG", mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color=(0, 128, 0) if mode == "RGB" else (0, 128, 0, 0)).save(buf, format=fmt)
    return buf.getvalue()


def upload(client, content: bytes, name="pic.png"):
    return client.post("/api/notr/images", files={"image": (name, content)})


# -- notes ----------------------------------------------------------------------------------


def test_a_plain_note_needs_no_links_and_not_even_a_title(client):
    created = client.post("/api/notr/notes", json={"body": "Remember the milk"}).json()

    assert created["title"] == ""
    assert created["assets"] == created["plants"] == created["recipes"] == []
    assert created["pinned"] is False and created["is_archived"] is False
    assert client.get(f"/api/notr/notes/{created['id']}").json()["body"] == "Remember the milk"


def test_an_unknown_note_is_a_404(client):
    assert client.get("/api/notr/notes/99").status_code == 404
    assert client.put("/api/notr/notes/99", json={"title": "x"}).status_code == 404
    assert client.delete("/api/notr/notes/99").status_code == 404


def test_a_note_can_be_about_a_position_a_plant_and_a_recipe(client, asset):
    plant_id, recipe_id = make_plant(client), make_recipe(client)

    created = note(client, asset_ids=[asset.id], plant_ids=[plant_id], recipe_ids=[recipe_id])

    assert created["assets"] == [{"id": asset.id, "ticker": "ACME", "name": "Acme Inc"}]
    assert created["plants"] == [{"id": plant_id, "name": "Japanese Maple"}]
    assert created["recipes"] == [{"id": recipe_id, "title": "Pannenkoeken"}]


def test_a_link_to_something_that_does_not_exist_is_refused(client):
    for field in ("asset_ids", "plant_ids", "recipe_ids"):
        response = client.post("/api/notr/notes", json={"title": "x", field: [999]})
        assert response.status_code == 400
        assert client.get("/api/notr/notes").json() == []


def test_a_note_written_for_a_position_shows_in_the_journal_and_on_the_position(client, asset, db_session):
    other = make_asset(db_session, "OTHER")
    note(client, title="Thesis", asset_ids=[asset.id])
    note(client, title="Shopping list")

    journal = client.get("/api/notr/notes", params={"positions_only": True}).json()
    on_position = client.get("/api/notr/notes", params={"asset_id": asset.id}).json()

    assert [n["title"] for n in journal] == ["Thesis"]
    assert [n["title"] for n in on_position] == ["Thesis"]
    assert client.get("/api/notr/notes", params={"asset_id": other.id}).json() == []
    assert {n["title"] for n in client.get("/api/notr/notes").json()} == {"Thesis", "Shopping list"}


def test_a_note_about_several_positions_shows_on_each(client, db_session):
    a, b = make_asset(db_session, "AAA"), make_asset(db_session, "BBB")
    note(client, title="Sector view", asset_ids=[b.id, a.id])

    for asset_id in (a.id, b.id):
        assert [n["title"] for n in client.get("/api/notr/notes", params={"asset_id": asset_id}).json()] == ["Sector view"]
    # ordered by ticker, whatever order they were picked in
    assert [x["ticker"] for x in client.get("/api/notr/notes").json()[0]["assets"]] == ["AAA", "BBB"]


def test_plant_and_recipe_notes_are_filtered_by_what_they_are_about(client):
    plant_id, recipe_id = make_plant(client), make_recipe(client)
    note(client, title="Prune in March", plant_ids=[plant_id])
    note(client, title="Less sugar", recipe_ids=[recipe_id])

    assert [n["title"] for n in client.get("/api/notr/notes", params={"plant_id": plant_id}).json()] == ["Prune in March"]
    assert [n["title"] for n in client.get("/api/notr/notes", params={"recipe_id": recipe_id}).json()] == ["Less sugar"]


def test_deleting_a_plant_or_recipe_keeps_the_note_and_drops_the_link(client):
    plant_id, recipe_id = make_plant(client), make_recipe(client)
    created = note(client, plant_ids=[plant_id], recipe_ids=[recipe_id])

    assert client.delete(f"/api/gardnr/plants/{plant_id}").status_code == 204
    assert client.delete(f"/api/listr/recipes/{recipe_id}").status_code == 204

    after = client.get(f"/api/notr/notes/{created['id']}").json()
    assert after["plants"] == [] and after["recipes"] == []


def test_search_matches_title_and_body_and_takes_symbols_literally(client):
    note(client, title="Dividend plan", body="Reinvest")
    note(client, title="Other", body="Growth is 100% of the goal")
    note(client, title="Third", body="no symbols here")

    def titles(q):
        return sorted(n["title"] for n in client.get("/api/notr/notes", params={"q": q}).json())

    assert titles("dividend") == ["Dividend plan"]
    assert titles("reinvest") == ["Dividend plan"]
    assert titles("100%") == ["Other"]
    assert titles("%") == ["Other"]
    assert titles("a_b") == []
    assert len(client.get("/api/notr/notes", params={"q": "  "}).json()) == 3


def test_pinned_notes_come_first_then_newest(client):
    note(client, title="Old", created_at="2026-01-01T10:00:00")
    note(client, title="New", created_at="2026-06-01T10:00:00")
    note(client, title="Pinned old", created_at="2025-01-01T10:00:00", pinned=True)

    assert [n["title"] for n in client.get("/api/notr/notes").json()] == ["Pinned old", "New", "Old"]


def test_archived_notes_are_left_out_unless_asked_for(client):
    kept, gone = note(client, title="Kept"), note(client, title="Gone")
    client.put(f"/api/notr/notes/{gone['id']}", json={"is_archived": True})

    assert [n["title"] for n in client.get("/api/notr/notes").json()] == ["Kept"]
    assert [n["title"] for n in client.get("/api/notr/notes", params={"archived": True}).json()] == ["Gone"]
    assert kept["is_archived"] is False


def test_labels_filter_notes_and_are_get_or_create_by_name(client):
    first = client.post("/api/notr/labels", json={"name": "Thesis"}).json()
    again = client.post("/api/notr/labels", json={"name": "Thesis"}).json()
    other = client.post("/api/notr/labels", json={"name": "Risk"}).json()
    assert first["id"] == again["id"] != other["id"]
    note(client, title="Tagged", label_ids=[first["id"]])
    note(client, title="Untagged")

    tagged = client.get("/api/notr/notes", params={"label_id": first["id"]}).json()

    assert [n["title"] for n in tagged] == ["Tagged"]
    assert [lbl["name"] for lbl in tagged[0]["labels"]] == ["Thesis"]


def test_labels_reorder_and_archive(client):
    a = client.post("/api/notr/labels", json={"name": "A"}).json()["id"]
    b = client.post("/api/notr/labels", json={"name": "B"}).json()["id"]
    client.put("/api/notr/labels/reorder", json={"label_ids": [b, a]})
    assert [lbl["name"] for lbl in client.get("/api/notr/labels").json()] == ["B", "A"]

    client.put(f"/api/notr/labels/{a}", json={"is_archived": True})
    assert [lbl["name"] for lbl in client.get("/api/notr/labels").json()] == ["B"]
    assert len(client.get("/api/notr/labels", params={"include_archived": True}).json()) == 2
    assert client.post("/api/notr/labels", json={"name": "   "}).status_code in (400, 422)
    assert client.put("/api/notr/labels/999", json={"color": "#112233"}).status_code == 404


def test_omitting_links_and_labels_on_update_leaves_them_alone(client, asset):
    label = client.post("/api/notr/labels", json={"name": "Thesis"}).json()["id"]
    created = note(client, asset_ids=[asset.id], label_ids=[label], plant_ids=[make_plant(client)])

    updated = client.put(f"/api/notr/notes/{created['id']}", json={"title": "Renamed"}).json()

    assert updated["title"] == "Renamed"
    assert len(updated["assets"]) == len(updated["labels"]) == len(updated["plants"]) == 1


def test_an_empty_list_clears_links_and_labels(client, asset):
    label = client.post("/api/notr/labels", json={"name": "Thesis"}).json()["id"]
    created = note(client, asset_ids=[asset.id], label_ids=[label])

    cleared = client.put(
        f"/api/notr/notes/{created['id']}", json={"asset_ids": [], "label_ids": [], "plant_ids": [], "recipe_ids": []}
    ).json()

    assert cleared["assets"] == cleared["labels"] == []


def test_relinking_a_note_moves_it_between_positions(client, db_session):
    a, b = make_asset(db_session, "AAA"), make_asset(db_session, "BBB")
    created = note(client, asset_ids=[a.id])

    client.put(f"/api/notr/notes/{created['id']}", json={"asset_ids": [b.id]})

    assert client.get("/api/notr/notes", params={"asset_id": a.id}).json() == []
    assert len(client.get("/api/notr/notes", params={"asset_id": b.id}).json()) == 1


def test_deleting_a_note_removes_it_everywhere(client, asset):
    created = note(client, asset_ids=[asset.id])

    assert client.delete(f"/api/notr/notes/{created['id']}").status_code == 204

    assert client.get("/api/notr/notes", params={"positions_only": True}).json() == []
    assert client.get("/api/notr/notes", params={"asset_id": asset.id}).json() == []


def test_a_note_can_be_dated_for_the_day_it_is_about(client):
    created = note(client, created_at="2025-03-01T09:30:00+01:00")

    assert created["created_at"].startswith("2025-03-01T08:30:00")
    assert created["updated_at"] == created["created_at"]


def test_a_note_without_a_date_is_dated_now_in_utc(client):
    created = note(client)

    assert created["created_at"].endswith("+00:00")


# -- tasks ----------------------------------------------------------------------------------

CHECKLIST = "Plan\n\n- [ ] one\n- [x] two\n  - [ ] nested\n\n1. [ ] numbered\n- plain bullet\n"


def test_ticking_a_checkbox_changes_just_that_task(client):
    created = note(client, body=CHECKLIST)

    ticked = client.put(f"/api/notr/notes/{created['id']}/tasks", json={"index": 0, "checked": True}).json()
    assert ticked["body"] == CHECKLIST.replace("- [ ] one", "- [x] one")

    unticked = client.put(f"/api/notr/notes/{created['id']}/tasks", json={"index": 1, "checked": False}).json()
    assert "- [ ] two" in unticked["body"] and "- [x] one" in unticked["body"]

    nested = client.put(f"/api/notr/notes/{created['id']}/tasks", json={"index": 2, "checked": True}).json()
    assert "  - [x] nested" in nested["body"]

    numbered = client.put(f"/api/notr/notes/{created['id']}/tasks", json={"index": 3, "checked": True}).json()
    assert "1. [x] numbered" in numbered["body"]


def test_a_task_that_is_not_there_is_a_404(client):
    created = note(client, body=CHECKLIST)

    assert client.put(f"/api/notr/notes/{created['id']}/tasks", json={"index": 9, "checked": True}).status_code == 404
    assert client.put("/api/notr/notes/99/tasks", json={"index": 0, "checked": True}).status_code == 404


# -- pictures -------------------------------------------------------------------------------


def test_a_picture_is_stored_and_served_with_its_type(client):
    stored = upload(client, image_bytes()).json()

    assert stored["url"] == f"/api/notr/images/{stored['id']}"
    assert stored["content_type"] == "image/png"
    served = client.get(stored["url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert "immutable" in served.headers["cache-control"]
    assert served.headers["x-content-type-options"] == "nosniff"
    assert Image.open(io.BytesIO(served.content)).size == (10, 10)


def test_a_big_picture_is_scaled_down_and_a_big_png_photo_becomes_a_jpeg(client):
    noisy = Image.effect_noise((2400, 1800), 80).convert("RGB")
    buf = io.BytesIO()
    noisy.save(buf, format="PNG")

    stored = upload(client, buf.getvalue()).json()

    assert stored["content_type"] == "image/jpeg"
    assert max(Image.open(io.BytesIO(client.get(stored["url"]).content)).size) == 1600
    assert stored["size_bytes"] < len(buf.getvalue())


def test_a_jpeg_stays_a_jpeg_and_a_transparent_png_stays_a_png(client):
    jpeg = upload(client, image_bytes(fmt="JPEG"), "p.jpg").json()
    transparent = upload(client, image_bytes(fmt="PNG", mode="RGBA"), "p.png").json()

    assert jpeg["content_type"] == "image/jpeg"
    assert transparent["content_type"] == "image/png"


@pytest.mark.parametrize(
    "content",
    [b"", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", b"<html></html>", b"%PDF-1.4 hi", b"GIF89a...."],
)
def test_only_png_jpeg_and_webp_pictures_are_accepted(client, content):
    assert upload(client, content).status_code == 400


def test_a_file_that_claims_to_be_a_picture_but_is_not_one_is_refused(client):
    assert upload(client, b"\x89PNG\r\n\x1a\n" + b"not really a png").status_code == 400


def test_an_unknown_picture_is_a_404(client):
    assert client.get("/api/notr/images/99").status_code == 404


def test_saving_a_note_claims_the_pictures_its_body_shows(client, db_session):
    shown, unused = upload(client, image_bytes()).json(), upload(client, image_bytes()).json()

    created = note(client, body=f"Look:\n\n![chart]({shown['url']})")

    assert db_session.get(NotrNoteImage, shown["id"]).note_id == created["id"]
    assert db_session.get(NotrNoteImage, unused["id"]).note_id is None


def test_removing_a_picture_from_the_body_deletes_it(client, db_session):
    pic = upload(client, image_bytes()).json()
    created = note(client, body=f"![a]({pic['url']})")

    client.put(f"/api/notr/notes/{created['id']}", json={"body": "gone"})

    assert db_session.get(NotrNoteImage, pic["id"]) is None
    assert client.get(pic["url"]).status_code == 404


def test_editing_something_other_than_the_body_keeps_the_pictures(client, db_session):
    pic = upload(client, image_bytes()).json()
    created = note(client, body=f"![a]({pic['url']})")

    client.put(f"/api/notr/notes/{created['id']}", json={"pinned": True})

    assert db_session.get(NotrNoteImage, pic["id"]) is not None


def test_deleting_a_note_deletes_its_pictures(client, db_session):
    pic = upload(client, image_bytes()).json()
    created = note(client, body=f"![a]({pic['url']})")

    client.delete(f"/api/notr/notes/{created['id']}")

    assert db_session.get(NotrNoteImage, pic["id"]) is None


def test_a_picture_belonging_to_another_note_is_not_taken_over(client, db_session):
    pic = upload(client, image_bytes()).json()
    first = note(client, body=f"![a]({pic['url']})")

    note(client, body=f"copied ![a]({pic['url']})")

    assert db_session.get(NotrNoteImage, pic["id"]).note_id == first["id"]


def test_a_picture_uploaded_for_a_note_never_saved_is_cleaned_up_a_day_later(client, db_session, monkeypatch):
    monkeypatch.setattr(notr_note_service, "_utcnow", lambda: NOW)
    stale, fresh = upload(client, image_bytes()).json(), upload(client, image_bytes()).json()
    db_session.get(NotrNoteImage, stale["id"]).created_at = NOW - timedelta(days=2)
    db_session.get(NotrNoteImage, fresh["id"]).created_at = NOW - timedelta(hours=2)
    db_session.commit()

    upload(client, image_bytes())

    assert db_session.get(NotrNoteImage, stale["id"]) is None
    assert db_session.get(NotrNoteImage, fresh["id"]) is not None


def test_a_saved_notes_picture_is_never_cleaned_up(client, db_session, monkeypatch):
    monkeypatch.setattr(notr_note_service, "_utcnow", lambda: NOW)
    pic = upload(client, image_bytes()).json()
    note(client, body=f"![a]({pic['url']})")
    db_session.get(NotrNoteImage, pic["id"]).created_at = NOW - timedelta(days=30)
    db_session.commit()

    upload(client, image_bytes())

    assert db_session.get(NotrNoteImage, pic["id"]) is not None


def test_listing_notes_never_reads_picture_bytes(client, db_session):
    pic = upload(client, image_bytes()).json()
    note(client, body=f"![a]({pic['url']})")
    db_session.expire_all()

    client.get("/api/notr/notes")

    assert "content" not in db_session.get(NotrNoteImage, pic["id"]).__dict__


def test_referenced_image_ids_are_found_in_order_without_duplicates():
    body = "![a](/api/notr/images/7) text ![b](/api/notr/images/3) ![c](/api/notr/images/7) [x](/api/notr/images/x)"

    assert notr_note_service.referenced_image_ids(body) == [7, 3]
    assert notr_note_service.referenced_image_ids("") == []


# -- Vandaag --------------------------------------------------------------------------------


def test_pinned_notes_for_vandaag_use_the_title_or_the_start_of_the_body(db_session):
    from app.repositories import notr_note_repo

    notr_note_repo.create_note(db_session, title="Titled", body="x", pinned=True)
    notr_note_repo.create_note(db_session, title="", body="\n## Start here ![i](/api/notr/images/1)\nmore", pinned=True)
    notr_note_repo.create_note(db_session, title="Not pinned", body="x")
    notr_note_repo.create_note(db_session, title="Archived", body="x", pinned=True, is_archived=True)

    pinned = notr_note_service.pinned_for_today(db_session)

    assert sorted((p["title"], p["preview"]) for p in pinned) == [("", "Start here"), ("Titled", "x")]
