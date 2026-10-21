"""A recipe's photo: upload (re-encoded), replace, remove, serve -- and the Mealie import of one."""

import io

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.db import get_db
from app.models.listr_category import ListrCategory
from app.models.listr_item import ListrItem
from app.repositories import listr_recipe_repo
from app.routers import listr as listr_router
from app.services.listr_mealie_service import ListrMealieService
from app.services.mealie_provider import MealieProvider
from tests.test_listr_mealie import FakeMealie, frikandelbroodjes
from tests.test_listr_router import make_recipe


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(listr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def catalog(db_session):
    """Just the products frikandelbroodjes() needs a mapping for."""
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


def image_bytes(size=(10, 10), fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=(0, 128, 0)).save(buf, format=fmt)
    return buf.getvalue()


def test_a_recipe_has_no_photo_until_one_is_attached(client):
    recipe = make_recipe(client)
    assert recipe["has_photo"] is False
    assert client.get(f"/api/listr/recipes/{recipe['id']}/photo").status_code == 404


def test_attaching_replacing_and_removing_a_photo(client):
    recipe = make_recipe(client)
    url = f"/api/listr/recipes/{recipe['id']}/photo"

    put = client.put(url, files={"photo": ("a.png", image_bytes(), "image/png")})
    assert put.status_code == 200 and put.json()["has_photo"] is True
    assert client.get(f"/api/listr/recipes/{recipe['id']}").json()["has_photo"] is True
    assert client.get("/api/listr/recipes").json()[0]["has_photo"] is True

    served = client.get(url)
    assert served.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(served.content)).format == "JPEG"

    client.put(url, files={"photo": ("b.png", image_bytes((20, 20)), "image/png")})
    assert Image.open(io.BytesIO(client.get(url).content)).size == (20, 20)

    deleted = client.delete(url)
    assert deleted.json()["has_photo"] is False
    assert client.get(url).status_code == 404


def test_a_big_photo_is_shrunk_to_the_size_cap(client):
    recipe = make_recipe(client)
    url = f"/api/listr/recipes/{recipe['id']}/photo"
    client.put(url, files={"photo": ("big.png", image_bytes((3200, 1600)), "image/png")})
    assert Image.open(io.BytesIO(client.get(url).content)).size == (1600, 800)


def test_a_file_that_is_not_an_image_is_refused(client):
    recipe = make_recipe(client)
    response = client.put(f"/api/listr/recipes/{recipe['id']}/photo", files={"photo": ("x.txt", b"nope", "text/plain")})
    assert response.status_code == 400
    assert client.get(f"/api/listr/recipes/{recipe['id']}").json()["has_photo"] is False


def test_photo_endpoints_404_for_an_unknown_recipe(client):
    assert client.put("/api/listr/recipes/999/photo", files={"photo": ("a.png", image_bytes(), "image/png")}).status_code == 404
    assert client.delete("/api/listr/recipes/999/photo").status_code == 404
    assert client.get("/api/listr/recipes/999/photo").status_code == 404


# -- Mealie ----------------------------------------------------------------------------------


class FakeMealieWithImages(FakeMealie):
    def __init__(self, recipes, images):
        super().__init__(recipes)
        self.images = images

    def get_image(self, recipe_id):
        return self.images.get(recipe_id)


def with_image(recipe):
    recipe.has_image = True
    return recipe


def test_import_brings_mealies_picture_along(db_session, catalog):
    fake = FakeMealieWithImages([with_image(frikandelbroodjes())], {"m-1": image_bytes()})
    ListrMealieService(lambda: fake).import_recipes(db_session, {"f-ei": catalog["Eieren"].id})

    recipe = listr_recipe_repo.get_by_mealie_id(db_session, "m-1")
    assert recipe.has_photo and Image.open(io.BytesIO(recipe.photo)).format == "JPEG"


def test_a_recipe_without_a_mealie_picture_keeps_its_photo(db_session, catalog):
    ListrMealieService(lambda: FakeMealieWithImages([with_image(frikandelbroodjes())], {"m-1": image_bytes()})).import_recipes(
        db_session, {"f-ei": catalog["Eieren"].id}
    )
    edited = frikandelbroodjes(updated_at="2026-10-01T09:00:00")  # no image any more
    ListrMealieService(lambda: FakeMealie([edited])).import_recipes(db_session, {})

    assert listr_recipe_repo.get_by_mealie_id(db_session, "m-1").has_photo


def test_an_unusable_mealie_picture_does_not_fail_the_import(db_session, catalog):
    fake = FakeMealieWithImages([with_image(frikandelbroodjes())], {"m-1": b"not an image"})
    result = ListrMealieService(lambda: fake).import_recipes(db_session, {"f-ei": catalog["Eieren"].id})

    assert result.created == 1
    assert not listr_recipe_repo.get_by_mealie_id(db_session, "m-1").has_photo


def test_provider_fetches_the_image_and_treats_404_as_none():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.raw_path)
        return httpx.Response(200, content=b"img") if b"m-1" in request.url.raw_path else httpx.Response(404)

    provider = MealieProvider("http://m", "k", transport=httpx.MockTransport(handler))
    assert provider.get_image("m-1") == b"img"
    assert provider.get_image("m-2") is None
    assert seen[0] == b"/api/media/recipes/m-1/images/original.webp"


def test_provider_reads_whether_a_recipe_has_an_image():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "m-1", "slug": "s", "name": "S", "image": "abcd"})

    provider = MealieProvider("http://m", "k", transport=httpx.MockTransport(handler))
    assert provider.get_recipe("s").has_image is True
