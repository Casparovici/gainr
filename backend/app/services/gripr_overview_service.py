from dataclasses import dataclass
from datetime import date as date_, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.gripr_account import GriprAccountType
from app.models.gripr_category import GriprCategory, GriprCategoryKind
from app.models.gripr_transaction import GriprTransactionType
from app.repositories import gripr_account_repo, gripr_category_repo, gripr_settings_repo, gripr_transaction_repo
from app.services import gripr_account_service, gripr_budget_service, gripr_recurring_service
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
    # Against the same category's average over the COMPARE_PERIODS periods before: what a reader
    # means by "more than usual". None where there was nothing to compare with.
    average: Decimal | None = None
    change_pct: Decimal | None = None


# How many periods before the selected one "usual" is measured over.
COMPARE_PERIODS = 3


def _change_pct(amount: Decimal, average: Decimal | None) -> Decimal | None:
    return (amount - average) / average * 100 if average else None


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


def _top_level_spend(db: Session, start: date_, end: date_, categories: dict[int, GriprCategory]) -> dict[int, Decimal]:
    """Net spend per top-level category in the range, subcategories rolled up onto their parent."""
    totals: dict[int, Decimal] = {}
    for category_id, amount in gripr_transaction_repo.sum_net_spend_by_category(db, start, end).items():
        category = categories.get(category_id)
        if category is None:
            continue
        top_id = category.parent_id or category.id
        totals[top_id] = totals.get(top_id, Decimal(0)) + amount
    return totals


def _comparison_windows(start: date_, end: date_, start_day: int, today: date_) -> list[tuple[date_, date_]]:
    """The stretches of the COMPARE_PERIODS periods before `start` to compare with. A finished
    period is compared whole; one still running only with the same number of days into each
    earlier period -- twelve days of spending against whole periods would always look low."""
    in_progress = start <= today <= end
    windows = []
    for i in range(1, COMPARE_PERIODS + 1):
        s, e = period_bounds(start - relativedelta(months=i), start_day)
        windows.append((s, min(e, s + (today - start))) if in_progress else (s, e))
    return windows


def spending_by_category(db: Session, month: date_, today: date_ | None = None) -> list[CategoryAmount]:
    """Current period's expenses net of refunds, rolled up from subcategories onto their
    top-level parent — the same "Eten & Drinken (Bars)" counts toward "Eten & Drinken" rule the
    budget uses — each next to its average over the periods before. A category whose refunds
    cancel out its spend drops out: there's no slice of spending left to show for it."""
    start_day = gripr_settings_repo.get_period_start_day(db)
    start, end = period_bounds(month, start_day)
    categories = {c.id: c for c in gripr_category_repo.list_categories(db, include_archived=True)}
    totals = _top_level_spend(db, start, end, categories)
    before = [
        _top_level_spend(db, s, e, categories)
        for s, e in _comparison_windows(start, end, start_day, today or date_.today())
    ]

    rows = []
    for cid, amount in totals.items():
        if cid not in categories or amount <= 0:
            continue
        average = sum((p.get(cid, Decimal(0)) for p in before), Decimal(0)) / COMPARE_PERIODS
        rows.append(CategoryAmount(
            category_id=cid, name=categories[cid].name, amount=amount,
            average=average if average > 0 else None, change_pct=_change_pct(amount, average if average > 0 else None),
        ))
    return sorted(rows, key=lambda c: c.amount, reverse=True)


@dataclass
class CategoryComparison:
    spent: Decimal
    average: Decimal | None
    change_pct: Decimal | None
    periods: int
    # True while the period is still running: the average is then over the same number of days
    # into each earlier period, not over the whole of them.
    so_far: bool


def category_comparison(db: Session, category_id: int, month: date_, today: date_ | None = None) -> CategoryComparison:
    """One top-level category's period against its average over the COMPARE_PERIODS before it --
    net spend for an expense category, income received for an income one."""
    start_day = gripr_settings_repo.get_period_start_day(db)
    start, end = period_bounds(month, start_day)
    category = gripr_category_repo.get_category(db, category_id)
    ids = gripr_category_repo.descendant_ids(db, category_id)

    def total(a: date_, b: date_) -> Decimal:
        if category is not None and category.kind == GriprCategoryKind.INCOME:
            return gripr_transaction_repo.sum_for_categories(db, ids, GriprTransactionType.INCOME, a, b)
        return gripr_transaction_repo.sum_net_spend(db, a, b, ids)

    today = today or date_.today()
    spent = total(start, end)
    before = [total(s, e) for s, e in _comparison_windows(start, end, start_day, today)]
    average = sum(before, Decimal(0)) / COMPARE_PERIODS
    average = average if average > 0 else None
    return CategoryComparison(
        spent=spent, average=average, change_pct=_change_pct(spent, average), periods=COMPARE_PERIODS,
        so_far=start <= today <= end,
    )


def subcategory_breakdown(db: Session, category_id: int, month: date_) -> list[CategoryAmount]:
    """A top-level category's net spend in the period split by the subcategory it was filed under;
    what's filed directly on the category itself comes back under the category's own id, which the
    caller labels (it's the part not yet sorted into a subcategory). Zero and negative rows drop
    out, same as `spending_by_category`."""
    start, end = period_bounds(month, gripr_settings_repo.get_period_start_day(db))
    raw = gripr_transaction_repo.sum_net_spend_by_category(db, start, end)
    categories = {c.id: c for c in gripr_category_repo.list_categories(db, include_archived=True)}
    ids = gripr_category_repo.descendant_ids(db, category_id)
    return sorted(
        (
            CategoryAmount(category_id=cid, name=categories[cid].name, amount=raw[cid])
            for cid in ids
            if cid in categories and raw.get(cid, Decimal(0)) > 0
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


@dataclass
class BalanceForecastPoint:
    date: date_
    balance: Decimal
    is_forecast: bool


@dataclass
class BalanceForecast:
    points: list[BalanceForecastPoint]
    # Where the period ends, and the lowest the balance gets from today on.
    expected_end: Decimal | None = None
    lowest: BalanceForecastPoint | None = None
    # A week of everyday spending kept in the account, and what could leave it today (to savings
    # or investments) without the forecast ever dipping into that buffer.
    buffer: Decimal = Decimal(0)
    safe_to_move: Decimal | None = None
    # Whether the remaining everyday spending follows the reader's own weekday pattern; false
    # when there isn't enough history to learn one, and it is spread evenly instead.
    weekday_pattern: bool = False


# How far back the spending pattern is learned from, and how many expenses it takes before
# there is a pattern to speak of.
PATTERN_DAYS = 84
PATTERN_MIN_EXPENSES = 20
# The buffer kept back when working out what is safe to move: this many days of everyday spending.
BUFFER_DAYS = 7


def _weekday_shares(db: Session, today: date_, days: list[date_]) -> list[Decimal] | None:
    """How the remaining everyday spending divides over `days`, from when the reader has spent
    over the past twelve weeks (recurring payments left out, see everyday_expenses): a Saturday
    that usually carries a fifth of the week's spending gets a fifth. None when there is too
    little history to learn from, which makes the caller spread it evenly."""
    rows = gripr_transaction_repo.everyday_expenses(db, today - timedelta(days=PATTERN_DAYS), today - timedelta(days=1))
    if len(rows) < PATTERN_MIN_EXPENSES:
        return None
    by_weekday = [Decimal(0)] * 7
    for day, amount in rows:
        by_weekday[day.weekday()] += amount
    weights = [by_weekday[d.weekday()] for d in days]
    total = sum(weights, Decimal(0))
    return [w / total for w in weights] if total > 0 else None


def average_monthly_expense(db: Session, today: date_ | None = None) -> Decimal | None:
    """What a period of spending typically comes to: the median net spend of the three completed
    periods before the current one, so a single one-off (a large purchase) doesn't set the
    figure. None when there has been none."""
    today = today or date_.today()
    spent = sorted(m.expense for m in income_vs_expense(db, months=4, as_of=today)[:-1])
    if not spent or spent[-1] <= 0:
        return None
    return spent[len(spent) // 2]


def everyday_buffer(db: Session, today: date_) -> Decimal:
    """A week of everyday spending (groceries, going out -- not the recurring payments, which the
    forecast already places on their dates), averaged over the pattern window."""
    rows = gripr_transaction_repo.everyday_expenses(db, today - timedelta(days=PATTERN_DAYS), today - timedelta(days=1))
    total = sum((amount for _, amount in rows), Decimal(0))
    return (total / PATTERN_DAYS * BUFFER_DAYS).quantize(Decimal("0.01"))


@dataclass
class SavingsHealth:
    # (income - spending) / income for the selected period, and the same over the three
    # completed periods before it -- None where there was no income to divide by.
    savings_rate_pct: Decimal | None
    trailing_rate_pct: Decimal | None
    # Checking and savings balances today, leaving out the reservations (virtual pots), which are
    # earmarked for something rather than there to fall back on.
    liquid_savings: Decimal
    average_monthly_expense: Decimal | None
    # How many months of average spending the liquid savings would cover; None without spending.
    runway_months: Decimal | None


def _rate(income: Decimal, expense: Decimal) -> Decimal | None:
    return (income - expense) / income * 100 if income > 0 else None


def savings_health(db: Session, month: date_ | None = None, today: date_ | None = None) -> SavingsHealth:
    """The two figures a planner asks first: how much of what comes in is kept, and how long the
    money on hand would last. The rate follows the selected period (provisional while it is still
    running, since income may not have arrived yet); the runway is as of today."""
    today = today or date_.today()
    totals = income_vs_expense(db, months=4, as_of=month or today)
    selected, before = totals[-1], totals[:-1]
    accounts = gripr_account_repo.list_accounts(db)
    liquid = sum(
        (
            gripr_account_service.compute_balance(db, a)
            for a in accounts
            if a.type in (GriprAccountType.CHECKING, GriprAccountType.SAVINGS) and a.held_in_account_id is None
        ),
        Decimal(0),
    )
    average = average_monthly_expense(db, today)
    return SavingsHealth(
        savings_rate_pct=_rate(selected.income, selected.expense),
        trailing_rate_pct=_rate(sum((m.income for m in before), Decimal(0)), sum((m.expense for m in before), Decimal(0))),
        liquid_savings=liquid,
        average_monthly_expense=average,
        runway_months=liquid / average if average else None,
    )


def _top_category_id(categories: dict[int, GriprCategory], category_id: int | None) -> int | None:
    category = categories.get(category_id) if category_id is not None else None
    return (category.parent_id or category.id) if category is not None else None


def _signed_flow(
    type_: GriprTransactionType, account_id: int, counter_account_id: int | None, amount: Decimal, group_ids: set[int]
) -> Decimal:
    """What one row (a booked transaction, or a recurring rule's occurrence) contributes to this
    account group, signed -- the same convention as `gripr_transaction_repo._flow_case`, applied
    in Python since the forecast's future side has no row id to run a SQL `case` over yet."""
    mine = account_id in group_ids
    counter_mine = counter_account_id in group_ids if counter_account_id is not None else False
    if type_ == GriprTransactionType.TRANSFER:
        if mine and counter_mine:
            return Decimal(0)
        if counter_mine:
            return amount
        if mine:
            return -amount
        return Decimal(0)
    if type_ in (GriprTransactionType.INCOME, GriprTransactionType.REFUND) and mine:
        return amount
    if type_ == GriprTransactionType.EXPENSE and mine:
        return -amount
    return Decimal(0)


def balance_forecast(db: Session, as_of: date_ | None = None) -> BalanceForecast:
    """Day-by-day spendable balance (checking accounts only -- savings, investment, credit and
    loan balances don't swing with day-to-day spending, so including them would flatten the
    chart's whole point) for the period `as_of` falls in: real balances for every day up to and
    including today, then a forecast for the rest of the period.

    The forecast lands known recurring occurrences (already-booked future rows, like a rule
    pre-booked a couple of days ahead, plus ones not reached yet) on their own dates, and spreads
    each category's budget headroom -- what's left of it once that category's own future
    recurring occurrences are accounted for -- over the remaining days, following the weekdays the
    reader tends to spend on when there is history to learn that from (evenly otherwise), so the
    line slopes the way the account actually moves rather than jumping only on known dates."""
    as_of = as_of or date_.today()
    today = date_.today()
    start_day = gripr_settings_repo.get_period_start_day(db)
    period_start, period_end = period_bounds(as_of, start_day)

    accounts = gripr_account_repo.list_accounts(db)
    checking = [a for a in accounts if a.type == GriprAccountType.CHECKING and a.held_in_account_id is None]
    checking_ids = {a.id for a in checking}
    if not checking_ids:
        return BalanceForecast(points=[])

    balance_today = sum((gripr_account_service.compute_balance(db, a) for a in checking), Decimal(0))

    elapsed_end = min(today, period_end)
    daily_flow = gripr_transaction_repo.daily_net_flow(db, checking_ids, period_start, elapsed_end)
    running = balance_today - sum(daily_flow.values(), Decimal(0))

    points: list[BalanceForecastPoint] = []
    cursor = period_start
    while cursor <= elapsed_end:
        running += daily_flow.get(cursor, Decimal(0))
        points.append(BalanceForecastPoint(date=cursor, balance=running, is_forecast=False))
        cursor += timedelta(days=1)

    if elapsed_end >= period_end:
        return _summarise(db, points, today)

    categories = {c.id: c for c in gripr_category_repo.list_categories(db, include_archived=True)}
    daily_known: dict[date_, Decimal] = {}
    recurring_by_category: dict[tuple[int, GriprTransactionType], Decimal] = {}

    def record(
        day: date_,
        type_: GriprTransactionType,
        account_id: int,
        counter_account_id: int | None,
        amount: Decimal,
        category_id: int | None,
    ) -> None:
        signed = _signed_flow(type_, account_id, counter_account_id, amount, checking_ids)
        if signed == 0:
            return
        daily_known[day] = daily_known.get(day, Decimal(0)) + signed
        top_id = _top_category_id(categories, category_id)
        if top_id is not None and type_ in (GriprTransactionType.EXPENSE, GriprTransactionType.INCOME):
            key = (top_id, type_)
            recurring_by_category[key] = recurring_by_category.get(key, Decimal(0)) + abs(signed)

    forecast_start = elapsed_end + timedelta(days=1)
    for txn in gripr_transaction_repo.list_touching(db, checking_ids, forecast_start, period_end):
        record(txn.date, txn.type, txn.account_id, txn.counter_account_id, txn.amount, txn.category_id)
    for occurrence in gripr_recurring_service.planned_occurrences(db, elapsed_end, period_end):
        rule = occurrence.rule
        record(occurrence.date, rule.type, rule.account_id, rule.counter_account_id, rule.amount, rule.category_id)

    remaining_days = (period_end - elapsed_end).days
    days = [forecast_start + timedelta(days=i) for i in range(remaining_days)]
    expense_headroom = income_headroom = Decimal(0)
    for line in gripr_budget_service.get_budget_status(db, as_of):
        remaining = line.budgeted - line.spent
        expected_type = GriprTransactionType.EXPENSE if line.category.kind == GriprCategoryKind.EXPENSE else GriprTransactionType.INCOME
        covered = recurring_by_category.get((line.category.id, expected_type), Decimal(0))
        headroom = max(Decimal(0), remaining - covered)
        if line.category.kind == GriprCategoryKind.INCOME:
            income_headroom += headroom
        else:
            expense_headroom += headroom

    shares = _weekday_shares(db, today, days)
    even = Decimal(1) / remaining_days
    for i, cursor in enumerate(days):
        spread = -expense_headroom * (shares[i] if shares else even) + income_headroom * even
        running += daily_known.get(cursor, Decimal(0)) + spread
        points.append(BalanceForecastPoint(date=cursor, balance=running.quantize(Decimal("0.01")), is_forecast=True))
    return _summarise(db, points, today, weekday_pattern=shares is not None)


def _summarise(db: Session, points: list[BalanceForecastPoint], today: date_, weekday_pattern: bool = False) -> BalanceForecast:
    """The forecast's headline figures: where the period ends, the low point from today on, and
    what could be moved out today without touching a week's worth of spending."""
    ahead = [p for p in points if p.date >= today]
    if not ahead:
        return BalanceForecast(points=points)
    lowest = min(ahead, key=lambda p: p.balance)
    buffer = everyday_buffer(db, today)
    return BalanceForecast(
        points=points,
        expected_end=points[-1].balance,
        lowest=lowest,
        buffer=buffer,
        safe_to_move=max(Decimal(0), lowest.balance - buffer),
        weekday_pattern=weekday_pattern,
    )
