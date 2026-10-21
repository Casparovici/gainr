"""Depreciation (docs/adr/0034): the monthly transfer into the depreciation fund is what the car
loses, so when it books, the car's manually set value drops by that amount."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_transaction import GriprTransactionType
from app.repositories import gripr_transaction_repo
from app.routers import gripr as gripr_router
from app.services import gripr_depreciation_service, gripr_recurring_service, gripr_transaction_service

T = GriprTransactionType
DUE = date(2026, 11, 2)


@pytest.fixture()
def accounts(db_session):
    def make(name, type_, mode=GriprBalanceMode.TRANSACTIONAL, manual="0"):
        a = GriprAccount(name=name, type=type_, balance_mode=mode, manual_balance=Decimal(manual))
        db_session.add(a)
        db_session.flush()
        return a

    return {
        "tr": make("Trade Republic", GriprAccountType.SAVINGS),
        "fund": make("Afschrijving Auto", GriprAccountType.INVESTMENT, GriprBalanceMode.MANUAL, "1800"),
        "focus": make("Ford Focus", GriprAccountType.ASSET, GriprBalanceMode.MANUAL, "6800"),
        "peugeot": make("Peugeot 107", GriprAccountType.ASSET, GriprBalanceMode.MANUAL, "500"),
        "savings": make("Spaar", GriprAccountType.SAVINGS),
    }


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def plan(client, a, **extra):
    body = {
        "name": "TDIV plan", "type": "transfer", "amount": "121.00", "account_id": a["tr"].id, "counter_account_id": a["fund"].id,
        "frequency": "monthly", "interval": 1, "start_date": DUE.isoformat(),
        "depreciations": [{"account_id": a["focus"].id, "amount": "96.00"}, {"account_id": a["peugeot"].id, "amount": "25.00"}],
        **extra,
    }
    response = client.post("/api/gripr/recurring", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_transfer_booking_lowers_the_cars_by_their_share(client, db_session, accounts):
    rule = plan(client, accounts)

    assert [(d["account_name"], d["amount"]) for d in rule["depreciations"]] == [("Ford Focus", "96.00"), ("Peugeot 107", "25.00")]
    gripr_recurring_service.generate_due(db_session, as_of=DUE)

    assert accounts["focus"].manual_balance == Decimal("6704.00")
    assert accounts["peugeot"].manual_balance == Decimal("475.00")


def test_a_prebooked_occurrence_waits_for_its_date(client, db_session, accounts):
    plan(client, accounts)

    gripr_recurring_service.generate_due(db_session, as_of=DUE - timedelta(days=1))  # pre-booked, not due
    assert accounts["focus"].manual_balance == Decimal("6800")

    gripr_recurring_service.generate_due(db_session, as_of=DUE)
    assert accounts["focus"].manual_balance == Decimal("6704.00")
    gripr_recurring_service.generate_due(db_session, as_of=DUE)  # again: exactly once
    assert accounts["focus"].manual_balance == Decimal("6704.00")


def test_deleting_the_booked_transfer_gives_the_value_back(client, db_session, accounts):
    plan(client, accounts)
    (txn,) = gripr_recurring_service.generate_due(db_session, as_of=DUE)

    gripr_transaction_service.delete_transaction(db_session, txn)

    assert (accounts["focus"].manual_balance, accounts["peugeot"].manual_balance) == (Decimal("6800.00"), Decimal("500.00"))
    assert gripr_transaction_repo.get_transaction(db_session, txn.id) is None


def test_changing_the_rule_later_doesnt_change_what_was_applied(client, db_session, accounts):
    rule = plan(client, accounts)
    (txn,) = gripr_recurring_service.generate_due(db_session, as_of=DUE)

    client.put(f"/api/gripr/recurring/{rule['id']}", json={"depreciations": [{"account_id": accounts["focus"].id, "amount": "50.00"}]})
    gripr_transaction_service.delete_transaction(db_session, txn)

    assert accounts["focus"].manual_balance == Decimal("6800.00")  # the 96 that was taken comes back, not 50


def test_an_amount_over_the_transfer_a_non_asset_or_a_non_transfer_is_refused(client, db_session, accounts):
    a = accounts
    over = {"depreciations": [{"account_id": a["focus"].id, "amount": "100.00"}, {"account_id": a["peugeot"].id, "amount": "25.00"}]}
    wrong_account = {"depreciations": [{"account_id": a["savings"].id, "amount": "10.00"}]}
    base = {"name": "x", "type": "transfer", "amount": "121.00", "account_id": a["tr"].id, "counter_account_id": a["fund"].id,
            "frequency": "monthly", "start_date": DUE.isoformat()}

    assert client.post("/api/gripr/recurring", json={**base, **over}).status_code == 400
    assert client.post("/api/gripr/recurring", json={**base, **wrong_account}).status_code == 400
    expense = {**base, "type": "expense", "counter_account_id": None, "depreciations": [{"account_id": a["focus"].id, "amount": "10.00"}]}
    assert client.post("/api/gripr/recurring", json=expense).status_code == 400


def test_the_overview_compares_each_car_and_the_fund(client, db_session, accounts):
    plan(client, accounts)

    body = client.get("/api/gripr/depreciation").json()

    focus, peugeot = body["assets"]
    assert (focus["name"], focus["value"], focus["monthly"], focus["months_left"]) == ("Ford Focus", "6800.00", "96.00", 70)
    assert (peugeot["months_left"], peugeot["monthly"]) == (20, "25.00")
    (fund,) = body["funds"]
    assert (fund["name"], fund["balance"], fund["assets_value"], fund["monthly"]) == ("Afschrijving Auto", "1800.00", "7300.00", "121.00")
    assert fund["covers_pct"] == "24.7"


def test_clearing_the_depreciations_stops_it(client, db_session, accounts):
    rule = plan(client, accounts)

    cleared = client.put(f"/api/gripr/recurring/{rule['id']}", json={"depreciations": []}).json()
    gripr_recurring_service.generate_due(db_session, as_of=DUE)

    assert cleared["depreciations"] == []
    assert accounts["focus"].manual_balance == Decimal("6800")
    assert gripr_depreciation_service.for_rule(db_session, rule["id"]) == []
