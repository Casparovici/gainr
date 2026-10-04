from dataclasses import dataclass
from datetime import date as date_
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.gripr_account import GriprAccountType
from app.models.gripr_transaction import GriprTransactionType
from app.repositories import gripr_account_repo, gripr_category_repo, gripr_settings_repo, gripr_transaction_repo
from app.services.gripr_period_service import period_bounds


@dataclass
class MonthTotal:
    month: date_
    income: Decimal
    expense: Decimal


@dataclass
class CategoryAmount:
    category_id: int
    name: str
    amount: Decimal


@dataclass
class PutAsidePoint:
    month: date_
    investments: Decimal
    savings: Decimal
    reservations: Decimal


@dataclass
class CategoryTrendPoint:
    month: date_
    amount: Decimal


def income_vs_expense(db: Session, months: int = 12, as_of: date_ | None = None) -> list[MonthTotal]:
    as_of = as_of or date_.today()
    start_day = gripr_settings_repo.get_period_start_day(db)
    results = []
    # Walk backwards one period at a time from the period `as_of` falls in, so a period with no
    # activity still shows as zero rather than silently disappearing from the trend.
    cursor, _ = period_bounds(as_of, start_day)
    for _ in range(months):
        start, end = period_bounds(cursor, start_day)
        income = gripr_transaction_repo.sum_by_type(db, GriprTransactionType.INCOME, start, end)
        # Net of refunds: a friend paying back half a dinner is less spending, not income.
        expense = gripr_transaction_repo.sum_net_spend(db, start, end)
        results.append(MonthTotal(month=start, income=income, expense=expense))
        cursor = cursor - relativedelta(months=1)
    results.reverse()
    return results


def spending_by_category(db: Session, month: date_) -> list[CategoryAmount]:
    """Current period's expenses net of refunds, rolled up from subcategories onto their
    top-level parent — the same "Eten & Drinken (Bars)" counts toward "Eten & Drinken" rule the
    budget uses. A category whose refunds cancel out its spend drops out: there's no slice of
    spending left to show for it."""
    start, end = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    raw = gripr_transaction_repo.sum_net_spend_by_category(db, start, end)
    categories = {c.id: c for c in gripr_category_repo.list_categories(db, include_archived=True)}

    totals: dict[int, Decimal] = {}
    for category_id, amount in raw.items():
        category = categories.get(category_id)
        if category is None:
            continue
        top_id = category.parent_id or category.id
        totals[top_id] = totals.get(top_id, Decimal(0)) + amount

    return sorted(
        (
            CategoryAmount(category_id=cid, name=categories[cid].name, amount=amount)
            for cid, amount in totals.items()
            if cid in categories and amount > 0
        ),
        key=lambda c: c.amount,
        reverse=True,
    )


def category_trend(
    db: Session, category_id: int, months: int = 12, as_of: date_ | None = None
) -> list[CategoryTrendPoint]:
    """A top-level category's net spend per period over the trailing `months`, subcategories
    rolled up the same way `spending_by_category` does -- the Overview page's per-category line
    chart."""
    as_of = as_of or date_.today()
    start_day = gripr_settings_repo.get_period_start_day(db)
    category_ids = gripr_category_repo.descendant_ids(db, category_id)
    results = []
    cursor, _ = period_bounds(as_of, start_day)
    for _ in range(months):
        start, end = period_bounds(cursor, start_day)
        amount = gripr_transaction_repo.sum_net_spend(db, start, end, category_ids)
        results.append(CategoryTrendPoint(month=start, amount=amount))
        cursor = cursor - relativedelta(months=1)
    results.reverse()
    return results


def money_put_aside(db: Session, months: int = 12, as_of: date_ | None = None) -> list[PutAsidePoint]:
    """Per period, the net money that went into investments, savings and reservations: transfers
    in minus out, plus income and minus spending on those accounts. Investments are the investment
    accounts (their balance follows the portfolio, so only money moved counts); reservations are the
    virtual pots (Reservering Vakantie, Onderhoud Auto); savings are the other savings accounts.
    Moving money from savings into a pot shows as less savings and more reservations."""
    as_of = as_of or date_.today()
    start_day = gripr_settings_repo.get_period_start_day(db)
    accounts = gripr_account_repo.list_accounts(db, include_archived=True)
    investments = {a.id for a in accounts if a.type == GriprAccountType.INVESTMENT}
    reservations = {a.id for a in accounts if a.held_in_account_id is not None}
    savings = {a.id for a in accounts if a.type == GriprAccountType.SAVINGS and a.held_in_account_id is None}
    results = []
    cursor, _ = period_bounds(as_of, start_day)
    for _ in range(months):
        start, end = period_bounds(cursor, start_day)
        results.append(PutAsidePoint(
            month=start,
            investments=gripr_transaction_repo.net_flow(db, investments, start, end),
            savings=gripr_transaction_repo.net_flow(db, savings, start, end),
            reservations=gripr_transaction_repo.net_flow(db, reservations, start, end),
        ))
        cursor = cursor - relativedelta(months=1)
    results.reverse()
    return results