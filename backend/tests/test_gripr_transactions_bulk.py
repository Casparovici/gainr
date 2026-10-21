"""Transactions: free-text search, and one action on several selected rows."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.routers import gripr as gripr_router

T = GriprTransactionType
DAY = date(2026, 10, 1)


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def setup(db_session):
    def account(name):
        a = GriprAccount(name=name, type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
        db_session.add(a)
        return a

    def category(name, kind=GriprCategoryKind.EXPENSE, parent=None):
        c = GriprCategory(name=name, kind=kind, parent_id=parent.id if parent else None)
        db_session.add(c)
        db_session.flush()
        return c

    ing, joint = account("ING"), account("Gezamenlijk")
    db_session.flush()
    food = category("Boodschappen")
    market = category("Markt", parent=food)
    salary = category("Salaris", GriprCategoryKind.INCOME)

    def txn(type_, amount, notes=None, acc=ing, counter=None, cat=None):
        t = GriprTransaction(
            date=DAY, type=type_, amount=Decimal(amount), account_id=acc.id, notes=notes,
            counter_account_id=counter.id if counter else None, category_id=cat.id if cat else None,
        )
        db_session.add(t)
        db_session.flush()
        return t

    return {"ing": ing, "joint": joint, "food": food, "market": market, "salary": salary, "txn": txn}


def ids(response) -> set[int]:
    return {t["id"] for t in response.json()["items"]}


def test_search_finds_notes_category_account_and_amount(client, setup):
    s = setup
    ah = s["txn"](T.EXPENSE, "31.20", "Albert Heijn 1234 Amsterdam — Betaalpas")
    filed = s["txn"](T.EXPENSE, "9.99", "card", cat=s["food"])
    on_joint = s["txn"](T.EXPENSE, "4.00", "coffee", acc=s["joint"])

    assert ids(client.get("/api/gripr/transactions", params={"q": "albert heijn"})) == {ah.id}
    assert ids(client.get("/api/gripr/transactions", params={"q": "boodschap"})) == {filed.id}
    assert ids(client.get("/api/gripr/transactions", params={"q": "gezamenlijk"})) == {on_joint.id}
    assert ids(client.get("/api/gripr/transactions", params={"q": "31,20"})) == {ah.id}


def test_bulk_files_under_a_subcategory_and_skips_what_it_cannot_apply_to(client, setup):
    s = setup
    a, b = s["txn"](T.EXPENSE, "10"), s["txn"](T.EXPENSE, "20")
    pay = s["txn"](T.INCOME, "3000")
    move = s["txn"](T.TRANSFER, "50", counter=s["joint"])

    r = client.post("/api/gripr/transactions/bulk", json={
        "transaction_ids": [a.id, b.id, pay.id, move.id], "action": "set_category", "category_id": s["market"].id,
    })

    assert r.json() == {"updated": 2, "skipped": 2}  # income doesn't take an expense category; a transfer none
    assert (a.category_id, b.category_id, pay.category_id, move.category_id) == (s["market"].id, s["market"].id, None, None)


def test_bulk_moves_to_another_account_but_never_a_transfer_onto_its_own_other_side(client, setup):
    s = setup
    a = s["txn"](T.EXPENSE, "10")
    move = s["txn"](T.TRANSFER, "50", counter=s["joint"])

    r = client.post("/api/gripr/transactions/bulk", json={
        "transaction_ids": [a.id, move.id], "action": "set_account", "account_id": s["joint"].id,
    })

    assert r.json() == {"updated": 1, "skipped": 1}
    assert (a.account_id, move.account_id) == (s["joint"].id, s["ing"].id)


def test_bulk_delete(client, setup, db_session):
    s = setup
    a, b, keep = s["txn"](T.EXPENSE, "10"), s["txn"](T.EXPENSE, "20"), s["txn"](T.EXPENSE, "30")

    r = client.post("/api/gripr/transactions/bulk", json={"transaction_ids": [a.id, b.id], "action": "delete"})

    assert r.json() == {"updated": 2, "skipped": 0}
    assert [t.id for t in db_session.query(GriprTransaction)] == [keep.id]


def test_bulk_refuses_unknown_ids_and_missing_targets_without_changing_anything(client, setup):
    s = setup
    a = s["txn"](T.EXPENSE, "10")

    unknown = client.post("/api/gripr/transactions/bulk", json={"transaction_ids": [a.id, 9999], "action": "delete"})
    no_category = client.post("/api/gripr/transactions/bulk", json={"transaction_ids": [a.id], "action": "set_category"})

    assert unknown.status_code == 400 and no_category.status_code == 400
    assert a.category_id is None
