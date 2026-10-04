from dataclasses import dataclass
from datetime import date as date_
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.gripr_account import GriprAccount, GriprAccountType
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_transaction import GriprTransactionType
from app.repositories import (
    gripr_account_repo,
    gripr_budget_repo,
    gripr_category_repo,
    gripr_recurring_repo,
    gripr_savings_goal_repo,
    gripr_settings_repo,
    gripr_transaction_repo,
)
from app.services.gripr_period_service import period_bounds

# Only these account types can carry a savings goal -- a target for "money moved in", which only
# makes sense for an account you're deliberately building up.
SAVINGS_GOAL_ACCOUNT_TYPES = (GriprAccountType.SAVINGS, GriprAccountType.INVESTMENT)


# A budget on an expense category tracks spend against a cap; a budget on an income category
# tracks receipts against a target -- same shape (a category, a budgeted amount, an actual),
# but which transaction type counts toward "actual" depends on the category's own kind.
_TXN_TYPE_FOR_KIND = {
    GriprCategoryKind.EXPENSE: GriprTransactionType.EXPENSE,
    GriprCategoryKind.INCOME: GriprTransactionType.INCOME,
}


@dataclass
class BudgetLine:
    category: GriprCategory
    budgeted: Decimal
    spent: Decimal


def get_budget_status(db: Session, month: date_) -> list[BudgetLine]:
    start, end = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    top_level = [c for c in gripr_category_repo.list_categories(db) if c.parent_id is None]
    budgets = {b.category_id: b.amount for b in gripr_budget_repo.list_budgets_for_month(db, start)}

    lines = []
    for category in top_level:
        # A budget covers the parent category and everything filed under it — a transaction
        # tagged "Eten & Drinken (Bars)" should count against the "Eten & Drinken" budget.
        category_ids = gripr_category_repo.descendant_ids(db, category.id)
        if category.kind == GriprCategoryKind.EXPENSE:
            # Net of refunds -- only your own share of a split bill counts against the budget.
            spent = gripr_transaction_repo.sum_net_spend(db, start, end, category_ids)
        else:
            spent = gripr_transaction_repo.sum_for_categories(db, category_ids, GriprTransactionType.INCOME, start, end)
        lines.append(BudgetLine(category=category, budgeted=budgets.get(category.id, Decimal(0)), spent=spent))
    return lines


def set_budget(db: Session, category_id: int, month: date_, amount: Decimal):
    start, _ = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    return gripr_budget_repo.upsert_budget(db, category_id, start, amount)


@dataclass
class BudgetSuggestion:
    category_id: int
    previous_month: Decimal
    year_average: Decimal
    recurring_monthly: Decimal


def get_suggestions(db: Session, month: date_) -> list[BudgetSuggestion]:
    """Three reference points for filling in a budget that's still empty: what you budgeted
    last month, your average budget over the trailing year (both zero if you've never set one
    for this category before — nothing to suggest yet), and what's already committed via
    Recurring for this category. Computed for every top-level category (expense or income)
    regardless of whether it currently has a budget — the empty-vs-not check is the caller's,
    this just answers "what would this category's suggestions be for this month.\""""
    start, _ = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    previous_month_start = start - relativedelta(months=1)
    year_window_start = previous_month_start - relativedelta(months=11)

    top_level = [c for c in gripr_category_repo.list_categories(db) if c.parent_id is None]

    suggestions = []
    for category in top_level:
        previous_budget = gripr_budget_repo.get_budget(db, category.id, previous_month_start)
        previous_month = previous_budget.amount if previous_budget else Decimal(0)

        year_total = gripr_budget_repo.sum_budgets_in_range(db, category.id, year_window_start, previous_month_start)
        year_average = (year_total / 12).quantize(Decimal("0.01"))

        category_ids = gripr_category_repo.descendant_ids(db, category.id)
        recurring_monthly = gripr_recurring_repo.monthly_equivalent_for_categories(
            db, category_ids, _TXN_TYPE_FOR_KIND[category.kind]
        )
        if category.kind == GriprCategoryKind.EXPENSE:
            # A housemate's recurring share of the rent lowers what Recurring actually commits.
            recurring_monthly -= gripr_recurring_repo.monthly_equivalent_for_categories(
                db, category_ids, GriprTransactionType.REFUND
            )

        suggestions.append(
            BudgetSuggestion(
                category_id=category.id,
                previous_month=previous_month,
                year_average=year_average,
                recurring_monthly=recurring_monthly,
            )
        )
    return suggestions


# -- savings goals ------------------------------------------------------------------------


@dataclass
class SavingsGoalLine:
    account: GriprAccount
    budgeted: Decimal
    saved: Decimal


def _savings_accounts(db: Session) -> list[GriprAccount]:
    return [a for a in gripr_account_repo.list_accounts(db) if a.type in SAVINGS_GOAL_ACCOUNT_TYPES]


def get_savings_status(db: Session, month: date_) -> list[SavingsGoalLine]:
    start, end = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    goals = {g.account_id: g.amount for g in gripr_savings_goal_repo.list_goals_for_month(db, start)}

    lines = []
    for account in _savings_accounts(db):
        saved = gripr_transaction_repo.net_transferred_in(db, account.id, start, end)
        lines.append(SavingsGoalLine(account=account, budgeted=goals.get(account.id, Decimal(0)), saved=saved))
    return lines


def set_savings_goal(db: Session, account_id: int, month: date_, amount: Decimal):
    start, _ = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    return gripr_savings_goal_repo.upsert_goal(db, account_id, start, amount)


@dataclass
class SavingsGoalSuggestion:
    account_id: int
    previous_month: Decimal
    year_average: Decimal
    recurring_monthly: Decimal


def get_savings_suggestions(db: Session, month: date_) -> list[SavingsGoalSuggestion]:
    """Same three reference points as get_suggestions, but for a savings goal: last period's
    goal, the trailing-year average goal, and what's already committed via a recurring transfer
    into the account."""
    start, _ = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    previous_month_start = start - relativedelta(months=1)
    year_window_start = previous_month_start - relativedelta(months=11)

    suggestions = []
    for account in _savings_accounts(db):
        previous_goal = gripr_savings_goal_repo.get_goal(db, account.id, previous_month_start)
        previous_month = previous_goal.amount if previous_goal else Decimal(0)

        year_total = gripr_savings_goal_repo.sum_goals_in_range(db, account.id, year_window_start, previous_month_start)
        year_average = (year_total / 12).quantize(Decimal("0.01"))

        recurring_monthly = gripr_recurring_repo.monthly_equivalent_for_account(db, account.id)

        suggestions.append(
            SavingsGoalSuggestion(
                account_id=account.id,
                previous_month=previous_month,
                year_average=year_average,
                recurring_monthly=recurring_monthly,
            )
        )
    return suggestions
