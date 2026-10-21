"""Overview's balance forecast: the checking balance day by day through the current period --
real up to today, then a projection for the rest of it from recurring rules and budget headroom."""

from datetime import date, timedelta
from decimal import Decimal

from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_recurring import GriprRecurrenceFrequency, GriprRecurringTransaction
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.services import gripr_budget_service, gripr_overview_service
from app.services.gripr_period_service import period_bounds

T = GriprTransactionType
TODAY = date.today()
PERIOD_START, PERIOD_END = period_bounds(TODAY, 1)


def make_account(db, name, type_=GriprAccountType.CHECKING, **kw) -> GriprAccount:
    account = GriprAccount(name=name, type=type_, balance_mode=GriprBalanceMode.TRANSACTIONAL, **kw)
    db.add(account)
    db.flush()
    return account


def make_category(db, name, kind=GriprCategoryKind.EXPENSE, parent_id=None) -> GriprCategory:
    category = GriprCategory(name=name, kind=kind, parent_id=parent_id)
    db.add(category)
    db.flush()
    return category


def make_txn(db, d, type_, amount, account, counter_account=None, category=None) -> GriprTransaction:
    txn = GriprTransaction(
        date=d, type=type_, amount=Decimal(amount), account_id=account.id,
        counter_account_id=counter_account.id if counter_account else None,
        category_id=category.id if category else None,
    )
    db.add(txn)
    db.flush()
    return txn


def make_recurring(db, name, next_due_date, account, amount, type_=T.EXPENSE, category=None, **kw) -> GriprRecurringTransaction:
    rule = GriprRecurringTransaction(
        name=name, type=type_, amount=Decimal(amount), account_id=account.id,
        category_id=category.id if category else None,
        frequency=kw.pop("frequency", GriprRecurrenceFrequency.MONTHLY),
        start_date=kw.pop("start_date", next_due_date),
        next_due_date=next_due_date,
        **kw,
    )
    db.add(rule)
    db.flush()
    return rule


def test_no_checking_account_gives_an_empty_series(db_session):
    make_account(db_session, "Spaarrekening", type_=GriprAccountType.SAVINGS)

    assert gripr_overview_service.balance_forecast(db_session).points == []


def test_actual_leg_follows_booked_transactions_up_to_today(db_session):
    checking = make_account(db_session, "ING", opening_balance=Decimal(1000))
    make_txn(db_session, PERIOD_START, T.INCOME, "500", checking)
    make_txn(db_session, TODAY, T.EXPENSE, "100", checking)

    points = gripr_overview_service.balance_forecast(db_session).points
    actuals = [p for p in points if not p.is_forecast]

    assert actuals[0].date == PERIOD_START
    assert actuals[-1].date == TODAY
    assert actuals[-1].balance == Decimal(1400)
    assert all(not p.is_forecast for p in actuals)


def test_forecast_leg_lands_a_recurring_expense_on_its_due_date(db_session):
    checking = make_account(db_session, "ING", opening_balance=Decimal(1000))
    due = TODAY + timedelta(days=3)
    if due > PERIOD_END:
        return  # too close to period end this run -- nothing to assert
    make_recurring(db_session, "Netflix", due, checking, "15")

    points = gripr_overview_service.balance_forecast(db_session).points
    by_date = {p.date: p for p in points}

    before = by_date[due - timedelta(days=1)]
    on_due = by_date[due]
    assert on_due.is_forecast
    assert on_due.balance == before.balance - Decimal(15)


def test_forecast_spreads_budget_headroom_net_of_recurring(db_session):
    if PERIOD_END - TODAY < timedelta(days=4):
        return  # not enough days left this period to assert a spread
    checking = make_account(db_session, "ING", opening_balance=Decimal(1000))
    groceries = make_category(db_session, "Groceries")
    gripr_budget_service.set_budget(db_session, groceries.id, PERIOD_START, Decimal(200))
    # 50 already spent, and a 30 recurring grocery delivery still to come -- headroom is 200-50-30=120.
    make_txn(db_session, TODAY, T.EXPENSE, "50", checking, category=groceries)
    due = TODAY + timedelta(days=2)
    make_recurring(db_session, "Weekly delivery", due, checking, "30", category=groceries)

    points = gripr_overview_service.balance_forecast(db_session).points
    last = points[-1]
    remaining_days = (PERIOD_END - TODAY).days
    expected_spread_total = Decimal(120) / remaining_days * remaining_days

    today_point = next(p for p in points if p.date == TODAY)
    # Balance today: 1000 - 50 = 950. By period end: minus the 30 recurring, minus the spread.
    expected_end = today_point.balance - Decimal(30) - expected_spread_total
    assert last.balance == expected_end.quantize(Decimal("0.01"))


def test_fully_spent_budget_adds_no_further_spread(db_session):
    if PERIOD_END == TODAY:
        return  # no forecast leg to assert on the last day of a period
    checking = make_account(db_session, "ING", opening_balance=Decimal(1000))
    leisure = make_category(db_session, "Leisure")
    gripr_budget_service.set_budget(db_session, leisure.id, PERIOD_START, Decimal(50))
    make_txn(db_session, TODAY, T.EXPENSE, "80", checking, category=leisure)

    points = gripr_overview_service.balance_forecast(db_session).points
    today_point = next(p for p in points if p.date == TODAY)
    last = points[-1]

    assert last.balance == today_point.balance


def test_transfer_between_two_checking_accounts_nets_to_zero(db_session):
    main = make_account(db_session, "ING")
    joint = make_account(db_session, "Joint")
    make_txn(db_session, TODAY, T.TRANSFER, "200", main, joint)

    points = gripr_overview_service.balance_forecast(db_session).points

    assert points[-1].balance == Decimal(0)


def test_savings_account_is_excluded_from_the_checking_balance(db_session):
    checking = make_account(db_session, "ING", opening_balance=Decimal(500))
    savings = make_account(db_session, "Spaarrekening", type_=GriprAccountType.SAVINGS, opening_balance=Decimal(2000))
    make_txn(db_session, TODAY, T.TRANSFER, "100", checking, savings)

    points = gripr_overview_service.balance_forecast(db_session).points

    assert points[-1].balance == Decimal(400)
