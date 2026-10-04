from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.models.listr_category import ListrCategory
from app.models.listr_item import ListrItem
from app.repositories import gripr_transaction_repo, picnic_session_repo, picnic_sync_repo
from app.services import picnic_sync_service
from app.services.picnic_provider import PicnicAuthError, PicnicDelivery, PicnicDeliveryDetail, PicnicOrder

CEST = timezone(timedelta(hours=2))


def at(day: date, hour: int = 15) -> datetime:
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=CEST)


class FakeProvider:
    def __init__(self):
        self.deliveries: list[PicnicDelivery] = []
        self.details: dict[str, PicnicDeliveryDetail] = {}
        self.detail_calls: list[str] = []
        self.raise_auth = False

    def get_deliveries(self, auth_key):
        if self.raise_auth:
            raise PicnicAuthError("expired")
        return self.deliveries

    def get_delivery_detail(self, auth_key, delivery_id):
        self.detail_calls.append(delivery_id)
        return self.details[delivery_id]


@pytest.fixture()
def provider():
    return FakeProvider()


@pytest.fixture()
def setup(db_session):
    """An ING account, a Boodschappen category, a connected session, sync on since Sep 1."""
    account = GriprAccount(name="ING", type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    category = GriprCategory(name="Boodschappen", kind=GriprCategoryKind.EXPENSE)
    db_session.add_all([account, category])
    db_session.flush()
    picnic_session_repo.set_auth_key(db_session, "key")
    picnic_sync_repo.update_settings(
        db_session, enabled=True, gripr_account_id=account.id, gripr_category_id=category.id, since=date(2026, 9, 1)
    )
    return account, category


def add_delivery(provider, delivery_id, day, orders, articles=()):
    """`orders` are (id, charged cents, order date) or (id, charged cents, order date, cents
    without deposit)."""
    parsed = [
        PicnicOrder(id=o[0], created_at=at(o[2], 21), charged_cents=o[1], total_cents=o[3] if len(o) > 3 else o[1])
        for o in orders
    ]
    provider.deliveries.append(
        PicnicDelivery(id=delivery_id, delivered_at=at(day), total_cents=sum(o.total_cents for o in parsed), order_count=len(parsed))
    )
    provider.details[delivery_id] = PicnicDeliveryDetail(id=delivery_id, orders=parsed, articles=list(articles))


def expenses(db):
    return [t for t in gripr_transaction_repo.list_all_transactions(db) if t.type == GriprTransactionType.EXPENSE]


def test_books_each_order_as_an_expense_on_its_order_date(db_session, provider, setup):
    account, category = setup
    add_delivery(provider, "d1", date(2026, 9, 20), [("505-1", 7871, date(2026, 9, 19)), ("505-2", 870, date(2026, 9, 19))])

    result = picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2))

    assert (result.deliveries, result.orders_booked, result.orders_matched) == (1, 2, 0)
    booked = sorted(expenses(db_session), key=lambda t: t.amount)
    assert [t.amount for t in booked] == [Decimal("8.70"), Decimal("78.71")]
    assert all(t.date == date(2026, 9, 19) and t.account_id == account.id and t.category_id == category.id for t in booked)
    assert booked[1].source_ref == "picnic_order:505-1"
    assert booked[1].notes == "Picnic"


def test_an_order_already_booked_by_hand_is_matched_not_booked_twice(db_session, provider, setup):
    account, _ = setup
    manual = GriprTransaction(
        date=date(2026, 9, 22), type=GriprTransactionType.EXPENSE, amount=Decimal("78.71"), account_id=account.id
    )
    db_session.add(manual)
    db_session.flush()
    add_delivery(provider, "d1", date(2026, 9, 20), [("505-1", 7871, date(2026, 9, 19))])

    result = picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2))

    assert (result.orders_booked, result.orders_matched) == (0, 1)
    assert len(expenses(db_session)) == 1
    assert manual.source_ref == "picnic_order:505-1"  # claimed, so no later order can match it again


def test_one_hand_booked_expense_for_the_whole_delivery_matches_all_its_orders(db_session, provider, setup):
    # The real 9 Sep case: three orders (62.60 + 11.60 + 12.91 charged, 86.12 without deposit),
    # booked by hand as a single 86.12 five days after the delivery.
    account, _ = setup
    db_session.add(GriprTransaction(date=date(2026, 9, 14), type=GriprTransactionType.EXPENSE, amount=Decimal("86.12"), account_id=account.id))
    db_session.flush()
    add_delivery(provider, "d1", date(2026, 9, 9), [
        ("207-1", 6260, date(2026, 9, 7), 6194),
        ("301-1", 1160, date(2026, 9, 8), 1127),
        ("301-2", 1291, date(2026, 9, 8), 1291),
    ])

    result = picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2))

    assert (result.orders_booked, result.orders_matched) == (0, 3)
    assert len(expenses(db_session)) == 1


def test_an_order_booked_by_hand_without_deposit_still_matches(db_session, provider, setup):
    account, _ = setup
    db_session.add(GriprTransaction(date=date(2026, 9, 20), type=GriprTransactionType.EXPENSE, amount=Decimal("78.32"), account_id=account.id))
    db_session.flush()
    add_delivery(provider, "d1", date(2026, 9, 20), [("505-1", 7871, date(2026, 9, 19), 7832), ("505-2", 870, date(2026, 9, 19))])

    result = picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2))

    # 505-1 matched by its deposit-free amount; 505-2 had nothing, so it's booked.
    assert (result.orders_booked, result.orders_matched) == (1, 1)
    assert sorted(t.amount for t in expenses(db_session)) == [Decimal("8.70"), Decimal("78.32")]


def test_a_hand_booked_expense_outside_the_window_or_for_another_amount_does_not_match(db_session, provider, setup):
    account, _ = setup
    db_session.add_all([
        GriprTransaction(date=date(2026, 9, 1), type=GriprTransactionType.EXPENSE, amount=Decimal("78.71"), account_id=account.id),
        GriprTransaction(date=date(2026, 9, 20), type=GriprTransactionType.EXPENSE, amount=Decimal("78.70"), account_id=account.id),
    ])
    db_session.flush()
    add_delivery(provider, "d1", date(2026, 9, 20), [("505-1", 7871, date(2026, 9, 19))])

    result = picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2))

    assert (result.orders_booked, result.orders_matched) == (1, 0)


def test_each_delivery_is_processed_once(db_session, provider, setup):
    add_delivery(provider, "d1", date(2026, 9, 20), [("505-1", 7871, date(2026, 9, 19))])

    picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2))
    second = picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2))

    assert second.deliveries == 0
    assert provider.detail_calls == ["d1"]
    assert len(expenses(db_session)) == 1


def test_deliveries_before_since_or_while_switched_off_are_left_alone(db_session, provider, setup):
    add_delivery(provider, "old", date(2026, 8, 30), [("505-0", 5000, date(2026, 8, 29))])

    assert picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2)).deliveries == 0

    picnic_sync_repo.update_settings(db_session, enabled=False, since=date(2026, 8, 1))
    add_delivery(provider, "d1", date(2026, 9, 20), [("505-1", 7871, date(2026, 9, 19))])
    assert picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2)).deliveries == 0
    assert expenses(db_session) == []


def test_without_an_account_or_category_it_only_restocks(db_session, provider, setup):
    picnic_sync_repo.update_settings(db_session, gripr_account_id=None)
    add_delivery(provider, "d1", date(2026, 9, 20), [("505-1", 7871, date(2026, 9, 19))])

    result = picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2))

    assert (result.deliveries, result.orders_booked) == (1, 0)
    assert expenses(db_session) == []


def test_restocks_tracked_items_linked_to_the_delivered_products(db_session, provider, setup):
    category = ListrCategory(name="Groente & Fruit")
    db_session.add(category)
    db_session.flush()
    bananas = ListrItem(name="Bananen", category_id=category.id, default_unit="kg", picnic_product_id="s1018276",
                        inventory_status="out", inventory_count=0, inventory_minimum=1)
    pasta = ListrItem(name="Spaghetti", category_id=category.id, default_unit="pak", picnic_product_id="s1016029",
                      inventory_status=None, inventory_count=0)  # not tracked
    db_session.add_all([bananas, pasta])
    db_session.flush()
    add_delivery(provider, "d1", date(2026, 9, 20), [("505-1", 7871, date(2026, 9, 19))],
                 articles=[("s1018276", 1), ("s1018276", 1), ("s1016029", 2), ("s9999999", 1)])

    result = picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2))

    assert result.items_restocked == 2
    assert bananas.inventory_count == 2
    assert bananas.inventory_status == "in_stock"
    assert pasta.inventory_count == 0


def test_an_expired_session_is_cleared_and_reported(db_session, provider, setup):
    provider.raise_auth = True

    with pytest.raises(picnic_sync_service.PicnicSyncNotConnected):
        picnic_sync_service.sync(db_session, provider=provider, as_of=date(2026, 10, 2))

    assert picnic_session_repo.get(db_session) is None
