"""Overview's planning figures: what is safe to move out of checking, the savings rate and
runway, and the budgets that have been missed the same way period after period."""

from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from app.models.bank_sync import BankSyncedTransaction
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_recurring import GriprRecurrenceFrequency, GriprRecurringTransaction
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.repositories import gripr_transaction_repo
from app.services import gripr_budget_service, gripr_overview_service
from app.services.gripr_period_service import period_bounds

T = GriprTransactionType
TODAY = date.today()
PERIOD_START, PERIOD_END = period_bounds(TODAY, 1)


def past_start(periods_ago: int) -> date:
    return PERIOD_START - relativedelta(months=periods_ago)


def account(db, name, type_=GriprAccountType.CHECKING, **kw):
    a = GriprAccount(name=name, type=type_, balance_mode=GriprBalanceMode.TRANSACTIONAL, **kw)
    db.add(a)
    db.flush()
    return a


def category(db, name, kind=GriprCategoryKind.EXPENSE):
    c = GriprCategory(name=name, kind=kind)
    db.add(c)
    db.flush()
    return c


def txn(db, day, type_, amount, acc, cat=None, source_ref=None):
    t = GriprTransaction(
        date=day, type=type_, amount=Decimal(amount), account_id=acc.id,
        category_id=cat.id if cat else None, source_ref=source_ref,
    )
    db.add(t)
    db.flush()
    return t


# -- safe to move -----------------------------------------------------------------------------


def test_safe_to_move_is_the_forecasts_low_point_minus_a_buffer_of_everyday_spending(db_session):
    checking = account(db_session, "ING", opening_balance=Decimal(5000))
    # 840 of everyday spending over the 84 days before today -> a week's worth is 70
    txn(db_session, TODAY - timedelta(days=10), T.EXPENSE, "420", checking)
    txn(db_session, TODAY - timedelta(days=20), T.EXPENSE, "420", checking)
    due = TODAY + timedelta(days=2)
    if due > PERIOD_END:
        return  # too close to the period's end to put a payment in it
    db_session.add(GriprRecurringTransaction(
        name="Rent", type=T.EXPENSE, amount=Decimal(200), account_id=checking.id,
        frequency=GriprRecurrenceFrequency.MONTHLY, start_date=due, next_due_date=due,
    ))
    db_session.flush()

    forecast = gripr_overview_service.balance_forecast(db_session)

    assert forecast.buffer == Decimal("70.00")
    assert forecast.expected_end == forecast.points[-1].balance
    assert forecast.lowest.balance == forecast.points[-1].balance  # the payment is the low point
    assert forecast.lowest.balance == Decimal("3960.00")  # 5000 - 840 - the 200 payment still to come
    assert forecast.safe_to_move == Decimal("3890.00")
    assert forecast.weekday_pattern is False  # three expenses are no pattern


def test_nothing_is_safe_to_move_when_the_low_point_is_inside_the_buffer(db_session):
    checking = account(db_session, "ING", opening_balance=Decimal(900))
    txn(db_session, TODAY - timedelta(days=10), T.EXPENSE, "420", checking)
    txn(db_session, TODAY - timedelta(days=11), T.EXPENSE, "420", checking)  # 60 left; the buffer is 70

    forecast = gripr_overview_service.balance_forecast(db_session)

    assert forecast.safe_to_move == 0


# -- the spending pattern ---------------------------------------------------------------------


def test_remaining_spending_follows_the_weekdays_the_reader_spends_on(db_session):
    saturdays_left = [TODAY + timedelta(days=i) for i in range(1, (PERIOD_END - TODAY).days + 1) if (TODAY + timedelta(days=i)).weekday() == 5]
    if not saturdays_left:
        return  # no Saturday left in this period to see the pattern on
    checking = account(db_session, "ING", opening_balance=Decimal(2000))
    food = category(db_session, "Boodschappen")
    gripr_budget_service.set_budget(db_session, food.id, PERIOD_START, Decimal(500))
    # Twelve weeks of shopping done only on Saturdays.
    saturday = TODAY - timedelta(days=1)
    while saturday.weekday() != 5:
        saturday -= timedelta(days=1)
    for week in range(12):
        for _ in range(3):
            txn(db_session, saturday - timedelta(weeks=week), T.EXPENSE, "10", checking)

    forecast = gripr_overview_service.balance_forecast(db_session)

    assert forecast.weekday_pattern is True
    ahead = [p for p in forecast.points if p.is_forecast]
    for previous, point in zip([p for p in forecast.points if p.date == TODAY] + ahead, ahead):
        if point.date.weekday() != 5:
            assert point.balance == previous.balance  # no spending on any other day
    assert ahead[-1].balance < forecast.points[[p.date for p in forecast.points].index(TODAY)].balance


def test_recurring_payments_and_large_purchases_are_not_everyday_spending(db_session):
    checking = account(db_session, "ING")
    window = (TODAY - timedelta(days=30), TODAY)
    txn(db_session, TODAY - timedelta(days=3), T.EXPENSE, "12", checking)
    txn(db_session, TODAY - timedelta(days=4), T.EXPENSE, "800", checking, source_ref="pefi_recurring:1:2026-10-01")
    fulfilled = txn(db_session, TODAY - timedelta(days=5), T.EXPENSE, "55", checking, source_ref="ing:abc")
    rule = GriprRecurringTransaction(
        name="Energie", type=T.EXPENSE, amount=Decimal("55"), account_id=checking.id,
        frequency=GriprRecurrenceFrequency.MONTHLY, start_date=TODAY, next_due_date=TODAY,
    )
    db_session.add(rule)
    db_session.flush()
    db_session.add(BankSyncedTransaction(
        reference="ing:abc", iban="NL00", transacted_on=TODAY - timedelta(days=5), outcome="fulfilled",
        gripr_transaction_id=fulfilled.id, recurring_id=rule.id,
    ))
    db_session.flush()

    txn(db_session, TODAY - timedelta(days=6), T.EXPENSE, "2500", checking)  # a purchase, not routine

    rows = gripr_transaction_repo.everyday_expenses(db_session, *window)

    assert rows == [(TODAY - timedelta(days=3), Decimal("12"))]


# -- savings rate and runway ------------------------------------------------------------------


def test_one_outlier_period_does_not_set_the_typical_monthly_spend(db_session):
    checking = account(db_session, "ING")
    for ago, amount in ((1, "400"), (2, "500"), (3, "9000")):
        txn(db_session, past_start(ago), T.EXPENSE, amount, checking)

    assert gripr_overview_service.average_monthly_expense(db_session, TODAY) == Decimal(500)


def test_savings_rate_and_runway(db_session):
    checking = account(db_session, "ING")
    savings = account(db_session, "Spaar", GriprAccountType.SAVINGS, opening_balance=Decimal(3000))
    account(db_session, "Vakantie", GriprAccountType.SAVINGS, opening_balance=Decimal(700), held_in_account_id=savings.id)
    for ago in (1, 2, 3):
        txn(db_session, past_start(ago), T.INCOME, "1000", checking)
        txn(db_session, past_start(ago), T.EXPENSE, "500", checking)
    txn(db_session, PERIOD_START, T.INCOME, "1000", checking)
    txn(db_session, PERIOD_START, T.EXPENSE, "400", checking)

    health = gripr_overview_service.savings_health(db_session, TODAY, today=TODAY)

    assert health.savings_rate_pct == Decimal(60)
    assert health.trailing_rate_pct == Decimal(50)
    # checking 2100 + savings 3000; the reservation pot is earmarked and left out
    assert health.liquid_savings == Decimal(5100)
    assert health.average_monthly_expense == Decimal(500)
    assert health.runway_months == Decimal("10.2")


def test_no_income_or_no_spending_gives_no_figures_rather_than_a_division_by_zero(db_session):
    account(db_session, "ING", opening_balance=Decimal(100))

    health = gripr_overview_service.savings_health(db_session, TODAY, today=TODAY)

    assert health.savings_rate_pct is None and health.trailing_rate_pct is None
    assert health.average_monthly_expense is None and health.runway_months is None
    assert health.liquid_savings == Decimal(100)


# -- budgets that keep missing -----------------------------------------------------------------


def budgeted_history(db, cat, acc, budget, spent):
    for ago in range(0, 4):
        gripr_budget_service.set_budget(db, cat.id, past_start(ago), Decimal(budget))
    for ago, amount in zip((1, 2, 3), spent):
        txn(db, past_start(ago), T.EXPENSE, amount, acc, cat)


def test_a_budget_missed_the_same_way_three_periods_running_is_flagged_with_a_better_figure(db_session):
    checking = account(db_session, "ING")
    over, under, mixed = category(db_session, "Eten"), category(db_session, "Uitjes"), category(db_session, "Auto")
    budgeted_history(db_session, over, checking, 100, ("150", "152", "148"))
    budgeted_history(db_session, under, checking, 200, ("100", "110", "90"))
    budgeted_history(db_session, mixed, checking, 100, ("150", "50", "150"))

    found = gripr_budget_service.budget_attention(db_session, TODAY)

    assert [(a.category.name, a.kind) for a in found] == [("Eten", "over_streak"), ("Uitjes", "under_streak")]
    assert found[0].average_spent == Decimal(150) and found[0].suggested_budget == Decimal(150)
    assert found[1].average_spent == Decimal(100) and found[1].suggested_budget == Decimal(100)
    assert all(a.periods == 3 for a in found)


def test_without_a_budget_in_every_period_nothing_is_flagged(db_session):
    checking = account(db_session, "ING")
    food = category(db_session, "Eten")
    gripr_budget_service.set_budget(db_session, food.id, PERIOD_START, Decimal(100))
    gripr_budget_service.set_budget(db_session, food.id, past_start(1), Decimal(100))
    for ago in (1, 2, 3):
        txn(db_session, past_start(ago), T.EXPENSE, "300", checking, food)

    assert gripr_budget_service.budget_attention(db_session, TODAY) == []


# -- against the usual -------------------------------------------------------------------------


def test_spending_by_category_compares_each_category_with_its_average_before(db_session):
    checking = account(db_session, "ING")
    food = category(db_session, "Boodschappen")
    sub = GriprCategory(name="Markt", kind=GriprCategoryKind.EXPENSE, parent_id=food.id)
    new = category(db_session, "Nieuw")
    db_session.add(sub)
    db_session.flush()
    for ago, amount in ((1, "100"), (2, "100"), (3, "100")):
        txn(db_session, past_start(ago), T.EXPENSE, amount, checking, food)
    txn(db_session, PERIOD_START, T.EXPENSE, "90", checking, food)
    txn(db_session, PERIOD_START, T.EXPENSE, "28", checking, sub)  # rolls up: 118 this period
    txn(db_session, PERIOD_START, T.EXPENSE, "40", checking, new)

    # A finished period: compared with the whole of the periods before.
    rows = {r.name: r for r in gripr_overview_service.spending_by_category(db_session, TODAY, today=PERIOD_END + timedelta(days=1))}

    assert rows["Boodschappen"].average == Decimal(100)
    assert rows["Boodschappen"].change_pct == Decimal(18)
    assert rows["Nieuw"].average is None and rows["Nieuw"].change_pct is None  # nothing to compare with


def test_a_category_dialog_comparison_counts_the_periods_without_spending_as_zero(db_session):
    checking = account(db_session, "ING")
    fun = category(db_session, "Uitjes")
    txn(db_session, past_start(1), T.EXPENSE, "90", checking, fun)
    txn(db_session, PERIOD_START, T.EXPENSE, "15", checking, fun)

    c = gripr_overview_service.category_comparison(db_session, fun.id, TODAY, today=PERIOD_END + timedelta(days=1))

    assert (c.spent, c.average, c.change_pct, c.periods, c.so_far) == (Decimal(15), Decimal(30), Decimal(-50), 3, False)


def test_a_running_period_is_compared_with_the_same_point_in_the_periods_before(db_session):
    checking = account(db_session, "ING")
    food = category(db_session, "Boodschappen")
    for ago in (1, 2, 3):
        txn(db_session, past_start(ago) + timedelta(days=2), T.EXPENSE, "100", checking, food)  # early in the period
        txn(db_session, past_start(ago) + timedelta(days=20), T.EXPENSE, "300", checking, food)  # later on
    txn(db_session, PERIOD_START + timedelta(days=1), T.EXPENSE, "110", checking, food)
    five_days_in = PERIOD_START + timedelta(days=5)

    c = gripr_overview_service.category_comparison(db_session, food.id, five_days_in, today=five_days_in)
    rows = {r.name: r for r in gripr_overview_service.spending_by_category(db_session, five_days_in, today=five_days_in)}

    # Five days in, the earlier periods had spent 100 each -- not their full 400.
    assert (c.average, c.change_pct, c.so_far) == (Decimal(100), Decimal(10), True)
    assert rows["Boodschappen"].average == Decimal(100)
