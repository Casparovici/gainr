"""gripr's bell: what the syncs booked since the last visit, money that came back for something
fronted (or is still owed a month on), and banks that need attention."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.bank_sync import BankConnection
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.routers import gripr as gripr_router
from app.services import gripr_notification_service, gripr_transaction_service

T = GriprTransactionType
NOW = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)
LAST_VISIT = NOW - timedelta(days=1)


@pytest.fixture()
def ing(db_session) -> GriprAccount:
    account = GriprAccount(name="ING", type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db_session.add_all([
        account,
        BankConnection(aspsp_name="ING", aspsp_country="NL", source_prefix="ing", enabled=True, since=date(2026, 10, 3),
                       session_id="s", valid_until=datetime(2027, 3, 30), last_synced_at=datetime(2026, 10, 5, 4, 30)),
    ])
    db_session.flush()
    return account


def booked(db, account, amount, *, ref=None, created=NOW - timedelta(hours=2), category=None, type_=T.EXPENSE, **kw) -> GriprTransaction:
    txn = gripr_transaction_service.create_transaction(
        db, date=created.date(), type=type_, amount=Decimal(amount), account_id=account.id,
        category_id=category.id if category else None, source_ref=ref, **kw,
    )
    txn.created_at = created.replace(tzinfo=None)
    db.flush()
    return txn


def notifications(db, since=LAST_VISIT):
    return gripr_notification_service.list_notifications(db, since, NOW)


def test_new_synced_transactions_are_counted_per_source_with_what_needs_a_category(db_session, ing):
    groceries = GriprCategory(name="Boodschappen", kind=GriprCategoryKind.EXPENSE)
    db_session.add(groceries)
    db_session.flush()
    booked(db_session, ing, "12.50", ref="ing:1")
    booked(db_session, ing, "8.00", ref="ing:2", category=groceries)
    booked(db_session, ing, "50.00", ref="picnic_order:abc", category=groceries)
    booked(db_session, ing, "99.00", ref="ing:old", created=LAST_VISIT - timedelta(hours=1))  # seen last time
    booked(db_session, ing, "5.00")  # typed in by hand: no news

    items = {n.key: n for n in notifications(db_session)}

    assert items["synced:ING"].title == "2 new transactions from ING"
    assert items["synced:ING"].detail == "1 needs a category"
    assert items["synced:ING"].link == "/gripr/transactions?category=uncategorized"
    assert items["synced:Picnic"].title == "1 new transaction from Picnic"
    assert items["synced:Picnic"].detail is None


def test_money_back_for_a_fronted_expense_and_a_reminder_when_it_stays_open(db_session, ing):
    dinner = booked(db_session, ing, "100.00", created=NOW - timedelta(days=40), notes="Etentje",
                    expected_back=Decimal("75.00"), expected_from="Jan")
    refund = booked(db_session, ing, "25.00", type_=T.REFUND, refund_of_id=dinner.id)

    items = {n.key: n for n in notifications(db_session)}

    assert items[f"money_back:{refund.id}"].title == "€ 25,00 came back from Jan"
    assert items[f"money_back:{refund.id}"].detail == "for Etentje"
    still = items[f"still_owed:{dinner.id}"]
    assert still.title == "€ 50,00 still owed by Jan"
    assert still.at.date() == dinner.date + timedelta(days=30)


def test_something_owed_less_than_a_month_isnt_a_reminder_yet(db_session, ing):
    booked(db_session, ing, "40.00", created=NOW - timedelta(days=5), expected_back=Decimal("40.00"))

    assert not [n for n in notifications(db_session) if n.kind == "still_owed"]


def test_banks_needing_attention_stay_listed_but_keep_their_date(db_session, ing):
    tr = BankConnection(aspsp_name="Trade Republic", aspsp_country="NL", source_prefix="tr", amount_only=True, enabled=True,
                        since=date(2026, 10, 3), session_id="s2", valid_until=datetime(2026, 10, 12),
                        last_synced_at=datetime(2026, 10, 3, 5, 15), last_error="Trade Republic allows only a few reads a day")
    off = BankConnection(aspsp_name="Rabobank", aspsp_country="NL", source_prefix="rabo", enabled=False)
    db_session.add_all([tr, off])
    db_session.flush()

    items = {n.key: n for n in notifications(db_session)}

    assert items["bank:tr:expiring"].title == "Trade Republic needs a reconnect soon"
    assert items["bank:tr:expiring"].at == datetime(2026, 9, 28, tzinfo=timezone.utc)
    error = items["bank:tr:error"]
    assert error.detail.startswith("Trade Republic allows")
    assert error.at == datetime(2026, 10, 3, 5, 15, tzinfo=timezone.utc)  # stable: no new dot each visit
    assert not any(k.startswith("bank:ing") or k.startswith("bank:rabo") for k in items)


def test_an_ended_consent_asks_for_a_reconnect(db_session, ing):
    connection = db_session.query(BankConnection).one()
    connection.valid_until = datetime(2026, 10, 1)

    (item,) = [n for n in notifications(db_session) if n.kind == "bank"]

    assert item.key == "bank:ing:reconnect"


def test_the_api_lists_newest_first_and_defaults_to_a_week(db_session, ing):
    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    booked(db_session, ing, "12.50", ref="ing:1", created=recent)

    body = client.get("/api/gripr/notifications").json()
    assert [n["key"] for n in body] == ["synced:ING"]
    assert client.get("/api/gripr/notifications", params={"since": datetime.now(timezone.utc).isoformat()}).json() == []
