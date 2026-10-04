"""Money expected back (docs/adr/0032): an expense the reader fronted for others counts only their
own share from the start; what's still to come back is listed as owed until refunds cover it or the
rest is written off."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_transaction import GriprTransactionType
from app.repositories import gripr_transaction_repo
from app.routers import gripr as gripr_router
from app.services import gripr_account_service, gripr_receivable_service, gripr_transaction_service

EXPENSE = GriprTransactionType.EXPENSE
INCOME = GriprTransactionType.INCOME
REFUND = GriprTransactionType.REFUND
DAY = date.today() - timedelta(days=10)


@pytest.fixture()
def ing(db_session) -> GriprAccount:
    account = GriprAccount(name="ING", type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db_session.add(account)
    db_session.flush()
    return account


@pytest.fixture()
def restaurants(db_session) -> GriprCategory:
    category = GriprCategory(name="Restaurants", kind=GriprCategoryKind.EXPENSE)
    db_session.add(category)
    db_session.flush()
    return category


def dinner(db, ing, restaurants, expected="75.00", who="Jan, Piet", amount="100.00"):
    return gripr_transaction_service.create_transaction(
        db, date=DAY, type=EXPENSE, amount=Decimal(amount), account_id=ing.id, category_id=restaurants.id,
        notes="Etentje", expected_back=Decimal(expected) if expected else None, expected_from=who,
    )


def money_back(db, ing, expense, amount, day=DAY + timedelta(days=2)):
    return gripr_transaction_service.create_transaction(
        db, date=day, type=REFUND, amount=Decimal(amount), account_id=ing.id, refund_of_id=expense.id,
    )


def spend(db) -> Decimal:
    return gripr_transaction_repo.sum_net_spend(db, DAY - timedelta(days=1), date.today())


def test_only_your_share_counts_from_the_start(db_session, ing, restaurants):
    expense = dinner(db_session, ing, restaurants)

    assert spend(db_session) == Decimal("25.00")
    # The account itself really paid the whole bill.
    assert gripr_account_service.list_with_balances(db_session)[0].balance == Decimal("-100.00")
    (open_,) = gripr_receivable_service.list_open(db_session)
    assert (open_.expense.id, open_.expected, open_.received, open_.outstanding) == (expense.id, Decimal("75.00"), 0, Decimal("75.00"))


def test_repayments_close_what_is_owed_without_changing_your_share(db_session, ing, restaurants):
    expense = dinner(db_session, ing, restaurants)
    money_back(db_session, ing, expense, "50.00")

    assert spend(db_session) == Decimal("25.00")
    assert gripr_receivable_service.list_open(db_session)[0].outstanding == Decimal("25.00")

    money_back(db_session, ing, expense, "25.00")
    assert spend(db_session) == Decimal("25.00")
    assert gripr_receivable_service.list_open(db_session) == []


def test_getting_more_back_than_expected_lowers_your_share_further(db_session, ing, restaurants):
    expense = dinner(db_session, ing, restaurants)
    money_back(db_session, ing, expense, "80.00")

    assert spend(db_session) == Decimal("20.00")


def test_writing_off_makes_the_rest_your_own_spending(db_session, ing, restaurants):
    expense = dinner(db_session, ing, restaurants)
    money_back(db_session, ing, expense, "50.00")

    gripr_receivable_service.write_off(db_session, expense)

    assert expense.expected_back == Decimal("50.00")
    assert spend(db_session) == Decimal("50.00")
    assert gripr_receivable_service.list_open(db_session) == []


def test_writing_off_with_nothing_back_clears_the_expectation(db_session, ing, restaurants):
    expense = dinner(db_session, ing, restaurants)

    gripr_receivable_service.write_off(db_session, expense)

    assert (expense.expected_back, expense.expected_from) == (None, None)
    assert spend(db_session) == Decimal("100.00")


def test_more_than_the_expense_cant_be_expected_back(db_session, ing, restaurants):
    with pytest.raises(gripr_transaction_service.InvalidRefundError):
        dinner(db_session, ing, restaurants, expected="120.00")


def test_only_an_expense_expects_money_back(db_session, ing, restaurants):
    expense = dinner(db_session, ing, restaurants)

    gripr_transaction_service.update_transaction(db_session, expense, type=INCOME, category_id=None)

    assert (expense.expected_back, expense.expected_from) == (None, None)


def test_a_repayment_is_matched_by_name_when_only_one_expense_fits(db_session, ing, restaurants):
    expense = dinner(db_session, ing, restaurants, who="Jan de Vries")
    dinner(db_session, ing, restaurants, who="Piet")

    assert gripr_receivable_service.match_incoming(db_session, "J. de Vries via Tikkie", Decimal("25.00")) == expense
    assert gripr_receivable_service.match_incoming(db_session, "Klaas", Decimal("25.00")) is None
    assert gripr_receivable_service.match_incoming(db_session, "Jan de Vries", Decimal("90.00")) is None  # more than owed


def test_two_expenses_from_the_same_person_are_left_for_you_to_pick(db_session, ing, restaurants):
    dinner(db_session, ing, restaurants, who="Jan")
    dinner(db_session, ing, restaurants, who="Jan")

    assert gripr_receivable_service.match_incoming(db_session, "Jan via Tikkie", Decimal("10.00")) is None


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_the_api_lists_what_is_owed_and_writes_it_off(client, db_session, ing, restaurants):
    expense = dinner(db_session, ing, restaurants)
    money_back(db_session, ing, expense, "30.00")

    body = client.get("/api/gripr/receivables").json()
    assert body["total"] == "45.00"
    assert [(i["id"], i["expected_from"], i["received"], i["outstanding"]) for i in body["items"]] == [
        (expense.id, "Jan, Piet", "30.00", "45.00")
    ]
    listed = client.get("/api/gripr/transactions").json()["items"]
    assert next(t for t in listed if t["id"] == expense.id)["outstanding"] == "45.00"

    after = client.post(f"/api/gripr/receivables/{expense.id}/write-off").json()
    assert after == {"total": "0", "items": []}


def test_the_api_sets_and_clears_an_expectation(client, db_session, ing, restaurants):
    expense = dinner(db_session, ing, restaurants, expected=None, who=None)

    body = client.put(f"/api/gripr/transactions/{expense.id}", json={"expected_back": "40.00", "expected_from": " Abel "}).json()
    assert (body["expected_back"], body["expected_from"], body["outstanding"]) == ("40.00", "Abel", "40.00")
    assert client.put(f"/api/gripr/transactions/{expense.id}", json={"expected_back": "200.00"}).status_code == 400
    body = client.put(f"/api/gripr/transactions/{expense.id}", json={"expected_back": None}).json()
    assert (body["expected_back"], body["expected_from"]) == (None, None)


def test_what_is_owed_counts_in_net_worth_until_written_off(db_session, ing, restaurants):
    expense = dinner(db_session, ing, restaurants)

    assert gripr_account_service.net_worth(db_session) == Decimal("-25.00")  # -100 paid, 75 owed

    gripr_receivable_service.write_off(db_session, expense)
    assert gripr_account_service.net_worth(db_session) == Decimal("-100.00")
