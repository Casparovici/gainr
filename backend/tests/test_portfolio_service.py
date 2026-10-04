import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.routers import portfolios as portfolios_router
from app.services import portfolio_service
from app.services.portfolio_service import get_main_portfolio


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(portfolios_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_get_main_portfolio_creates_it_on_first_use(db_session):
    portfolio = get_main_portfolio(db_session)

    assert portfolio.name == "Main"
    assert get_main_portfolio(db_session).id == portfolio.id  # get-or-create, not a duplicate


def test_create_portfolio_via_router(client):
    response = client.post("/api/portfolios", json={"name": "Kids"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Kids"
    assert body["is_archived"] is False


def test_create_portfolio_rejects_a_blank_name(client):
    assert client.post("/api/portfolios", json={"name": "   "}).status_code == 422


def test_list_portfolios_excludes_archived_by_default(client, db_session):
    kids = portfolio_service.create_portfolio(db_session, "Kids")
    portfolio_service.update_portfolio(db_session, kids, is_archived=True)
    db_session.commit()

    default_list = client.get("/api/portfolios").json()
    with_archived = client.get("/api/portfolios", params={"include_archived": True}).json()

    assert kids.name not in [p["name"] for p in default_list]
    assert kids.name in [p["name"] for p in with_archived]


def test_rename_and_archive_via_router(client, db_session):
    kids = portfolio_service.create_portfolio(db_session, "Kids")
    db_session.commit()

    response = client.put(f"/api/portfolios/{kids.id}", json={"name": "Kids Investments", "is_archived": True})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Kids Investments"
    assert body["is_archived"] is True


def test_updating_an_unknown_portfolio_is_a_404(client):
    assert client.put("/api/portfolios/9999", json={"name": "Ghost"}).status_code == 404
