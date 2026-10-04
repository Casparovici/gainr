import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.routers import gardnr as gardnr_router


@pytest.fixture()
def client(db_session):
    # Only the router under test, rather than app.main -- importing that would run create_all
    # against the real portfolio.db.
    app = FastAPI()
    app.include_router(gardnr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def make_area(client, name="Back yard") -> int:
    return client.post("/api/gardnr/areas", json={"name": name}).json()["id"]


def make_plant(client, area_id, name="Japanese Maple", type_="tree") -> int:
    return client.post("/api/gardnr/plants", json={"area_id": area_id, "name": name, "type": type_}).json()["id"]


def test_create_and_list_areas(client):
    make_area(client, "Front yard")
    make_area(client, "Back yard")

    areas = client.get("/api/gardnr/areas").json()

    assert [a["name"] for a in areas] == ["Front yard", "Back yard"]
    assert all(a["plant_count"] == 0 for a in areas)


def test_area_reorder(client):
    first = make_area(client, "Front yard")
    second = make_area(client, "Back yard")

    client.put("/api/gardnr/areas/reorder", json={"area_ids": [second, first]})

    areas = client.get("/api/gardnr/areas").json()
    assert [a["name"] for a in areas] == ["Back yard", "Front yard"]


def test_creating_a_zone_under_a_nonexistent_area_404s(client):
    resp = client.post(
        "/api/gardnr/areas/999/zones",
        json={"name": "Lawn", "shape": "rect", "x": 0, "y": 0, "width": 50, "height": 50, "color": "#4caf50"},
    )
    assert resp.status_code == 404


def test_area_detail_bundles_zones_and_plant_markers(client):
    area_id = make_area(client)
    client.post(
        f"/api/gardnr/areas/{area_id}/zones",
        json={"name": "Vegetable bed", "shape": "rect", "x": 10, "y": 10, "width": 30, "height": 20, "color": "#8b5e34"},
    )
    client.post("/api/gardnr/plants", json={"area_id": area_id, "name": "Tomato", "type": "plant", "x": 15, "y": 15})

    detail = client.get(f"/api/gardnr/areas/{area_id}").json()

    assert detail["area"]["plant_count"] == 1
    assert len(detail["zones"]) == 1
    assert detail["zones"][0]["name"] == "Vegetable bed"
    assert detail["plants"][0]["name"] == "Tomato"
    assert detail["plants"][0]["last_action"] is None
    assert detail["plants"][0]["next_action"] is None


def test_care_log_and_schedule_round_trip(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)

    schedule = client.post(
        f"/api/gardnr/plants/{plant_id}/schedules",
        json={"action_type": "water", "interval_value": 3, "frequency": "daily"},
    ).json()
    assert schedule["is_overdue"] is False

    client.post(f"/api/gardnr/plants/{plant_id}/logs", json={"action_type": "water", "performed_on": "2020-01-01"})

    detail = client.get(f"/api/gardnr/plants/{plant_id}").json()
    assert len(detail["care_logs"]) == 1
    assert detail["care_schedules"][0]["is_overdue"] is True  # 2020-01-01 + 3 days is long past


def test_a_schedule_can_start_on_a_chosen_date_and_have_it_moved_or_cleared(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)

    schedule = client.post(
        f"/api/gardnr/plants/{plant_id}/schedules",
        json={"action_type": "fertilize", "interval_value": 2, "frequency": "weekly", "start_date": "2099-03-01"},
    ).json()
    assert schedule["start_date"] == "2099-03-01"
    assert schedule["next_due"] == "2099-03-01"  # the first occurrence, not two weeks after it

    moved = client.put(f"/api/gardnr/schedules/{schedule['id']}", json={"start_date": "2099-04-01"}).json()
    assert moved["next_due"] == "2099-04-01"

    cleared = client.put(f"/api/gardnr/schedules/{schedule['id']}", json={"start_date": None}).json()
    assert cleared["start_date"] is None
    assert cleared["next_due"] < "2099-01-01"  # back to creation date plus the interval


def test_pausing_a_schedule_removes_it_from_next_action(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    schedule_id = client.post(
        f"/api/gardnr/plants/{plant_id}/schedules", json={"action_type": "water", "interval_value": 1, "frequency": "daily"}
    ).json()["id"]

    client.put(f"/api/gardnr/schedules/{schedule_id}", json={"is_active": False})

    rows = client.get("/api/gardnr/plants").json()
    assert rows[0]["next_action"] is None
    assert rows[0]["is_overdue"] is False


def test_plants_list_sorts_most_overdue_first(client):
    area_id = make_area(client)
    soon = make_plant(client, area_id, name="Soon")
    later = make_plant(client, area_id, name="Later")
    unscheduled = make_plant(client, area_id, name="Unscheduled")

    client.post(f"/api/gardnr/plants/{later}/schedules", json={"action_type": "prune", "interval_value": 1, "frequency": "yearly"})
    client.post(f"/api/gardnr/plants/{soon}/schedules", json={"action_type": "water", "interval_value": 1, "frequency": "daily"})

    rows = client.get("/api/gardnr/plants").json()

    assert [r["name"] for r in rows] == ["Soon", "Later", "Unscheduled"]


def test_plants_list_carries_every_scheduled_action_not_just_the_soonest(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    client.post(f"/api/gardnr/plants/{plant_id}/schedules", json={"action_type": "prune", "interval_value": 1, "frequency": "yearly"})
    water_id = client.post(
        f"/api/gardnr/plants/{plant_id}/schedules", json={"action_type": "water", "interval_value": 1, "frequency": "daily"}
    ).json()["id"]
    paused_id = client.post(
        f"/api/gardnr/plants/{plant_id}/schedules", json={"action_type": "fertilize", "interval_value": 1, "frequency": "weekly"}
    ).json()["id"]
    client.put(f"/api/gardnr/schedules/{paused_id}", json={"is_active": False})

    row = client.get("/api/gardnr/plants").json()[0]

    assert [a["action_type"] for a in row["scheduled_actions"]] == ["water", "prune"]
    assert row["scheduled_actions"][0]["schedule_id"] == water_id
    assert row["next_action"] == row["scheduled_actions"][0]


def test_deleting_a_plant_removes_its_logs_and_schedules(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    client.post(f"/api/gardnr/plants/{plant_id}/logs", json={"action_type": "water", "performed_on": "2026-01-01"})
    client.post(f"/api/gardnr/plants/{plant_id}/schedules", json={"action_type": "water", "interval_value": 1, "frequency": "daily"})

    resp = client.delete(f"/api/gardnr/plants/{plant_id}")

    assert resp.status_code == 204
    assert client.get(f"/api/gardnr/plants/{plant_id}").status_code == 404


def test_deleting_an_area_cascades_to_its_plants(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)

    client.delete(f"/api/gardnr/areas/{area_id}")

    assert client.get(f"/api/gardnr/plants/{plant_id}").status_code == 404


def test_renaming_an_area_keeps_its_plants(client):
    area_id = make_area(client, "Voortin")
    plant_id = make_plant(client, area_id)

    client.put(f"/api/gardnr/areas/{area_id}", json={"name": "Voortuin"})

    areas = client.get("/api/gardnr/areas").json()
    assert [a["name"] for a in areas] == ["Voortuin"]
    assert areas[0]["plant_count"] == 1
    assert client.get(f"/api/gardnr/plants/{plant_id}").status_code == 200


def test_areas_carry_their_own_overdue_plant_count(client):
    """The Areas tile grid needs to say which garden to walk into first without opening each
    one — the same overdue definition the plants list and the map markers use."""
    front = make_area(client, "Voortuin")
    back = make_area(client, "Achtertuin")
    overdue_plant = make_plant(client, front, name="Hortensia")
    make_plant(client, back, name="Olijfboom")
    client.post(
        f"/api/gardnr/plants/{overdue_plant}/schedules",
        json={"action_type": "water", "interval_value": 1, "frequency": "daily"},
    )
    client.post(f"/api/gardnr/plants/{overdue_plant}/logs", json={"action_type": "water", "performed_on": "2020-01-01"})

    areas = {a["name"]: a for a in client.get("/api/gardnr/areas").json()}

    assert areas["Voortuin"]["overdue_count"] == 1
    assert areas["Achtertuin"]["overdue_count"] == 0  # has a plant, but nothing scheduled


def test_map_markers_carry_the_backends_own_overdue_verdict(client):
    """The map used to recompute this in the browser from the date string, which disagreed
    with the backend across timezones and around midnight."""
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    client.put(f"/api/gardnr/plants/{plant_id}", json={"x": "10", "y": "10"})
    client.post(
        f"/api/gardnr/plants/{plant_id}/schedules",
        json={"action_type": "water", "interval_value": 1, "frequency": "daily"},
    )
    client.post(f"/api/gardnr/plants/{plant_id}/logs", json={"action_type": "water", "performed_on": "2020-01-01"})

    marker = client.get(f"/api/gardnr/areas/{area_id}").json()["plants"][0]

    assert marker["next_action"]["is_overdue"] is True


def test_clearing_a_plants_optional_fields_actually_clears_them(client):
    """Emptying "Soort" or the notes in the detail panel sends an explicit null -- that has to
    persist, not be read as "field omitted, leave it alone"."""
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    client.put(f"/api/gardnr/plants/{plant_id}", json={"species": "Acer palmatum", "notes": "Shade in summer"})

    resp = client.put(f"/api/gardnr/plants/{plant_id}", json={"species": None, "notes": None})

    assert resp.status_code == 200
    plant = client.get(f"/api/gardnr/plants/{plant_id}").json()["plant"]
    assert plant["species"] is None
    assert plant["notes"] is None


def test_unplacing_a_plant_marker_clears_its_coordinates(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    client.put(f"/api/gardnr/plants/{plant_id}", json={"x": "25.5", "y": "40.0"})

    client.put(f"/api/gardnr/plants/{plant_id}", json={"x": None, "y": None})

    plant = client.get(f"/api/gardnr/plants/{plant_id}").json()["plant"]
    assert plant["x"] is None
    assert plant["y"] is None


# -- plant status (see docs/adr/0012 addendum) -----------------------------------------------


def test_a_new_plant_defaults_to_thriving(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)

    plant = client.get(f"/api/gardnr/plants/{plant_id}").json()["plant"]

    assert plant["status"] == "thriving"


def test_plant_status_shows_on_the_list_and_the_map(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    client.put(f"/api/gardnr/plants/{plant_id}", json={"x": "10", "y": "10", "status": "struggling"})

    rows = client.get("/api/gardnr/plants").json()
    marker = client.get(f"/api/gardnr/areas/{area_id}").json()["plants"][0]

    assert rows[0]["status"] == "struggling"
    assert marker["status"] == "struggling"


# -- care log photos (see docs/adr/0012 addendum) ---------------------------------------------


def _tiny_png_bytes() -> bytes:
    # A minimal valid 1x1 PNG -- enough for Pillow to decode, resize (a no-op at this size) and
    # re-encode without needing a real photo fixture on disk.
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(0, 128, 0)).save(buf, format="PNG")
    return buf.getvalue()


def test_care_log_has_no_photo_until_one_is_attached(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    log_id = client.post(f"/api/gardnr/plants/{plant_id}/logs", json={"action_type": "harvest", "performed_on": "2026-01-01"}).json()["id"]

    detail = client.get(f"/api/gardnr/plants/{plant_id}").json()

    assert detail["care_logs"][0]["has_photo"] is False
    assert client.get(f"/api/gardnr/logs/{log_id}/photo").status_code == 404


def test_attaching_and_fetching_a_care_log_photo(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    log_id = client.post(f"/api/gardnr/plants/{plant_id}/logs", json={"action_type": "harvest", "performed_on": "2026-01-01"}).json()["id"]

    put_resp = client.put(f"/api/gardnr/logs/{log_id}/photo", files={"photo": ("tomato.png", _tiny_png_bytes(), "image/png")})
    assert put_resp.status_code == 200
    assert put_resp.json()["has_photo"] is True

    get_resp = client.get(f"/api/gardnr/logs/{log_id}/photo")
    assert get_resp.status_code == 200
    assert get_resp.headers["content-type"] == "image/jpeg"  # always re-encoded, regardless of upload format
    assert len(get_resp.content) > 0


def test_deleting_a_care_log_photo_clears_it(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    log_id = client.post(f"/api/gardnr/plants/{plant_id}/logs", json={"action_type": "harvest", "performed_on": "2026-01-01"}).json()["id"]
    client.put(f"/api/gardnr/logs/{log_id}/photo", files={"photo": ("tomato.png", _tiny_png_bytes(), "image/png")})

    del_resp = client.delete(f"/api/gardnr/logs/{log_id}/photo")

    assert del_resp.status_code == 200
    assert del_resp.json()["has_photo"] is False
    assert client.get(f"/api/gardnr/logs/{log_id}/photo").status_code == 404


def test_uploading_something_unreadable_as_a_photo_400s(client):
    area_id = make_area(client)
    plant_id = make_plant(client, area_id)
    log_id = client.post(f"/api/gardnr/plants/{plant_id}/logs", json={"action_type": "harvest", "performed_on": "2026-01-01"}).json()["id"]

    resp = client.put(f"/api/gardnr/logs/{log_id}/photo", files={"photo": ("notes.txt", b"not an image", "text/plain")})

    assert resp.status_code == 400

