from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.asset import Asset
from app.models.broker_sync import BrokerConnection
from app.routers import assets as assets_router
from app.routers import brokers as brokers_router
from app.services import broker_sync_service


@pytest.fixture()
def client(db_session):
    # Only the routers under test -- importing app.main would run create_all on the real database.
    app = FastAPI()
    app.include_router(brokers_router.router)
    app.include_router(assets_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def connection(db_session) -> BrokerConnection:
    """The row the migration seeds: off, no portfolio."""
    row = BrokerConnection(broker="Trading212")
    db_session.add(row)
    db_session.flush()
    return row


def test_status_starts_off_and_unconfigured(client, connection):
    body = client.get("/api/brokers/trading212").json()

    assert body == {
        "configured": False, "enabled": False, "since": None, "portfolio_id": None,
        "last_synced_at": None, "last_error": None, "unmapped": [],
    }


def test_switching_on_needs_a_portfolio_and_starts_today(client, connection, portfolio_id):
    assert client.put("/api/brokers/trading212", json={"enabled": True}).status_code == 422
    assert client.put("/api/brokers/trading212", json={"enabled": True, "portfolio_id": 999}).status_code == 404

    body = client.put("/api/brokers/trading212", json={"enabled": True, "portfolio_id": portfolio_id}).json()

    assert (body["enabled"], body["portfolio_id"], body["since"]) == (True, portfolio_id, date.today().isoformat())


def test_held_back_instruments_are_listed(client, connection):
    connection.unmapped = (
        '[{"isin": "IE000J80JTL1", "ticker": "GRIDd_EQ", "name": "Smart Grid", "currency": "EUR",'
        ' "records": 2, "first_date": "2026-10-02"}, {"broken": true}]'
    )

    body = client.get("/api/brokers/trading212").json()

    assert [(u["isin"], u["records"]) for u in body["unmapped"]] == [("IE000J80JTL1", 2)]


def test_sync_now_reports_what_happened(client, connection, monkeypatch):
    monkeypatch.setattr(
        broker_sync_service, "sync",
        lambda db: broker_sync_service.BrokerSyncResult(booked=2, matched=1, deposits=1, problems=["x"]),
    )

    body = client.post("/api/brokers/trading212/sync").json()

    assert body == {"booked": 2, "matched": 1, "deposits": 1, "unmapped": [], "problems": ["x"]}


def test_an_asset_takes_an_isin_and_rejects_one_that_isnt(client, db_session):
    asset = Asset(ticker="GRIDINAV", name="Smart Grid")
    db_session.add(asset)
    db_session.flush()

    assert client.put(f"/api/assets/{asset.id}", json={"isin": "not-an-isin"}).status_code == 422
    body = client.put(f"/api/assets/{asset.id}", json={"isin": " ie000j80jtl1 "}).json()
    assert body["isin"] == "IE000J80JTL1"
    assert client.put(f"/api/assets/{asset.id}", json={"isin": ""}).json()["isin"] is None
