"""Refunds (docs/adr/0023): money that comes back for an expense -- a friend's half of a dinner,
a shop refund -- nets against spend instead of counting as income, lands in whichever account
received it, and when linked to its expense counts in that expense's period."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_recurring import GriprRecurrenceFrequency, GriprRecurringTransaction
from app.models.gripr_transaction import GriprTransactionType
from app.repositories import gripr_transaction_repo
from app.routers import gripr as gripr_router
from app.services import (
    gripr_account_service,
    gripr_budget_service,
    gripr_overview_service,
    gripr_transaction_service,
)

EXPENSE = GriprTransactionType.EXPENSE
INCOME = GriprTransactionType.INCOME
REFUND = GriprTransactionType.REFUND


def make_account(db, name) -> GriprAccount:
    account = GriprAccount(name=name, type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db.add(account)
    db.flush()
    return account


def make_category(db, name, kind=GriprCategoryKind.EXPENSE, parent_id=None) -> GriprCategory:
    category = GriprCategory(name=name, kind=kind, parent_id=parent_id)
    db.add(category)
    db.flush()
    return category


def book(db, d, type_, amount, account, category=None, refund_of=None, **kw):
    return gripr_transaction_service.create_transaction(
        db, date=d, type=type_, amount=Decimal(amount), account_id=account.id,
        category_id=category.id if category else None,
        refund_of_id=refund_of.id if refund_of else None, **kw,
    )


@pytest.fixture()
def setup(db_session):
    tr = make_account(db_session, "Trade Republic")
    ing = make_account(db_session, "ING")
    food = make_category(db_session, "Eten & Drinken")
    return db_session, tr, ing, food


# -- balances ------------------------------------------------------------------------------


def test_a_refund_raises_the_balance_of_the_account_that_received_it(setup):
    db, tr, ing, food = setup
    dinner = book(db, date(2026, 9, 28), EXPENSE, "60", tr, food)
    book(db, date(2026, 9, 29), REFUND, "30", ing, refund_of=dinner)

    assert gripr_account_service.compute_balance(db, tr) == Decimal(-60)
    assert gripr_account_service.compute_balance(db, ing) == Decimal(30)


# -- spend attribution ---------------------------------------------------------------------


def test_budget_spent_is_net_of_refunds(setup):
    db, tr, ing, food = setup
    dinner = book(db, date(2026, 5, 10), EXPENSE, "60", tr, food)
    book(db, date(2026, 5, 11), REFUND, "30", ing, refund_of=dinner)

    lines = gripr_budget_service.get_budget_status(db, date(2026, 5, 1))
    assert next(line for line in lines if line.category.id == food.id).spent == Decimal(30)


def test_a_linked_refund_counts_in_its_expenses_period_not_its_own(setup):
    db, tr, ing, food = setup
    dinner = book(db, date(2026, 5, 28), EXPENSE, "60", tr, food)
    book(db, date(2026, 6, 2), REFUND, "30", ing, refund_of=dinner)

    may = gripr_budget_service.get_budget_status(db, date(2026, 5, 1))
    june = gripr_budget_service.get_budget_status(db, date(2026, 6, 1))
    assert next(line for line in may if line.category.id == food.id).spent == Decimal(30)
    assert next(line for line in june if line.category.id == food.id).spent == Decimal(0)


def test_an_unlinked_refund_counts_on_its_own_date(setup):
    db, tr, ing, food = setup
    book(db, date(2026, 5, 28), EXPENSE, "60", tr, food)
    book(db, date(2026, 6, 2), REFUND, "25", ing, food)

    june = gripr_budget_service.get_budget_status(db, date(2026, 6, 1))
    assert next(line for line in june if line.category.id == food.id).spent == Decimal(-25)


def test_a_refund_still_on_its_way_does_not_count_yet(setup):
    db, tr, ing, food = setup
    today = date.today()
    dinner = book(db, today, EXPENSE, "60", tr, food)
    book(db, today + timedelta(days=3), REFUND, "30", ing, refund_of=dinner)

    lines = gripr_budget_service.get_budget_status(db, today)
    assert next(line for line in lines if line.category.id == food.id).spent == Decimal(60)
    assert gripr_account_service.compute_balance(db, ing) == Decimal(0)


def test_income_vs_expense_lowers_expense_and_leaves_income_alone(setup):
    db, tr, ing, food = setup
    salary = make_category(db, "Salaris", kind=GriprCategoryKind.INCOME)
    book(db, date(2026, 5, 1), INCOME, "2000", ing, salary)
    dinner = book(db, date(2026, 5, 10), EXPENSE, "60", tr, food)
    book(db, date(2026, 5, 12), REFUND, "30", ing, refund_of=dinner)

    (may,) = gripr_overview_service.income_vs_expense(db, months=1, as_of=date(2026, 5, 20))
    assert may.income == Decimal(2000)
    assert may.expense == Decimal(30)


def test_spending_by_category_nets_refunds_and_drops_a_fully_refunded_category(setup):
    db, tr, ing, food = setup
    bars = make_category(db, "Eten & Drinken (Bars)", parent_id=food.id)
    travel = make_category(db, "Reizen")
    drinks = book(db, date(2026, 5, 10), EXPENSE, "40", tr, bars)
    book(db, date(2026, 5, 11), REFUND, "10", ing, refund_of=drinks)
    tickets = book(db, date(2026, 5, 12), EXPENSE, "200", tr, travel)
    book(db, date(2026, 5, 20), REFUND, "200", tr, refund_of=tickets)

    result = gripr_overview_service.spending_by_category(db, date(2026, 5, 15))
    assert [(c.name, c.amount) for c in result] == [("Eten & Drinken", Decimal(30))]


def test_category_trend_attributes_a_late_refund_to_the_expenses_month(setup):
    db, tr, ing, food = setup
    dinner = book(db, date(2026, 4, 30), EXPENSE, "60", tr, food)
    book(db, date(2026, 5, 3), REFUND, "30", ing, refund_of=dinner)

    trend = gripr_overview_service.category_trend(db, food.id, months=2, as_of=date(2026, 5, 20))
    assert [(p.month, p.amount) for p in trend] == [(date(2026, 4, 1), Decimal(30)), (date(2026, 5, 1), Decimal(0))]


def test_budget_suggestion_nets_recurring_refund_rules(setup):
    db, tr, ing, food = setup
    housing = make_category(db, "Wonen")
    for name, type_, amount in [("Rent", EXPENSE, "1200"), ("Housemate's half", REFUND, "600")]:
        db.add(GriprRecurringTransaction(
            name=name, type=type_, amount=Decimal(amount), account_id=ing.id, category_id=housing.id,
            frequency=GriprRecurrenceFrequency.MONTHLY, start_date=date(2026, 1, 1), next_due_date=date(2026, 1, 1),
        ))
    db.flush()

    suggestions = gripr_budget_service.get_suggestions(db, date(2026, 3, 1))
    assert next(s for s in suggestions if s.category_id == housing.id).recurring_monthly == Decimal("600.00")


# -- the link itself -----------------------------------------------------------------------


def test_a_linked_refund_takes_its_expenses_category(setup):
    db, tr, ing, food = setup
    other = make_category(db, "Overig")
    dinner = book(db, date(2026, 5, 10), EXPENSE, "60", tr, food)
    refund = book(db, date(2026, 5, 11), REFUND, "30", ing, other, refund_of=dinner)

    assert refund.category_id == food.id


def test_refunded_totals_sums_every_refund_per_expense(setup):
    db, tr, ing, food = setup
    dinner = book(db, date(2026, 5, 10), EXPENSE, "90", tr, food)
    book(db, date(2026, 5, 11), REFUND, "30", ing, refund_of=dinner)
    book(db, date(2026, 5, 12), REFUND, "30", tr, refund_of=dinner)

    assert gripr_transaction_repo.refunded_totals(db, [dinner.id]) == {dinner.id: Decimal(60)}


def test_a_refund_under_an_income_category_is_rejected(setup):
    db, tr, ing, food = setup
    salary = make_category(db, "Salaris", kind=GriprCategoryKind.INCOME)
    with pytest.raises(gripr_transaction_service.InvalidRefundError):
        book(db, date(2026, 5, 11), REFUND, "30", ing, salary)


def test_a_refund_can_only_point_at_an_expense(setup):
    db, tr, ing, food = setup
    salary = make_category(db, "Salaris", kind=GriprCategoryKind.INCOME)
    paycheck = book(db, date(2026, 5, 1), INCOME, "2000", ing, salary)
    with pytest.raises(gripr_transaction_service.InvalidRefundError):
        book(db, date(2026, 5, 11), REFUND, "30", ing, refund_of=paycheck)


def test_only_a_refund_keeps_a_link(setup):
    db, tr, ing, food = setup
    dinner = book(db, date(2026, 5, 10), EXPENSE, "60", tr, food)
    other = book(db, date(2026, 5, 11), EXPENSE, "5", tr, food, refund_of=dinner)
    assert other.refund_of_id is None

    refund = book(db, date(2026, 5, 11), REFUND, "30", ing, refund_of=dinner)
    gripr_transaction_service.update_transaction(db, refund, type=INCOME)
    assert refund.refund_of_id is None


def test_recategorizing_an_expense_moves_its_refunds_along(setup):
    db, tr, ing, food = setup
    travel = make_category(db, "Reizen")
    dinner = book(db, date(2026, 5, 10), EXPENSE, "60", tr, food)
    refund = book(db, date(2026, 5, 11), REFUND, "30", ing, refund_of=dinner)

    gripr_transaction_service.update_transaction(db, dinner, category_id=travel.id)
    assert refund.category_id == travel.id


def test_an_expense_that_stops_being_one_leaves_its_refunds_unlinked(setup):
    db, tr, ing, food = setup
    dinner = book(db, date(2026, 5, 10), EXPENSE, "60", tr, food)
    refund = book(db, date(2026, 5, 11), REFUND, "30", ing, refund_of=dinner)

    gripr_transaction_service.update_transaction(db, dinner, type=GriprTransactionType.TRANSFER, counter_account_id=ing.id, category_id=None)
    assert refund.refund_of_id is None


def test_deleting_an_expense_keeps_its_refunds_but_unlinks_them(setup):
    db, tr, ing, food = setup
    dinner = book(db, date(2026, 5, 10), EXPENSE, "60", tr, food)
    refund = book(db, date(2026, 5, 11), REFUND, "30", ing, refund_of=dinner)

    gripr_transaction_service.delete_transaction(db, dinner)
    db.refresh(refund)
    assert refund.refund_of_id is None
    assert gripr_account_service.compute_balance(db, ing) == Decimal(30)


# -- API -----------------------------------------------------------------------------------


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_api_round_trips_a_refund_and_reports_what_came_back(client, setup):
    db, tr, ing, food = setup
    dinner = client.post("/api/gripr/transactions", json={
        "date": "2026-05-10", "type": "expense", "amount": "60", "account_id": tr.id, "category_id": food.id,
        "notes": "Dinner with Sam",
    }).json()
    refund = client.post("/api/gripr/transactions", json={
        "date": "2026-05-12", "type": "refund", "amount": "30", "account_id": ing.id, "refund_of_id": dinner["id"],
    })
    assert refund.status_code == 200
    body = refund.json()
    assert body["category_id"] == food.id
    assert body["refund_of"]["notes"] == "Dinner with Sam"
    assert body["refund_of"]["account_name"] == "Trade Republic"

    items = client.get("/api/gripr/transactions").json()["items"]
    listed = next(t for t in items if t["id"] == dinner["id"])
    assert Decimal(listed["refunded_amount"]) == Decimal(30)


def test_api_rejects_a_refund_under_an_income_category(client, setup):
    db, tr, ing, food = setup
    salary = make_category(db, "Salaris", kind=GriprCategoryKind.INCOME)
    response = client.post("/api/gripr/transactions", json={
        "date": "2026-05-12", "type": "refund", "amount": "30", "account_id": ing.id, "category_id": salary.id,
    })
    assert response.status_code == 400


def test_api_rejects_a_recurring_refund_rule_under_an_income_category(client, setup):
    db, tr, ing, food = setup
    salary = make_category(db, "Salaris", kind=GriprCategoryKind.INCOME)
    response = client.post("/api/gripr/recurring", json={
        "name": "Housemate", "type": "refund", "amount": "600", "account_id": ing.id, "category_id": salary.id,
        "frequency": "monthly", "start_date": "2026-01-01",
    })
    assert response.status_code == 400
