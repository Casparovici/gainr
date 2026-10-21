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


# A budget is only called chronically over or under after this many completed periods in a row:
# one bad month is a month, three is a budget that doesn't match how the money is spent.
ATTENTION_PERIODS = 3
# "Always under" means spending stayed below this share of the budget every time.
UNDER_SHARE = Decimal("0.75")
# Suggested budgets round up to a figure that's easy to type and remember.
SUGGESTION_STEP = Decimal(5)


@dataclass
class BudgetAttention:
    category: GriprCategory
    kind: str  # "over_streak" | "under_streak"
    periods: int
    budgeted: Decimal
    average_spent: Decimal
    suggested_budget: Decimal


def _round_up(value: Decimal) -> Decimal:
    return (value / SUGGESTION_STEP).to_integral_value(rounding="ROUND_CEILING") * SUGGESTION_STEP


def budget_attention(db: Session, month: date_) -> list[BudgetAttention]:
    """Expense categories whose budget has been missed the same way for the last few completed
    periods before `month`: overspent every time (the budget is too low, or the spending needs
    to come down) or comfortably under every time (money tied up that could go elsewhere). Each
    comes with a budget that would have fitted the average. A category needs a budget in every
    one of those periods to count -- no budget is not "under budget"."""
    start, _ = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    past = [
        {line.category.id: line for line in get_budget_status(db, start - relativedelta(months=i))}
        for i in range(1, ATTENTION_PERIODS + 1)
    ]
    found: list[BudgetAttention] = []
    for line in get_budget_status(db, month):
        if line.category.kind != GriprCategoryKind.EXPENSE or line.budgeted <= 0:
            continue
        history = [p[line.category.id] for p in past if line.category.id in p]
        if len(history) < ATTENTION_PERIODS or any(h.budgeted <= 0 for h in history):
            continue
        average = sum((h.spent for h in history), Decimal(0)) / len(history)
        suggested = _round_up(average)
        if all(h.spent > h.budgeted for h in history):
            kind = "over_streak"
        elif all(h.spent < h.budgeted * UNDER_SHARE for h in history) and suggested < line.budgeted:
            kind = "under_streak"
        else:
            continue
        found.append(BudgetAttention(line.category, kind, len(history), line.budgeted, average, suggested))
    # The biggest gap between the budget and how the money really goes first.
    return sorted(found, key=lambda a: (a.kind != "over_streak", -abs(a.average_spent - a.budgeted)))


def set_budget(db: Session, category_id: int, month: date_, amount: Decimal):
    start, _ = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    return gripr_budget_repo.upsert_budget(db, category_id, start, amount)


SUGGESTION_YEAR_MONTHS = 12


@dataclass
class BudgetSuggestion:
    category_id: int
    previous_month: Decimal
    year_average: Decimal
    recurring_monthly: Decimal


def _trailing_year_actuals(db: Session, start: date_) -> dict[int, Decimal]:
    """Actual spend (or income received, for an income category) per top-level category over the
    twelve completed periods before the one starting `start`, summed. Built from get_budget_status
    so it's the same "spent" figure the Budget page shows, month by month."""
    totals: dict[int, Decimal] = {}
    for i in range(1, SUGGESTION_YEAR_MONTHS + 1):
        for line in get_budget_status(db, start - relativedelta(months=i)):
            totals[line.category.id] = totals.get(line.category.id, Decimal(0)) + line.spent
    return totals


def get_suggestions(db: Session, month: date_) -> list[BudgetSuggestion]:
    """Three reference points for filling in a budget that's still empty: what you budgeted
    last month, your average actual spend over the trailing year (both zero if there's no history
    for this category yet -- nothing to suggest), and what's already committed via Recurring for
    this category. The year average is what the category really ran at, not the budgets set for
    it: a budget you never stuck to would otherwise keep suggesting itself. Computed for every
    top-level category (expense or income) regardless of whether it currently has a budget -- the
    empty-vs-not check is the caller's, this just answers "what would this category's suggestions
    be for this month.\""""
    start, _ = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    previous_month_start = start - relativedelta(months=1)

    top_level = [c for c in gripr_category_repo.list_categories(db) if c.parent_id is None]
    year_actuals = _trailing_year_actuals(db, start)

    suggestions = []
    for category in top_level:
        previous_budget = gripr_budget_repo.get_budget(db, category.id, previous_month_start)
        previous_month = previous_budget.amount if previous_budget else Decimal(0)

        year_total = year_actuals.get(category.id, Decimal(0))
        year_average = (year_total / SUGGESTION_YEAR_MONTHS).quantize(Decimal("0.01"))

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


@dataclass
class SavingsRoom:
    income_budgeted: Decimal
    expense_budgeted: Decimal
    # Budgeted income minus budgeted expenses: what the period's own budget leaves for saving and
    # investing. Negative when the budgeted expenses are more than the budgeted income.
    room: Decimal
    # What the savings goals already plan to put aside, and what of the room that leaves open.
    goals_budgeted: Decimal
    unallocated: Decimal


def get_savings_room(db: Session, month: date_) -> SavingsRoom:
    """How much the period's budget leaves for savings and investments, set against what the savings
    goals plan to take -- budgeted figures only, so it answers "how much can I save" before the
    period has happened, the way the Expenses and Income tabs plan it."""
    lines = get_budget_status(db, month)
    income = sum((l.budgeted for l in lines if l.category.kind == GriprCategoryKind.INCOME), Decimal(0))
    expenses = sum((l.budgeted for l in lines if l.category.kind == GriprCategoryKind.EXPENSE), Decimal(0))
    goals = sum((l.budgeted for l in get_savings_status(db, month)), Decimal(0))
    room = income - expenses
    return SavingsRoom(
        income_budgeted=income,
        expense_budgeted=expenses,
        room=room,
        goals_budgeted=goals,
        unallocated=room - goals,
    )


def set_savings_goal(db: Session, account_id: int, month: date_, amount: Decimal):
    start, _ = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    return gripr_savings_goal_repo.upsert_goal(db, account_id, start, amount)


@dataclass
class SavingsGoalSuggestion:
    account_id: int
    previous_month: Decimal
    year_average: Decimal
    recurring_monthly: Decimal


def _trailing_year_saved(db: Session, start: date_) -> dict[int, Decimal]:
    """Net money moved into each savings account over the twelve completed periods before the one
    starting `start`, summed. Built from get_savings_status so it's the same "saved" figure the
    savings tiles show, month by month."""
    totals: dict[int, Decimal] = {}
    for i in range(1, SUGGESTION_YEAR_MONTHS + 1):
        for line in get_savings_status(db, start - relativedelta(months=i)):
            totals[line.account.id] = totals.get(line.account.id, Decimal(0)) + line.saved
    return totals


def get_savings_suggestions(db: Session, month: date_) -> list[SavingsGoalSuggestion]:
    """Same three reference points as get_suggestions, but for a savings goal: last period's
    goal, the trailing-year average actually saved (net transfers in, not the goals set), and
    what's already committed via a recurring transfer into the account."""
    start, _ = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    previous_month_start = start - relativedelta(months=1)

    year_saved = _trailing_year_saved(db, start)

    suggestions = []
    for account in _savings_accounts(db):
        previous_goal = gripr_savings_goal_repo.get_goal(db, account.id, previous_month_start)
        previous_month = previous_goal.amount if previous_goal else Decimal(0)

        year_total = year_saved.get(account.id, Decimal(0))
        year_average = (year_total / SUGGESTION_YEAR_MONTHS).quantize(Decimal("0.01"))

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
