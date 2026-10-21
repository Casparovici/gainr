"""gripr endpoints whose rules used to live in the router: account and category updates, the
transaction list's category roll-up, and deleting a recurring rule."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models import GriprDepreciation
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_recurring import GriprRecurrenceFrequency, GriprRecurringTransaction
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType

T = GriprTransactionType
DAY = date(2026, 10, 1)


@pytest.fixture()
def client(db_session):
    from app.routers import gripr as gripr_router

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def account(db, name, type_=GriprAccountType.CHECKING, **kw) -> GriprAccount:
    a = GriprAccount(name=name, type=type_, balance_mode=GriprBalanceMode.TRANSACTIONAL, **kw)
    db.add(a)
    db.flush()
    return a


def category(db, name, kind=GriprCategoryKind.EXPENSE, parent=None) -> GriprCategory:
    c = GriprCategory(name=name, kind=kind, parent_id=parent.id if parent else None)
    db.add(c)
    db.flush()
    return c


def txn(db, acc, amount, cat=None, type_=T.EXPENSE) -> GriprTransaction:
    t = GriprTransaction(date=DAY, type=type_, amount=Decimal(amount), account_id=acc.id, category_id=cat.id if cat else None)
    db.add(t)
    db.flush()
    return t


# -- accounts ---------------------------------------------------------------------------------


def test_an_account_becomes_a_pot_inside_a_real_account(client, db_session):
    tr, pot = account(db_session, "Trade Republic"), account(db_session, "Onderhoud auto")
    updated = client.put(f"/api/gripr/accounts/{pot.id}", json={"held_in_account_id": tr.id})
    assert updated.status_code == 200
    assert updated.json()["held_in_account_id"] == tr.id


def test_pots_are_one_level_deep(client, db_session):
    tr, pot, other = account(db_session, "TR"), account(db_session, "Pot"), account(db_session, "Ander")
    client.put(f"/api/gripr/accounts/{pot.id}", json={"held_in_account_id": tr.id})

    assert client.put(f"/api/gripr/accounts/{other.id}", json={"held_in_account_id": pot.id}).status_code == 400  # into a pot
    assert client.put(f"/api/gripr/accounts/{tr.id}", json={"held_in_account_id": other.id}).status_code == 400  # holds pots
    assert client.put(f"/api/gripr/accounts/{tr.id}", json={"held_in_account_id": tr.id}).status_code == 400  # itself


def test_an_account_update_refuses_unknown_references(client, db_session):
    ing = account(db_session, "ING")
    assert client.put("/api/gripr/accounts/999", json={"name": "x"}).status_code == 404
    assert client.put(f"/api/gripr/accounts/{ing.id}", json={"held_in_account_id": 999}).status_code == 404
    assert client.put(f"/api/gripr/accounts/{ing.id}", json={"bank_logo_key": "no-such-bank"}).status_code == 400


def test_renaming_an_account(client, db_session):
    ing = account(db_session, "ING")
    assert client.put(f"/api/gripr/accounts/{ing.id}", json={"name": "ING Betalen"}).json()["name"] == "ING Betalen"


# -- categories -------------------------------------------------------------------------------


def test_an_expense_category_links_to_a_loan_account(client, db_session):
    loan = account(db_session, "Hypotheek", GriprAccountType.LOAN)
    rent = category(db_session, "Wonen")
    updated = client.put(f"/api/gripr/categories/{rent.id}", json={"linked_loan_account_id": loan.id})
    assert updated.status_code == 200
    assert updated.json()["linked_loan_account_id"] == loan.id


def test_only_expense_categories_link_and_only_to_loans(client, db_session):
    loan, checking = account(db_session, "Hypotheek", GriprAccountType.LOAN), account(db_session, "ING")
    salary = category(db_session, "Salaris", GriprCategoryKind.INCOME)
    rent = category(db_session, "Wonen")
    assert client.put(f"/api/gripr/categories/{salary.id}", json={"linked_loan_account_id": loan.id}).status_code == 400
    assert client.put(f"/api/gripr/categories/{rent.id}", json={"linked_loan_account_id": checking.id}).status_code == 400
    assert client.put(f"/api/gripr/categories/{rent.id}", json={"linked_loan_account_id": 999}).status_code == 400
    assert client.put("/api/gripr/categories/999", json={"name": "x"}).status_code == 404


def test_archiving_a_category_takes_its_subcategories_along(client, db_session):
    food = category(db_session, "Eten")
    groceries = category(db_session, "Boodschappen", parent=food)
    updated = client.put(f"/api/gripr/categories/{food.id}", json={"is_archived": True, "color": "#123456"}).json()
    assert updated["is_archived"] is True
    assert updated["color"] == "#123456"
    db_session.refresh(groceries)
    assert groceries.is_archived is True


# -- transactions -----------------------------------------------------------------------------


def test_filtering_on_a_category_includes_its_subcategories(client, db_session):
    ing = account(db_session, "ING")
    food = category(db_session, "Eten")
    groceries = category(db_session, "Boodschappen", parent=food)
    other = category(db_session, "Vervoer")
    top, sub = txn(db_session, ing, "10", food), txn(db_session, ing, "20", groceries)
    txn(db_session, ing, "30", other)

    page = client.get("/api/gripr/transactions", params={"category_id": food.id}).json()

    assert page["total"] == 2
    assert {t["id"] for t in page["items"]} == {top.id, sub.id}


def test_the_list_shows_what_was_refunded_and_how_many_files_are_attached(client, db_session):
    ing = account(db_session, "ING")
    expense = txn(db_session, ing, "50")
    refund = GriprTransaction(date=DAY, type=T.REFUND, amount=Decimal("20"), account_id=ing.id, refund_of_id=expense.id)
    db_session.add(refund)
    db_session.flush()

    item = next(t for t in client.get("/api/gripr/transactions").json()["items"] if t["id"] == expense.id)

    assert Decimal(item["refunded_amount"]) == Decimal("20")
    assert item["attachment_count"] == 0


# -- recurring --------------------------------------------------------------------------------


def test_deleting_a_recurring_rule_takes_its_depreciation_plan_along(client, db_session):
    ing, car = account(db_session, "ING"), account(db_session, "Auto", GriprAccountType.ASSET)
    fund = account(db_session, "Afschrijving", GriprAccountType.SAVINGS)
    rule = GriprRecurringTransaction(
        name="Afschrijving auto", type=T.TRANSFER, amount=Decimal("100"), account_id=ing.id,
        counter_account_id=fund.id, frequency=GriprRecurrenceFrequency.MONTHLY, start_date=DAY, next_due_date=DAY,
    )
    db_session.add(rule)
    db_session.flush()
    db_session.add(GriprDepreciation(account_id=car.id, amount=Decimal("100"), recurring_id=rule.id))
    db_session.flush()

    assert client.delete(f"/api/gripr/recurring/{rule.id}").status_code == 204

    assert db_session.get(GriprRecurringTransaction, rule.id) is None
    assert db_session.query(GriprDepreciation).count() == 0
    assert client.delete(f"/api/gripr/recurring/{rule.id}").status_code == 404


def test_savings_room_endpoint_reports_the_budget_left_for_saving(client, db_session):
    from app.services import gripr_budget_service

    salary = category(db_session, "Salaris", GriprCategoryKind.INCOME)
    rent = category(db_session, "Huur")
    spaar = account(db_session, "Spaar", GriprAccountType.SAVINGS)
    gripr_budget_service.set_budget(db_session, salary.id, DAY, Decimal("3000"))
    gripr_budget_service.set_budget(db_session, rent.id, DAY, Decimal("1200.50"))
    gripr_budget_service.set_savings_goal(db_session, spaar.id, DAY, Decimal("500"))

    response = client.get("/api/gripr/savings-goals/room", params={"month": DAY.isoformat()})

    assert response.status_code == 200
    body = {k: Decimal(v) for k, v in response.json().items()}
    assert body == {
        "income_budgeted": Decimal("3000"),
        "expense_budgeted": Decimal("1200.50"),
        "room": Decimal("1799.50"),
        "goals_budgeted": Decimal("500"),
        "unallocated": Decimal("1299.50"),
    }
