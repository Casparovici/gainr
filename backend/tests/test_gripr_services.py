from datetime import date, timedelta
from decimal import Decimal

from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_recurring import GriprRecurrenceFrequency, GriprRecurringTransaction
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.repositories import (
    gripr_account_repo,
    gripr_budget_repo,
    gripr_category_repo,
    gripr_recurring_repo,
    gripr_transaction_repo,
)
from app.services import (
    gripr_account_service,
    gripr_budget_service,
    gripr_category_service,
    gripr_overview_service,
    gripr_recurring_service,
)


def make_account(db, name, type_=GriprAccountType.CHECKING, mode=GriprBalanceMode.TRANSACTIONAL, **kw) -> GriprAccount:
    account = GriprAccount(name=name, type=type_, balance_mode=mode, **kw)
    db.add(account)
    db.flush()
    return account


def make_category(db, name, kind=GriprCategoryKind.EXPENSE, parent_id=None, **kw) -> GriprCategory:
    category = GriprCategory(name=name, kind=kind, parent_id=parent_id, **kw)
    db.add(category)
    db.flush()
    return category


def make_recurring(
    db, name, start_date, account, amount="10", frequency=GriprRecurrenceFrequency.MONTHLY, **kw
) -> GriprRecurringTransaction:
    rule = GriprRecurringTransaction(
        name=name,
        type=kw.pop("type_", GriprTransactionType.EXPENSE),
        amount=Decimal(amount),
        account_id=account.id,
        frequency=frequency,
        start_date=start_date,
        next_due_date=kw.pop("next_due_date", start_date),
        **kw,
    )
    db.add(rule)
    db.flush()
    return rule


def make_txn(db, d, type_, amount, account, counter_account=None, category=None) -> GriprTransaction:
    txn = GriprTransaction(
        date=d,
        type=type_,
        amount=Decimal(amount),
        account_id=account.id,
        counter_account_id=counter_account.id if counter_account else None,
        category_id=category.id if category else None,
    )
    db.add(txn)
    db.flush()
    return txn


# -- account balances ------------------------------------------------------------------------


def test_transactional_balance_is_opening_balance_plus_ledger(db_session):
    checking = make_account(db_session, "ING", opening_balance=Decimal(100))
    groceries = make_category(db_session, "Boodschappen")
    make_txn(db_session, date(2026, 1, 5), GriprTransactionType.INCOME, "500", checking, category=groceries)
    make_txn(db_session, date(2026, 1, 10), GriprTransactionType.EXPENSE, "80", checking, category=groceries)

    balance = gripr_account_service.compute_balance(db_session, checking)

    assert balance == Decimal(520)  # 100 + 500 - 80


def test_transfer_moves_balance_between_both_accounts(db_session):
    checking = make_account(db_session, "ING")
    savings = make_account(db_session, "ING Spaarrekening", type_=GriprAccountType.SAVINGS)
    make_txn(db_session, date(2026, 1, 1), GriprTransactionType.INCOME, "1000", checking)
    make_txn(db_session, date(2026, 1, 2), GriprTransactionType.TRANSFER, "300", checking, counter_account=savings)

    assert gripr_account_service.compute_balance(db_session, checking) == Decimal(700)
    assert gripr_account_service.compute_balance(db_session, savings) == Decimal(300)


def test_manual_balance_mode_ignores_the_ledger_entirely(db_session):
    mortgage = make_account(
        db_session, "Hypotheek", type_=GriprAccountType.LOAN, mode=GriprBalanceMode.MANUAL, manual_balance=Decimal(-400000)
    )
    # Even if something accidentally posted a transaction against it, a manual account's
    # balance is the number on the account, full stop.
    make_txn(db_session, date(2026, 1, 1), GriprTransactionType.EXPENSE, "1000", mortgage)

    assert gripr_account_service.compute_balance(db_session, mortgage) == Decimal(-400000)


def test_net_worth_sums_every_non_archived_account(db_session):
    make_account(db_session, "ING", opening_balance=Decimal(100))
    make_account(db_session, "Hypotheek", type_=GriprAccountType.LOAN, mode=GriprBalanceMode.MANUAL, manual_balance=Decimal(-1000))
    make_account(db_session, "Old bank", opening_balance=Decimal(9999), is_archived=True)

    assert gripr_account_service.net_worth(db_session) == Decimal(-900)  # 100 + -1000, archived excluded


def test_a_future_dated_transaction_does_not_count_toward_the_balance_yet(db_session):
    checking = make_account(db_session, "ING", opening_balance=Decimal(100))
    make_txn(db_session, date.today(), GriprTransactionType.INCOME, "500", checking)
    future = make_txn(db_session, date.today() + timedelta(days=1), GriprTransactionType.EXPENSE, "80", checking)

    assert gripr_account_service.compute_balance(db_session, checking) == Decimal(600)  # 100 + 500, expense not yet due

    # Once its date arrives it counts like any other transaction -- nothing special persisted
    # on the row itself, this is purely "as of today" on every read.
    future.date = date.today()
    db_session.flush()
    assert gripr_account_service.compute_balance(db_session, checking) == Decimal(520)


# -- budgets ------------------------------------------------------------------------------


def test_budget_status_rolls_subcategory_spend_up_to_the_parent(db_session):
    checking = make_account(db_session, "ING")
    food = make_category(db_session, "Eten & Drinken")
    bars = make_category(db_session, "Eten & Drinken (Bars)", parent_id=food.id)
    make_txn(db_session, date(2026, 3, 5), GriprTransactionType.EXPENSE, "40", checking, category=food)
    make_txn(db_session, date(2026, 3, 12), GriprTransactionType.EXPENSE, "25", checking, category=bars)
    # Outside the queried month — must not be counted.
    make_txn(db_session, date(2026, 2, 20), GriprTransactionType.EXPENSE, "999", checking, category=bars)
    gripr_budget_service.set_budget(db_session, food.id, date(2026, 3, 1), Decimal(100))

    lines = gripr_budget_service.get_budget_status(db_session, date(2026, 3, 15))
    line = next(l for l in lines if l.category.id == food.id)

    assert line.budgeted == Decimal(100)
    assert line.spent == Decimal(65)  # 40 + 25, February excluded


def test_budget_status_covers_top_level_categories_of_either_kind_but_not_subcategories(db_session):
    make_category(db_session, "Salaris", kind=GriprCategoryKind.INCOME)
    food = make_category(db_session, "Eten & Drinken")
    make_category(db_session, "Eten & Drinken (Bars)", parent_id=food.id)

    lines = gripr_budget_service.get_budget_status(db_session, date(2026, 3, 1))

    assert {l.category.name for l in lines} == {"Eten & Drinken", "Salaris"}


def test_budget_status_sums_income_transactions_for_an_income_category(db_session):
    checking = make_account(db_session, "ING")
    salary = make_category(db_session, "Salaris", kind=GriprCategoryKind.INCOME)
    make_txn(db_session, date(2026, 3, 5), GriprTransactionType.INCOME, "3000", checking, category=salary)
    # An expense filed under an income category (unusual, but must not count as "received").
    make_txn(db_session, date(2026, 3, 6), GriprTransactionType.EXPENSE, "50", checking, category=salary)
    gripr_budget_service.set_budget(db_session, salary.id, date(2026, 3, 1), Decimal(3200))

    lines = gripr_budget_service.get_budget_status(db_session, date(2026, 3, 15))
    line = next(l for l in lines if l.category.id == salary.id)

    assert line.budgeted == Decimal(3200)
    assert line.spent == Decimal(3000)


def test_budget_status_excludes_a_future_dated_transaction(db_session):
    checking = make_account(db_session, "ING")
    food = make_category(db_session, "Eten & Drinken")
    make_txn(db_session, date.today(), GriprTransactionType.EXPENSE, "20", checking, category=food)
    make_txn(db_session, date.today() + timedelta(days=1), GriprTransactionType.EXPENSE, "999", checking, category=food)

    lines = gripr_budget_service.get_budget_status(db_session, date.today())
    line = next(l for l in lines if l.category.id == food.id)

    assert line.spent == Decimal(20)  # tomorrow's 999 hasn't happened yet


# -- budget suggestions -----------------------------------------------------------------------


def test_suggestions_previous_month_is_the_month_right_before(db_session):
    food = make_category(db_session, "Eten & Drinken")
    gripr_budget_service.set_budget(db_session, food.id, date(2026, 2, 1), Decimal(80))

    suggestions = gripr_budget_service.get_suggestions(db_session, date(2026, 3, 1))
    line = next(s for s in suggestions if s.category_id == food.id)

    assert line.previous_month == Decimal(80)


def test_suggestions_year_average_is_the_trailing_twelve_months_divided_by_twelve(db_session):
    food = make_category(db_session, "Eten & Drinken")
    gripr_budget_service.set_budget(db_session, food.id, date(2026, 1, 1), Decimal(120))
    gripr_budget_service.set_budget(db_session, food.id, date(2026, 2, 1), Decimal(60))
    # Outside the trailing-12-month window ending at February — must not count.
    gripr_budget_service.set_budget(db_session, food.id, date(2024, 12, 1), Decimal(999))

    suggestions = gripr_budget_service.get_suggestions(db_session, date(2026, 3, 1))
    line = next(s for s in suggestions if s.category_id == food.id)

    assert line.year_average == Decimal("15.00")  # (120 + 60) / 12


def test_suggestions_recurring_monthly_normalizes_by_frequency_and_rolls_up_subcategories(db_session):
    checking = make_account(db_session, "ING")
    transport = make_category(db_session, "Vervoer")
    fuel = make_category(db_session, "Vervoer (Brandstof)", parent_id=transport.id)
    make_recurring(db_session, "Car insurance", date(2026, 1, 1), checking, amount="120", frequency=GriprRecurrenceFrequency.YEARLY, category_id=transport.id)
    make_recurring(db_session, "Fuel", date(2026, 1, 1), checking, amount="20", frequency=GriprRecurrenceFrequency.MONTHLY, category_id=fuel.id)
    # Must not count: paused, and an income-type rule.
    make_recurring(db_session, "Paused", date(2026, 1, 1), checking, amount="999", is_active=False, category_id=transport.id)
    make_recurring(db_session, "Salary", date(2026, 1, 1), checking, amount="3000", type_=GriprTransactionType.INCOME, frequency=GriprRecurrenceFrequency.MONTHLY, category_id=transport.id)

    suggestions = gripr_budget_service.get_suggestions(db_session, date(2026, 3, 1))
    line = next(s for s in suggestions if s.category_id == transport.id)

    assert line.recurring_monthly == Decimal("30.00")  # 120/12 + 20


def test_suggestions_recurring_monthly_for_an_income_category_uses_income_type_rules(db_session):
    checking = make_account(db_session, "ING")
    salary = make_category(db_session, "Salaris", kind=GriprCategoryKind.INCOME)
    make_recurring(db_session, "Salary", date(2026, 1, 1), checking, amount="3000", type_=GriprTransactionType.INCOME, frequency=GriprRecurrenceFrequency.MONTHLY, category_id=salary.id)
    # An expense-type rule filed under the same category id must not count toward income.
    make_recurring(db_session, "Mistagged", date(2026, 1, 1), checking, amount="999", frequency=GriprRecurrenceFrequency.MONTHLY, category_id=salary.id)

    suggestions = gripr_budget_service.get_suggestions(db_session, date(2026, 3, 1))
    line = next(s for s in suggestions if s.category_id == salary.id)

    assert line.recurring_monthly == Decimal("3000.00")


def test_suggestions_are_zero_when_theres_no_history_at_all(db_session):
    food = make_category(db_session, "Eten & Drinken")

    suggestions = gripr_budget_service.get_suggestions(db_session, date(2026, 3, 1))
    line = next(s for s in suggestions if s.category_id == food.id)

    assert line.previous_month == 0
    assert line.year_average == 0
    assert line.recurring_monthly == 0


# -- savings goals ----------------------------------------------------------------------------


def test_savings_status_only_covers_savings_and_investment_accounts(db_session):
    make_account(db_session, "ING")
    make_account(db_session, "ING Spaarrekening", type_=GriprAccountType.SAVINGS)
    make_account(db_session, "DEGIRO", type_=GriprAccountType.INVESTMENT)
    make_account(db_session, "Hypotheek", type_=GriprAccountType.LOAN, mode=GriprBalanceMode.MANUAL)

    lines = gripr_budget_service.get_savings_status(db_session, date(2026, 3, 1))

    assert {l.account.name for l in lines} == {"ING Spaarrekening", "DEGIRO"}


def test_savings_status_saved_nets_inbound_transfers_against_outbound_in_the_period(db_session):
    checking = make_account(db_session, "ING")
    savings = make_account(db_session, "ING Spaarrekening", type_=GriprAccountType.SAVINGS)
    make_txn(db_session, date(2026, 3, 5), GriprTransactionType.TRANSFER, "500", checking, counter_account=savings)
    make_txn(db_session, date(2026, 3, 20), GriprTransactionType.TRANSFER, "150", savings, counter_account=checking)
    # Outside the queried month — must not be counted.
    make_txn(db_session, date(2026, 2, 1), GriprTransactionType.TRANSFER, "999", checking, counter_account=savings)
    gripr_budget_service.set_savings_goal(db_session, savings.id, date(2026, 3, 1), Decimal(400))

    lines = gripr_budget_service.get_savings_status(db_session, date(2026, 3, 15))
    line = next(l for l in lines if l.account.id == savings.id)

    assert line.budgeted == Decimal(400)
    assert line.saved == Decimal(350)  # 500 in - 150 back out, February excluded


def test_set_savings_goal_keys_on_the_periods_start_date_not_the_1st(db_session):
    from app.repositories import gripr_savings_goal_repo, gripr_settings_repo

    gripr_settings_repo.set_period_start_day(db_session, 25)
    savings = make_account(db_session, "ING Spaarrekening", type_=GriprAccountType.SAVINGS)

    gripr_budget_service.set_savings_goal(db_session, savings.id, date(2026, 9, 10), Decimal(400))

    # Sep 10 falls in the period that started Aug 25, not Sep 1.
    assert gripr_savings_goal_repo.get_goal(db_session, savings.id, date(2026, 8, 25)) is not None
    assert gripr_savings_goal_repo.get_goal(db_session, savings.id, date(2026, 9, 1)) is None


def test_savings_status_excludes_a_future_dated_transfer(db_session):
    checking = make_account(db_session, "ING")
    savings = make_account(db_session, "ING Spaarrekening", type_=GriprAccountType.SAVINGS)
    make_txn(db_session, date.today(), GriprTransactionType.TRANSFER, "100", checking, counter_account=savings)
    make_txn(db_session, date.today() + timedelta(days=1), GriprTransactionType.TRANSFER, "500", checking, counter_account=savings)

    lines = gripr_budget_service.get_savings_status(db_session, date.today())
    line = next(l for l in lines if l.account.id == savings.id)

    assert line.saved == Decimal(100)  # tomorrow's transfer hasn't landed yet


def test_savings_suggestions_previous_month_and_year_average(db_session):
    savings = make_account(db_session, "ING Spaarrekening", type_=GriprAccountType.SAVINGS)
    gripr_budget_service.set_savings_goal(db_session, savings.id, date(2026, 1, 1), Decimal(300))
    gripr_budget_service.set_savings_goal(db_session, savings.id, date(2026, 2, 1), Decimal(150))
    # Outside the trailing-12-month window ending at February — must not count.
    gripr_budget_service.set_savings_goal(db_session, savings.id, date(2024, 12, 1), Decimal(999))

    suggestions = gripr_budget_service.get_savings_suggestions(db_session, date(2026, 3, 1))
    line = next(s for s in suggestions if s.account_id == savings.id)

    assert line.previous_month == Decimal(150)
    assert line.year_average == Decimal("37.50")  # (300 + 150) / 12


def test_savings_suggestions_recurring_monthly_uses_transfer_rules_into_the_account(db_session):
    checking = make_account(db_session, "ING")
    savings = make_account(db_session, "ING Spaarrekening", type_=GriprAccountType.SAVINGS)
    make_recurring(
        db_session, "Auto-save", date(2026, 1, 1), checking, amount="200",
        frequency=GriprRecurrenceFrequency.MONTHLY, type_=GriprTransactionType.TRANSFER, counter_account_id=savings.id,
    )
    # Must not count: a transfer rule into a different account.
    other = make_account(db_session, "DEGIRO", type_=GriprAccountType.INVESTMENT)
    make_recurring(
        db_session, "Other transfer", date(2026, 1, 1), checking, amount="999",
        frequency=GriprRecurrenceFrequency.MONTHLY, type_=GriprTransactionType.TRANSFER, counter_account_id=other.id,
    )

    suggestions = gripr_budget_service.get_savings_suggestions(db_session, date(2026, 3, 1))
    line = next(s for s in suggestions if s.account_id == savings.id)

    assert line.recurring_monthly == Decimal("200.00")


# -- overview -------------------------------------------------------------------------------


def test_spending_by_category_rolls_up_and_sorts_descending(db_session):
    checking = make_account(db_session, "ING")
    food = make_category(db_session, "Eten & Drinken")
    bars = make_category(db_session, "Eten & Drinken (Bars)", parent_id=food.id)
    transport = make_category(db_session, "Vervoer")
    make_txn(db_session, date(2026, 4, 1), GriprTransactionType.EXPENSE, "10", checking, category=bars)
    make_txn(db_session, date(2026, 4, 2), GriprTransactionType.EXPENSE, "5", checking, category=food)
    make_txn(db_session, date(2026, 4, 3), GriprTransactionType.EXPENSE, "50", checking, category=transport)

    result = gripr_overview_service.spending_by_category(db_session, date(2026, 4, 15))

    assert [(c.name, c.amount) for c in result] == [("Vervoer", Decimal(50)), ("Eten & Drinken", Decimal(15))]


def test_income_vs_expense_covers_every_requested_month_even_when_empty(db_session):
    checking = make_account(db_session, "ING")
    make_txn(db_session, date(2026, 5, 10), GriprTransactionType.INCOME, "2000", checking)
    make_txn(db_session, date(2026, 5, 15), GriprTransactionType.EXPENSE, "300", checking)
    # April has no activity at all — it must still appear, as zeros, not be skipped.

    result = gripr_overview_service.income_vs_expense(db_session, months=2, as_of=date(2026, 5, 20))

    assert [r.month for r in result] == [date(2026, 4, 1), date(2026, 5, 1)]
    assert result[0].income == Decimal(0) and result[0].expense == Decimal(0)
    assert result[1].income == Decimal(2000) and result[1].expense == Decimal(300)


def test_spending_by_category_excludes_a_future_dated_transaction(db_session):
    checking = make_account(db_session, "ING")
    food = make_category(db_session, "Eten & Drinken")
    make_txn(db_session, date.today(), GriprTransactionType.EXPENSE, "10", checking, category=food)
    make_txn(db_session, date.today() + timedelta(days=1), GriprTransactionType.EXPENSE, "999", checking, category=food)

    result = gripr_overview_service.spending_by_category(db_session, date.today())

    assert [(c.name, c.amount) for c in result] == [("Eten & Drinken", Decimal(10))]


def test_income_vs_expense_excludes_a_future_dated_transaction(db_session):
    checking = make_account(db_session, "ING")
    make_txn(db_session, date.today(), GriprTransactionType.EXPENSE, "10", checking)
    make_txn(db_session, date.today() + timedelta(days=1), GriprTransactionType.EXPENSE, "999", checking)

    result = gripr_overview_service.income_vs_expense(db_session, months=1, as_of=date.today())

    assert result[0].expense == Decimal(10)


def test_category_trend_rolls_up_subcategories_per_month(db_session):
    checking = make_account(db_session, "ING")
    food = make_category(db_session, "Eten & Drinken")
    bars = make_category(db_session, "Eten & Drinken (Bars)", parent_id=food.id)
    transport = make_category(db_session, "Vervoer")
    make_txn(db_session, date(2026, 4, 1), GriprTransactionType.EXPENSE, "10", checking, category=bars)
    make_txn(db_session, date(2026, 4, 2), GriprTransactionType.EXPENSE, "5", checking, category=food)
    make_txn(db_session, date(2026, 4, 3), GriprTransactionType.EXPENSE, "50", checking, category=transport)
    # April has no transport activity — it must still appear as a zero, not be skipped.

    result = gripr_overview_service.category_trend(db_session, food.id, months=2, as_of=date(2026, 4, 15))

    assert [r.month for r in result] == [date(2026, 3, 1), date(2026, 4, 1)]
    assert result[0].amount == Decimal(0)
    assert result[1].amount == Decimal(15)


def test_category_trend_excludes_a_future_dated_transaction(db_session):
    checking = make_account(db_session, "ING")
    food = make_category(db_session, "Eten & Drinken")
    make_txn(db_session, date.today(), GriprTransactionType.EXPENSE, "10", checking, category=food)
    make_txn(db_session, date.today() + timedelta(days=1), GriprTransactionType.EXPENSE, "999", checking, category=food)

    result = gripr_overview_service.category_trend(db_session, food.id, months=1, as_of=date.today())

    assert result[0].amount == Decimal(10)


# -- custom period boundary -------------------------------------------------------------------


def test_budget_status_respects_a_configured_period_start_day(db_session):
    from app.repositories import gripr_settings_repo

    gripr_settings_repo.set_period_start_day(db_session, 25)
    checking = make_account(db_session, "ING")
    food = make_category(db_session, "Eten & Drinken")
    # In the period starting 2026-08-25 (which runs through 2026-09-24).
    make_txn(db_session, date(2026, 9, 1), GriprTransactionType.EXPENSE, "40", checking, category=food)
    # In the *next* period (starts 2026-09-25) -- must not count.
    make_txn(db_session, date(2026, 9, 25), GriprTransactionType.EXPENSE, "999", checking, category=food)
    gripr_budget_service.set_budget(db_session, food.id, date(2026, 9, 1), Decimal(100))

    lines = gripr_budget_service.get_budget_status(db_session, date(2026, 9, 1))
    line = next(l for l in lines if l.category.id == food.id)

    assert line.spent == Decimal(40)


def test_set_budget_keys_on_the_periods_start_date_not_the_1st(db_session):
    from app.repositories import gripr_budget_repo, gripr_settings_repo

    gripr_settings_repo.set_period_start_day(db_session, 25)
    food = make_category(db_session, "Eten & Drinken")

    gripr_budget_service.set_budget(db_session, food.id, date(2026, 9, 10), Decimal(100))

    # 2026-09-10 falls in the period that started 2026-08-25, so that's the stored key.
    assert gripr_budget_repo.get_budget(db_session, food.id, date(2026, 8, 25)) is not None
    assert gripr_budget_repo.get_budget(db_session, food.id, date(2026, 9, 1)) is None


def test_suggestions_previous_period_shift_works_for_a_custom_start_day(db_session):
    from app.repositories import gripr_settings_repo

    gripr_settings_repo.set_period_start_day(db_session, 25)
    food = make_category(db_session, "Eten & Drinken")
    # The period immediately before the one starting 2026-08-25 starts 2026-07-25.
    gripr_budget_service.set_budget(db_session, food.id, date(2026, 7, 30), Decimal(80))

    suggestions = gripr_budget_service.get_suggestions(db_session, date(2026, 9, 1))
    line = next(s for s in suggestions if s.category_id == food.id)

    assert line.previous_month == Decimal(80)


def test_income_vs_expense_periods_are_anchored_to_the_custom_start_day(db_session):
    from app.repositories import gripr_settings_repo

    gripr_settings_repo.set_period_start_day(db_session, 25)
    checking = make_account(db_session, "ING")
    make_txn(db_session, date(2026, 9, 1), GriprTransactionType.INCOME, "500", checking)

    result = gripr_overview_service.income_vs_expense(db_session, months=2, as_of=date(2026, 9, 10))

    assert [r.month for r in result] == [date(2026, 7, 25), date(2026, 8, 25)]
    assert result[1].income == Decimal(500)  # 2026-09-01 falls in the period starting 08-25


# -- account ordering -------------------------------------------------------------------------


def test_list_accounts_orders_by_sort_order_within_each_type(db_session):
    checking_b = make_account(db_session, "B Checking", sort_order=1)
    checking_a = make_account(db_session, "A Checking", sort_order=0)
    savings = make_account(db_session, "Savings", type_=GriprAccountType.SAVINGS, sort_order=0)

    result = gripr_account_repo.list_accounts(db_session)

    assert [a.id for a in result] == [checking_a.id, checking_b.id, savings.id]


def test_next_sort_order_appends_after_the_current_max_within_the_type(db_session):
    make_account(db_session, "First", sort_order=0)
    make_account(db_session, "Second", sort_order=3)
    make_account(db_session, "Other type", type_=GriprAccountType.SAVINGS, sort_order=9)

    assert gripr_account_repo.next_sort_order(db_session, GriprAccountType.CHECKING) == 4
    assert gripr_account_repo.next_sort_order(db_session, GriprAccountType.INVESTMENT) == 1


def test_reorder_assigns_positions_in_the_given_order(db_session):
    first = make_account(db_session, "First", sort_order=0)
    second = make_account(db_session, "Second", sort_order=1)
    third = make_account(db_session, "Third", sort_order=2)

    gripr_account_repo.reorder(db_session, [third.id, first.id, second.id])

    result = gripr_account_repo.list_accounts(db_session)
    assert [a.id for a in result] == [third.id, first.id, second.id]


def test_category_reorder_and_color_override(db_session):
    first = make_category(db_session, "First")
    second = make_category(db_session, "Second")
    third = make_category(db_session, "Third")

    gripr_category_repo.reorder(db_session, [third.id, first.id, second.id])
    result = gripr_category_repo.list_categories(db_session)
    assert [c.id for c in result] == [third.id, first.id, second.id]

    gripr_category_repo.update_category(db_session, first, color="#2a78d6")
    assert first.color == "#2a78d6"


def test_category_color_can_be_reset_to_the_derived_default(db_session):
    category = make_category(db_session, "First", color="#2a78d6")

    gripr_category_repo.update_category(db_session, category, color=None)

    assert category.color is None


def test_account_color_can_be_set_and_reset_to_the_derived_default(db_session):
    account = make_account(db_session, "ING")

    gripr_account_repo.update_account(db_session, account, color="#eb6834")
    assert account.color == "#eb6834"

    gripr_account_repo.update_account(db_session, account, color=None)
    assert account.color is None


def test_category_next_sort_order_is_scoped_to_top_level_and_kind(db_session):
    make_category(db_session, "Expense A", sort_order=0)
    parent = make_category(db_session, "Expense B", sort_order=1)
    make_category(db_session, "Sub of B", parent_id=parent.id, sort_order=99)
    make_category(db_session, "Income A", kind=GriprCategoryKind.INCOME, sort_order=5)

    assert gripr_category_repo.next_sort_order(db_session, GriprCategoryKind.EXPENSE) == 2
    assert gripr_category_repo.next_sort_order(db_session, GriprCategoryKind.INCOME) == 6


# -- category archive/delete -------------------------------------------------------------------


def test_set_archived_on_a_top_level_category_cascades_to_its_subcategories(db_session):
    food = make_category(db_session, "Eten & Drinken")
    bars = make_category(db_session, "Eten & Drinken (Bars)", parent_id=food.id)

    gripr_category_service.set_archived(db_session, food, True)

    assert food.is_archived is True
    assert bars.is_archived is True


def test_set_archived_unarchiving_a_parent_does_not_restore_children(db_session):
    food = make_category(db_session, "Eten & Drinken")
    bars = make_category(db_session, "Eten & Drinken (Bars)", parent_id=food.id, is_archived=True)
    gripr_category_service.set_archived(db_session, food, True)

    gripr_category_service.set_archived(db_session, food, False)

    assert food.is_archived is False
    assert bars.is_archived is True  # stays archived — never told to come back


def test_delete_category_untags_its_transactions_instead_of_deleting_them(db_session):
    checking = make_account(db_session, "ING")
    groceries = make_category(db_session, "Boodschappen")
    txn = make_txn(db_session, date(2026, 1, 5), GriprTransactionType.EXPENSE, "12.50", checking, category=groceries)

    gripr_category_service.delete_category(db_session, groceries)

    assert gripr_category_repo.get_category(db_session, groceries.id) is None
    assert txn.category_id is None  # the transaction itself survives, just un-tagged


def test_delete_top_level_category_cascades_to_subcategories_and_their_transactions(db_session):
    checking = make_account(db_session, "ING")
    food = make_category(db_session, "Eten & Drinken")
    bars = make_category(db_session, "Eten & Drinken (Bars)", parent_id=food.id)
    bars_txn = make_txn(db_session, date(2026, 1, 1), GriprTransactionType.EXPENSE, "20", checking, category=bars)

    gripr_category_service.delete_category(db_session, food)

    assert gripr_category_repo.get_category(db_session, food.id) is None
    assert gripr_category_repo.get_category(db_session, bars.id) is None
    assert bars_txn.category_id is None


def test_delete_subcategory_leaves_its_parent_and_siblings_alone(db_session):
    food = make_category(db_session, "Eten & Drinken")
    bars = make_category(db_session, "Eten & Drinken (Bars)", parent_id=food.id)
    snacks = make_category(db_session, "Eten & Drinken (Snacks)", parent_id=food.id)

    gripr_category_service.delete_category(db_session, bars)

    assert gripr_category_repo.get_category(db_session, food.id) is not None
    assert gripr_category_repo.get_category(db_session, bars.id) is None
    assert gripr_category_repo.get_category(db_session, snacks.id) is not None


def test_delete_category_also_removes_its_budget_lines(db_session):
    food = make_category(db_session, "Eten & Drinken")
    gripr_budget_service.set_budget(db_session, food.id, date(2026, 3, 1), Decimal(200))

    gripr_category_service.delete_category(db_session, food)

    assert gripr_budget_repo.list_budgets_for_month(db_session, date(2026, 3, 1)) == []


# -- transaction listing ----------------------------------------------------------------------


def test_usage_counts_counts_both_sides_of_a_transfer(db_session):
    checking = make_account(db_session, "ING")
    savings = make_account(db_session, "Spaarrekening", type_=GriprAccountType.SAVINGS)
    unused = make_account(db_session, "Unused", type_=GriprAccountType.SAVINGS)
    make_txn(db_session, date(2026, 1, 1), GriprTransactionType.INCOME, "100", checking)
    make_txn(db_session, date(2026, 1, 2), GriprTransactionType.TRANSFER, "50", checking, counter_account=savings)

    counts = gripr_transaction_repo.usage_counts(db_session)

    assert counts[checking.id] == 2  # the income, plus the transfer's paying side
    assert counts[savings.id] == 1  # the transfer's receiving side
    assert unused.id not in counts


def test_list_transactions_filters_by_amount_range(db_session):
    checking = make_account(db_session, "ING")
    make_txn(db_session, date(2026, 1, 1), GriprTransactionType.EXPENSE, "5", checking)
    make_txn(db_session, date(2026, 1, 2), GriprTransactionType.EXPENSE, "50", checking)
    make_txn(db_session, date(2026, 1, 3), GriprTransactionType.EXPENSE, "500", checking)

    items, total = gripr_transaction_repo.list_transactions(
        db_session, amount_min=Decimal(10), amount_max=Decimal(100)
    )

    assert total == 1
    assert items[0].amount == Decimal(50)


def test_list_transactions_category_filter_rolls_up_subcategories(db_session):
    checking = make_account(db_session, "ING")
    food = make_category(db_session, "Eten & Drinken")
    bars = make_category(db_session, "Eten & Drinken (Bars)", parent_id=food.id)
    transport = make_category(db_session, "Vervoer")
    make_txn(db_session, date(2026, 1, 1), GriprTransactionType.EXPENSE, "10", checking, category=food)
    make_txn(db_session, date(2026, 1, 2), GriprTransactionType.EXPENSE, "20", checking, category=bars)
    make_txn(db_session, date(2026, 1, 3), GriprTransactionType.EXPENSE, "30", checking, category=transport)

    category_ids = gripr_category_repo.descendant_ids(db_session, food.id)
    items, total = gripr_transaction_repo.list_transactions(db_session, category_ids=category_ids)

    assert total == 2
    assert {i.amount for i in items} == {Decimal(10), Decimal(20)}


# -- recurring transactions -------------------------------------------------------------------


def test_advance_steps_by_one_period_per_frequency():
    assert gripr_recurring_service.advance(GriprRecurrenceFrequency.WEEKLY, date(2026, 1, 5)) == date(2026, 1, 12)
    assert gripr_recurring_service.advance(GriprRecurrenceFrequency.MONTHLY, date(2026, 1, 31)) == date(2026, 2, 28)
    assert gripr_recurring_service.advance(GriprRecurrenceFrequency.YEARLY, date(2024, 2, 29)) == date(2025, 2, 28)


def test_generate_due_books_a_transaction_and_advances_next_due_date(db_session):
    checking = make_account(db_session, "ING")
    netflix = make_recurring(db_session, "Netflix", date(2026, 1, 14), checking, amount="15.99")

    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 1, 14))

    # Just the due Jan 14 occurrence -- Feb 14 is a month out, well past the 2-day pre-book
    # horizon, so it isn't booked yet (see test_generate_due_pre_books_within_the_horizon).
    assert len(created) == 1
    assert created[0].amount == Decimal("15.99")
    assert created[0].date == date(2026, 1, 14)
    assert created[0].source_ref == f"pefi_recurring:{netflix.id}:2026-01-14"
    assert netflix.next_due_date == date(2026, 2, 14)


def test_advance_steps_by_the_given_interval():
    assert gripr_recurring_service.advance(GriprRecurrenceFrequency.WEEKLY, date(2026, 1, 5), interval=2) == date(2026, 1, 19)
    assert gripr_recurring_service.advance(GriprRecurrenceFrequency.MONTHLY, date(2026, 1, 31), interval=3) == date(2026, 4, 30)
    # interval=1 (the default) must behave exactly like before this feature existed.
    assert gripr_recurring_service.advance(GriprRecurrenceFrequency.WEEKLY, date(2026, 1, 5)) == date(2026, 1, 12)


def test_generate_due_respects_a_bi_weekly_rules_interval_when_catching_up(db_session):
    checking = make_account(db_session, "ING")
    make_recurring(
        db_session, "Bi-weekly allowance", date(2026, 1, 5), checking,
        frequency=GriprRecurrenceFrequency.WEEKLY, interval=2,
    )

    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 2, 20))

    # Mar 2 is well past the 2-day pre-book horizon from Feb 20, so it isn't booked yet.
    assert [t.date for t in created] == [
        date(2026, 1, 5), date(2026, 1, 19), date(2026, 2, 2), date(2026, 2, 16),
    ]


def test_generate_due_catches_up_every_missed_occurrence(db_session):
    checking = make_account(db_session, "ING")
    make_recurring(db_session, "Netflix", date(2026, 1, 14), checking, frequency=GriprRecurrenceFrequency.MONTHLY)

    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 4, 20))

    # May 14 is well past the 2-day pre-book horizon from Apr 20, so it isn't booked yet.
    assert [t.date for t in created] == [
        date(2026, 1, 14), date(2026, 2, 14), date(2026, 3, 14), date(2026, 4, 14),
    ]


def test_generate_due_caps_one_rules_catchup_per_pass_without_losing_occurrences(db_session):
    """A mistyped anchor year shouldn't book a decade of transactions inside one page load.
    The cap only defers the remainder — next_due_date stays put, so a second pass continues
    exactly where the first stopped."""
    checking = make_account(db_session, "ING")
    make_recurring(db_session, "Netflix", date(2000, 1, 14), checking, frequency=GriprRecurrenceFrequency.MONTHLY)

    first = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 4, 20))
    second = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 4, 20))

    assert len(first) == gripr_recurring_service.MAX_CATCHUP_PER_RULE
    assert first[0].date == date(2000, 1, 14)
    # Picks up on the very next occurrence rather than skipping or repeating one.
    assert second[0].date == date(2010, 1, 14)


def test_resuming_a_paused_rule_skips_the_pause_instead_of_backfilling_it(db_session):
    """Pausing means those occurrences didn't happen — resuming a rule paused for months
    shouldn't book every month it was off as if you'd been charged."""
    checking = make_account(db_session, "ING")
    rule = make_recurring(db_session, "Netflix", date(2026, 1, 14), checking, frequency=GriprRecurrenceFrequency.MONTHLY)
    gripr_recurring_service.update_recurring(db_session, rule, as_of=date(2026, 1, 20), is_active=False)

    gripr_recurring_service.update_recurring(db_session, rule, as_of=date(2026, 6, 20), is_active=True)
    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 6, 20))

    # Keeps the rule's own 14th-of-the-month rhythm rather than restarting from the resume date.
    assert rule.next_due_date == date(2026, 7, 14)
    # Jul 14 is well past the 2-day pre-book horizon from the Jun 20 resume date.
    assert created == []


def test_resuming_leaves_a_rule_that_never_came_due_on_its_original_date(db_session):
    checking = make_account(db_session, "ING")
    rule = make_recurring(db_session, "Netflix", date(2026, 8, 14), checking, frequency=GriprRecurrenceFrequency.MONTHLY)
    gripr_recurring_service.update_recurring(db_session, rule, as_of=date(2026, 6, 20), is_active=False)

    gripr_recurring_service.update_recurring(db_session, rule, as_of=date(2026, 6, 21), is_active=True)

    assert rule.next_due_date == date(2026, 8, 14)


def test_generate_due_ignores_a_paused_rule_entirely(db_session):
    checking = make_account(db_session, "ING")
    make_recurring(db_session, "Paused", date(2026, 1, 1), checking, is_active=False)

    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 3, 1))

    assert created == []


def test_generate_due_does_not_pre_book_a_rule_far_outside_the_horizon(db_session):
    """An active rule with nothing due for months shouldn't clutter Transactions with an
    occurrence dated a month out -- pre-booking only kicks in once it's within
    PREBOOK_HORIZON_DAYS of its own due date (see the next test)."""
    checking = make_account(db_session, "ING")
    make_recurring(db_session, "Future", date(2026, 6, 1), checking)

    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 3, 1))

    assert created == []


def test_generate_due_pre_books_a_rule_within_the_horizon(db_session):
    """The whole point of pre-booking: once an active rule's next occurrence is within
    PREBOOK_HORIZON_DAYS, it shows up in the Transactions list, editable, ahead of time -- it
    just doesn't count toward any balance/budget/overview total until its own date arrives (see
    gripr_transaction_repo's `date <= today` cutoff)."""
    checking = make_account(db_session, "ING")
    rule = make_recurring(db_session, "Upcoming", date(2026, 6, 1), checking, amount="42")

    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 5, 30))  # 2 days out

    assert [t.date for t in created] == [date(2026, 6, 1)]
    assert created[0].amount == Decimal(42)
    # Not advanced -- "next due" still names the same date as the pre-booked row.
    assert rule.next_due_date == date(2026, 6, 1)


def test_generate_due_pre_books_only_once_across_repeated_calls(db_session):
    checking = make_account(db_session, "ING")
    make_recurring(db_session, "Upcoming", date(2026, 6, 1), checking)

    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 5, 30))
    second = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 5, 31))

    assert second == []


def test_generate_due_stops_pre_booking_once_the_horizon_is_passed(db_session):
    """A rule due in exactly 3 days is outside the 2-day window -- confirms the boundary is
    exclusive on the far side, not just "eventually gets pre-booked no matter how far off"."""
    checking = make_account(db_session, "ING")
    make_recurring(db_session, "Too far", date(2026, 6, 4), checking)

    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 6, 1))

    assert created == []


def test_a_pre_booked_loan_linked_occurrence_does_not_move_the_loan_balance_until_due(db_session):
    """A repayment dated next month hasn't happened yet -- pre-booking it early (so it's visible
    and editable ahead of time) must not touch the loan balance until its own date arrives."""
    checking = make_account(db_session, "ING")
    loan = make_account(db_session, "Studieschuld", type_=GriprAccountType.LOAN, mode=GriprBalanceMode.MANUAL, manual_balance=Decimal("-10000"))
    category = make_category(db_session, "Studieschuld", linked_loan_account_id=loan.id)
    make_recurring(db_session, "Loan payment", date(2026, 6, 1), checking, amount="200", category_id=category.id)

    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 5, 30))  # 2 days out

    assert [t.date for t in created] == [date(2026, 6, 1)]
    assert loan.manual_balance == Decimal("-10000")  # pre-booked, but not due yet -- untouched

    # Its date has now arrived: generate_due's catch-up pass finds it already in the ledger and
    # applies the deferred effect now, exactly once. Next month's occurrence (Jul 1) is a month
    # out, well past the pre-book horizon, so nothing new is created yet.
    caught_up = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 6, 1))

    assert loan.manual_balance == Decimal("-9800")
    assert caught_up == []

    # Calling again the same day must not double-apply the now-due June effect.
    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 6, 1))
    assert loan.manual_balance == Decimal("-9800")


def test_pausing_a_rule_removes_its_pre_booked_future_occurrence(db_session):
    checking = make_account(db_session, "ING")
    rule = make_recurring(db_session, "Netflix", date(2026, 6, 1), checking, amount="15.99")
    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 5, 30))  # pre-books Jun 1
    assert gripr_transaction_repo.list_transactions(db_session)[1] == 1

    gripr_recurring_service.update_recurring(db_session, rule, as_of=date(2026, 5, 31), is_active=False)

    # The not-yet-happened Jun 1 charge is gone -- pausing means it won't occur.
    assert gripr_transaction_repo.list_transactions(db_session)[1] == 0


def test_pausing_a_rule_leaves_an_already_due_occurrence_alone(db_session):
    checking = make_account(db_session, "ING")
    rule = make_recurring(db_session, "Netflix", date(2026, 1, 14), checking, amount="15.99")
    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 1, 14))  # books Jan 14 for real
    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 2, 12))  # pre-books Feb 14, 2 days out

    gripr_recurring_service.update_recurring(db_session, rule, as_of=date(2026, 2, 13), is_active=False)

    # Jan 14 already happened -- pausing must not retroactively remove it, only the Feb 14
    # occurrence that was pre-booked ahead of its own due date (not yet due, so it goes).
    items, total = gripr_transaction_repo.list_transactions(db_session)
    assert total == 1
    assert items[0].date == date(2026, 1, 14)


def test_generate_due_deactivates_a_rule_once_it_passes_its_end_date(db_session):
    checking = make_account(db_session, "ING")
    rule = make_recurring(
        db_session, "Short gym membership", date(2026, 1, 1), checking, end_date=date(2026, 2, 1)
    )

    created = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 6, 1))

    assert [t.date for t in created] == [date(2026, 1, 1), date(2026, 2, 1)]
    assert rule.is_active is False


def test_generate_due_is_idempotent_when_called_again_before_the_next_period(db_session):
    checking = make_account(db_session, "ING")
    make_recurring(db_session, "Netflix", date(2026, 1, 14), checking)

    first = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 1, 20))
    second = gripr_recurring_service.generate_due(db_session, as_of=date(2026, 1, 20))

    # Feb 14 is nearly a month out from Jan 20 -- well past the 2-day pre-book horizon, so only
    # the due Jan 14 occurrence is booked.
    assert len(first) == 1
    assert second == []


def test_update_recurring_moving_start_date_resets_next_due_date(db_session):
    checking = make_account(db_session, "ING")
    rule = make_recurring(db_session, "Netflix", date(2026, 1, 14), checking)
    # Already caught up past January before the schedule gets pushed out.
    rule.next_due_date = date(2026, 3, 14)

    gripr_recurring_service.update_recurring(db_session, rule, start_date=date(2026, 5, 1))

    assert rule.start_date == date(2026, 5, 1)
    assert rule.next_due_date == date(2026, 5, 1)


def test_list_recurring_orders_by_next_due_date(db_session):
    checking = make_account(db_session, "ING")
    make_recurring(db_session, "Later", date(2026, 3, 1), checking)
    make_recurring(db_session, "Sooner", date(2026, 1, 1), checking)

    result = gripr_recurring_repo.list_recurring(db_session)

    assert [r.name for r in result] == ["Sooner", "Later"]


# -- settings router ----------------------------------------------------------------------------


def test_settings_default_to_calendar_month(db_session):
    from app.db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import gripr as gripr_router

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    assert client.get("/api/gripr/settings").json() == {"period_start_day": 1}


def test_updating_settings_persists_and_is_reflected_on_read(db_session):
    from app.db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import gripr as gripr_router

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.put("/api/gripr/settings", json={"period_start_day": 25})
    assert response.status_code == 200
    assert response.json() == {"period_start_day": 25}
    assert client.get("/api/gripr/settings").json() == {"period_start_day": 25}


def test_settings_out_of_range_period_start_day_is_rejected(db_session):
    from app.db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import gripr as gripr_router

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    assert client.put("/api/gripr/settings", json={"period_start_day": 0}).status_code == 422
    assert client.put("/api/gripr/settings", json={"period_start_day": 29}).status_code == 422


# -- linked loan account -----------------------------------------------------------------------


def test_linking_a_category_to_a_loan_account_through_the_router_persists_it(db_session):
    from app.db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import gripr as gripr_router

    loan = make_account(db_session, "Studieschuld", type_=GriprAccountType.LOAN, mode=GriprBalanceMode.MANUAL)
    category = make_category(db_session, "Studieschuld")
    db_session.commit()

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.put(f"/api/gripr/categories/{category.id}", json={"linked_loan_account_id": loan.id})

    assert response.status_code == 200
    assert response.json()["linked_loan_account_id"] == loan.id


def test_linking_a_category_to_a_non_loan_account_is_rejected(db_session):
    from app.db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import gripr as gripr_router

    checking = make_account(db_session, "ING")
    category = make_category(db_session, "Boodschappen")
    db_session.commit()

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.put(f"/api/gripr/categories/{category.id}", json={"linked_loan_account_id": checking.id})

    assert response.status_code == 400


def test_linking_an_income_category_to_a_loan_account_is_rejected(db_session):
    from app.db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import gripr as gripr_router

    loan = make_account(db_session, "Studieschuld", type_=GriprAccountType.LOAN, mode=GriprBalanceMode.MANUAL)
    salary = make_category(db_session, "Salaris", kind=GriprCategoryKind.INCOME)
    db_session.commit()

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.put(f"/api/gripr/categories/{salary.id}", json={"linked_loan_account_id": loan.id})

    assert response.status_code == 400


# -- is_recurring flag --------------------------------------------------------------------------


def test_transaction_out_flags_a_rule_generated_transaction_as_recurring(db_session):
    from app.db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import gripr as gripr_router

    checking = make_account(db_session, "ING")
    make_recurring(db_session, "Netflix", date(2026, 1, 14), checking, amount="15.99")
    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 1, 14))
    make_txn(db_session, date(2026, 1, 5), GriprTransactionType.EXPENSE, "12.50", checking)
    db_session.commit()

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    items = client.get("/api/gripr/transactions", params={"limit": 50}).json()["items"]

    by_amount = {item["amount"]: item["is_recurring"] for item in items}
    assert by_amount["15.99"] is True
    assert by_amount["12.50"] is False


# -- csv export --------------------------------------------------------------------------------


def test_transactions_export_csv_covers_every_transaction_with_names_resolved(db_session):
    from app.db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import gripr as gripr_router

    checking = make_account(db_session, "ING")
    savings = make_account(db_session, "Spaarrekening", type_=GriprAccountType.SAVINGS)
    groceries = make_category(db_session, "Boodschappen")
    make_txn(db_session, date(2026, 1, 5), GriprTransactionType.EXPENSE, "12.50", checking, category=groceries)
    make_txn(db_session, date(2026, 1, 1), GriprTransactionType.TRANSFER, "100", checking, counter_account=savings)
    db_session.commit()

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/gripr/transactions/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = response.text.strip().splitlines()
    assert rows[0] == "date,type,account,counter_account,category,amount,notes"
    assert len(rows) == 3  # header + the two transactions above
    # list_all_transactions orders by date, so the January 1st transfer comes first.
    assert rows[1].startswith("2026-01-01,transfer,ING,Spaarrekening,,100")
    assert rows[2].startswith("2026-01-05,expense,ING,,Boodschappen,12.50")


# -- renaming accounts and categories -------------------------------------------------------


def test_renaming_a_category(db_session):
    from app.db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import gripr as gripr_router

    category = make_category(db_session, "Boodschappen")
    db_session.commit()

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.put(f"/api/gripr/categories/{category.id}", json={"name": "Groceries"})

    assert response.status_code == 200
    assert response.json()["name"] == "Groceries"
    assert client.get("/api/gripr/categories").json()[0]["name"] == "Groceries"


def test_renaming_an_account(db_session):
    from app.db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import gripr as gripr_router

    account = make_account(db_session, "ING")
    db_session.commit()

    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.put(f"/api/gripr/accounts/{account.id}", json={"name": "ING Betaalrekening"})

    assert response.status_code == 200
    assert response.json()["name"] == "ING Betaalrekening"


# -- planned (not yet booked) occurrences -----------------------------------------------------


def test_planned_occurrences_projects_every_occurrence_up_to_the_period_end(db_session):
    checking = make_account(db_session, "ING")
    weekly = make_recurring(
        db_session, "Groente", date(2026, 10, 1), checking, frequency=GriprRecurrenceFrequency.WEEKLY
    )
    make_recurring(db_session, "Netflix", date(2026, 10, 14), checking)

    # Period starting on the 25th: Oct 1 falls in Sep 25 - Oct 24.
    until, planned = gripr_recurring_service.planned_until_period_end(db_session, 25, as_of=date(2026, 10, 1))

    assert until == date(2026, 10, 24)
    # Oct 1 itself is today, not upcoming; the weekly rule then lands on 8/15/22, Netflix on 14.
    assert [(p.rule.name, p.date) for p in planned] == [
        ("Groente", date(2026, 10, 8)),
        ("Netflix", date(2026, 10, 14)),
        ("Groente", date(2026, 10, 15)),
        ("Groente", date(2026, 10, 22)),
    ]
    # A projection only -- nothing was booked and the rule's schedule didn't move.
    assert weekly.next_due_date == date(2026, 10, 1)
    assert gripr_transaction_repo.list_all_transactions(db_session) == []


def test_planned_occurrences_skips_what_is_already_booked(db_session):
    checking = make_account(db_session, "ING")
    rule = make_recurring(db_session, "Spotify", date(2026, 10, 3), checking)
    gripr_recurring_service.generate_due(db_session, as_of=date(2026, 10, 1))  # pre-books Oct 3

    planned = gripr_recurring_service.planned_occurrences(db_session, date(2026, 10, 1), date(2026, 11, 30))

    # Oct 3 is already a (future-dated) ledger row; only Nov 3 is still just planned.
    assert [(p.rule.id, p.date) for p in planned] == [(rule.id, date(2026, 11, 3))]


def test_planned_occurrences_respects_end_dates_intervals_and_paused_rules(db_session):
    checking = make_account(db_session, "ING")
    make_recurring(db_session, "Ends", date(2026, 10, 5), checking, frequency=GriprRecurrenceFrequency.WEEKLY, end_date=date(2026, 10, 12))
    make_recurring(db_session, "Biweekly", date(2026, 10, 2), checking, frequency=GriprRecurrenceFrequency.WEEKLY, interval=2)
    make_recurring(db_session, "Paused", date(2026, 10, 6), checking, is_active=False)

    planned = gripr_recurring_service.planned_occurrences(db_session, date(2026, 10, 1), date(2026, 10, 24))

    assert [(p.rule.name, p.date) for p in planned] == [
        ("Biweekly", date(2026, 10, 2)),
        ("Ends", date(2026, 10, 5)),
        ("Ends", date(2026, 10, 12)),
        ("Biweekly", date(2026, 10, 16)),
    ]
