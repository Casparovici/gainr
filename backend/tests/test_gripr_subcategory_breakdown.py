"""Overview's per-subcategory split of a top-level category's spending."""

from datetime import date, timedelta
from decimal import Decimal

from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.services import gripr_overview_service

TODAY = date.today()


def test_splits_a_categorys_spending_by_subcategory_and_leaves_out_other_categories(db_session):
    account = GriprAccount(name="ING", type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    food = GriprCategory(name="Boodschappen", kind=GriprCategoryKind.EXPENSE)
    car = GriprCategory(name="Vervoer", kind=GriprCategoryKind.EXPENSE)
    db_session.add_all([account, food, car])
    db_session.flush()
    market = GriprCategory(name="Markt", kind=GriprCategoryKind.EXPENSE, parent_id=food.id)
    bakery = GriprCategory(name="Bakker", kind=GriprCategoryKind.EXPENSE, parent_id=food.id)
    db_session.add_all([market, bakery])
    db_session.flush()
    for category, amount in [(market, "30"), (market, "10"), (bakery, "12"), (food, "5"), (car, "99")]:
        db_session.add(
            GriprTransaction(
                date=TODAY, type=GriprTransactionType.EXPENSE, amount=Decimal(amount),
                account_id=account.id, category_id=category.id,
            )
        )
    db_session.flush()

    rows = gripr_overview_service.subcategory_breakdown(db_session, food.id, TODAY)

    assert [(r.name, r.amount) for r in rows] == [("Markt", Decimal(40)), ("Bakker", Decimal(12)), ("Boodschappen", Decimal(5))]
    assert rows[-1].category_id == food.id


def test_a_period_without_spending_is_empty(db_session):
    food = GriprCategory(name="Boodschappen", kind=GriprCategoryKind.EXPENSE)
    db_session.add(food)
    db_session.flush()

    assert gripr_overview_service.subcategory_breakdown(db_session, food.id, TODAY - timedelta(days=400)) == []
