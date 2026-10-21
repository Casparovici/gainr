from datetime import date as date_
from decimal import Decimal

from sqlalchemy import and_, case, delete, func, or_, select, update
from sqlalchemy.orm import Session, aliased, joinedload

from app.models.bank_sync import BankSyncedTransaction
from app.models.gripr_transaction import GriprTransaction, GriprTransactionType
from app.models.gripr_transaction_attachment import GriprTransactionAttachment


def list_transactions(
    db: Session,
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "date",
    sort_dir: str = "desc",
    account_id: int | None = None,
    category_ids: list[int] | None = None,
    type_filter: GriprTransactionType | None = None,
    date_from: date_ | None = None,
    date_to: date_ | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    uncategorized: bool = False,
    search: str | None = None,
) -> tuple[list[GriprTransaction], int]:
    query = select(GriprTransaction).options(
        joinedload(GriprTransaction.account),
        joinedload(GriprTransaction.counter_account),
        joinedload(GriprTransaction.category),
        joinedload(GriprTransaction.refund_of),
    )
    count_query = select(func.count()).select_from(GriprTransaction)

    if account_id is not None:
        # Either side of a transfer counts as "this account's" transaction.
        clause = (GriprTransaction.account_id == account_id) | (GriprTransaction.counter_account_id == account_id)
        query = query.where(clause)
        count_query = count_query.where(clause)
    if category_ids is not None:
        # Passed pre-expanded (a parent category plus its subcategories) so picking "Groceries"
        # matches everything filed under it, the same rollup the budget page's "spent" uses.
        query = query.where(GriprTransaction.category_id.in_(category_ids))
        count_query = count_query.where(GriprTransaction.category_id.in_(category_ids))
    if type_filter is not None:
        query = query.where(GriprTransaction.type == type_filter)
        count_query = count_query.where(GriprTransaction.type == type_filter)
    if uncategorized:
        # What still needs filing: an expense, income or refund without a category. A transfer
        # never has one, so it isn't "uncategorized" -- see GriprTransaction.category_id.
        clause = GriprTransaction.category_id.is_(None) & (GriprTransaction.type != GriprTransactionType.TRANSFER)
        query = query.where(clause)
        count_query = count_query.where(clause)
    if date_from:
        query = query.where(GriprTransaction.date >= date_from)
        count_query = count_query.where(GriprTransaction.date >= date_from)
    if date_to:
        query = query.where(GriprTransaction.date <= date_to)
        count_query = count_query.where(GriprTransaction.date <= date_to)
    if amount_min is not None:
        query = query.where(GriprTransaction.amount >= amount_min)
        count_query = count_query.where(GriprTransaction.amount >= amount_min)
    if amount_max is not None:
        query = query.where(GriprTransaction.amount <= amount_max)
        count_query = count_query.where(GriprTransaction.amount <= amount_max)

    if search and search.strip():
        clause = _search_clause(search.strip())
        query = query.where(clause)
        count_query = count_query.where(clause)

    sort_col = getattr(GriprTransaction, sort_by, GriprTransaction.date)
    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc(), GriprTransaction.id.desc())
    query = query.offset(offset).limit(limit)

    total = db.execute(count_query).scalar_one()
    items = list(db.execute(query).unique().scalars().all())
    return items, total


def _search_clause(text: str):
    """Free-text search over what a transaction says about itself: its notes (where the bank's
    counterparty and description land), the name of its category or account, and -- when the text
    reads as an amount ("31,20", "31.2") -- the amount itself."""
    from app.models.gripr_account import GriprAccount
    from app.models.gripr_category import GriprCategory

    pattern = f"%{text.casefold()}%"
    clauses = [
        func.lower(func.coalesce(GriprTransaction.notes, "")).like(pattern),
        GriprTransaction.category_id.in_(select(GriprCategory.id).where(func.lower(GriprCategory.name).like(pattern))),
        GriprTransaction.account_id.in_(select(GriprAccount.id).where(func.lower(GriprAccount.name).like(pattern))),
    ]
    try:
        amount = Decimal(text.replace("€", "").replace(" ", "").replace(",", "."))
    except ArithmeticError:
        amount = None
    if amount is not None and amount.is_finite():
        clauses.append(GriprTransaction.amount == amount)
    return or_(*clauses)


def usage_counts(db: Session) -> dict[int, int]:
    """Number of transactions each account appears in, either side of a transfer counted —
    what "most used" means for sorting an account picker."""
    primary = select(GriprTransaction.account_id, func.count()).group_by(GriprTransaction.account_id)
    counter = (
        select(GriprTransaction.counter_account_id, func.count())
        .where(GriprTransaction.counter_account_id.is_not(None))
        .group_by(GriprTransaction.counter_account_id)
    )
    counts: dict[int, int] = {}
    for account_id, n in db.execute(primary).all():
        counts[account_id] = counts.get(account_id, 0) + n
    for account_id, n in db.execute(counter).all():
        counts[account_id] = counts.get(account_id, 0) + n
    return counts


def list_all_transactions(db: Session) -> list[GriprTransaction]:
    query = (
        select(GriprTransaction)
        .options(
            joinedload(GriprTransaction.account),
            joinedload(GriprTransaction.counter_account),
            joinedload(GriprTransaction.category),
        )
        .order_by(GriprTransaction.date, GriprTransaction.id)
    )
    return list(db.execute(query).unique().scalars().all())


def get_transaction(db: Session, transaction_id: int) -> GriprTransaction | None:
    return db.get(GriprTransaction, transaction_id)


def exists_by_source_ref(db: Session, source_ref: str) -> bool:
    query = select(GriprTransaction).where(GriprTransaction.source_ref == source_ref)
    return db.execute(query).first() is not None


def get_by_source_ref(db: Session, source_ref: str) -> GriprTransaction | None:
    query = select(GriprTransaction).where(GriprTransaction.source_ref == source_ref)
    return db.execute(query).scalar_one_or_none()


def find_matching_expense(
    db: Session, account_id: int, amounts: set[Decimal], date_from: date_, date_to: date_, exclude_ids: set[int]
) -> GriprTransaction | None:
    """An expense on `account_id` for exactly one of `amounts`, dated within the window, that no other
    Picnic order has claimed yet -- how a Picnic charge the reader already booked by hand is
    recognised instead of booked twice (see picnic_sync_service). Closest-dated first."""
    query = (
        select(GriprTransaction)
        .where(
            GriprTransaction.account_id == account_id,
            GriprTransaction.type == GriprTransactionType.EXPENSE,
            GriprTransaction.amount.in_(amounts),
            GriprTransaction.date >= date_from,
            GriprTransaction.date <= date_to,
            (GriprTransaction.source_ref.is_(None)) | (~GriprTransaction.source_ref.startswith("picnic_order:")),
        )
        .order_by(GriprTransaction.date)
    )
    candidates = [t for t in db.execute(query).scalars().all() if t.id not in exclude_ids]
    return candidates[0] if candidates else None


def create_transaction(db: Session, **fields) -> GriprTransaction:
    txn = GriprTransaction(**fields)
    db.add(txn)
    db.flush()
    return txn


def update_transaction(db: Session, txn: GriprTransaction, **fields) -> GriprTransaction:
    # Callers pass model_dump(exclude_unset=True), so a key being present means "apply this" --
    # including an explicit None to clear it. Skipping None here stranded the old
    # counter_account_id on a transfer edited into an expense, which then kept surfacing under
    # the counter account (list_transactions matches either side).
    for key, value in fields.items():
        setattr(txn, key, value)
    db.flush()
    return txn


def delete_transaction(db: Session, txn: GriprTransaction) -> None:
    # SQLite doesn't enforce the attachments' ON DELETE CASCADE (foreign keys are off), so the
    # files go explicitly -- otherwise they'd outlive the transaction as unreachable rows.
    db.execute(delete(GriprTransactionAttachment).where(GriprTransactionAttachment.transaction_id == txn.id))
    db.delete(txn)
    db.flush()


def clear_category(db: Session, category_ids: list[int]) -> None:
    """Un-tags every transaction filed under any of these categories rather than deleting them
    — the money movement they record is real and stays in the ledger; only the categorization
    goes away. Used when a category is deleted, mirroring how a manual balance correction
    absorbs drift instead of fabricating a transaction to explain it."""
    db.execute(update(GriprTransaction).where(GriprTransaction.category_id.in_(category_ids)).values(category_id=None))
    db.flush()


def sum_amount(
    db: Session,
    account_id: int,
    type_: GriprTransactionType,
    counter_side: bool = False,
) -> Decimal:
    """Sum of amounts for `type_` where the account sits on the paying/receiving/source side
    (counter_side=False) or, for transfers, the destination side (counter_side=True). A
    future-dated transaction (tomorrow's rent, a recurring rule generated ahead of its due date)
    doesn't count toward the balance until its own date arrives."""
    column = GriprTransaction.counter_account_id if counter_side else GriprTransaction.account_id
    query = select(func.coalesce(func.sum(GriprTransaction.amount), 0)).where(
        column == account_id, GriprTransaction.type == type_, GriprTransaction.date <= date_.today()
    )
    return db.execute(query).scalar_one()


def sum_by_type(db: Session, type_: GriprTransactionType, date_from: date_, date_to: date_) -> Decimal:
    query = select(func.coalesce(func.sum(GriprTransaction.amount), 0)).where(
        GriprTransaction.type == type_,
        GriprTransaction.date >= date_from,
        GriprTransaction.date <= date_to,
        GriprTransaction.date <= date_.today(),
    )
    return db.execute(query).scalar_one()


def sum_for_categories(
    db: Session,
    category_ids: list[int],
    type_: GriprTransactionType,
    date_from: date_,
    date_to: date_,
) -> Decimal:
    query = select(func.coalesce(func.sum(GriprTransaction.amount), 0)).where(
        GriprTransaction.category_id.in_(category_ids),
        GriprTransaction.type == type_,
        GriprTransaction.date >= date_from,
        GriprTransaction.date <= date_to,
        GriprTransaction.date <= date_.today(),
    )
    return db.execute(query).scalar_one()


def net_transferred_in(db: Session, account_id: int, date_from: date_, date_to: date_) -> Decimal:
    """Inbound transfers to this account minus outbound ones, within the period -- what "saved"
    means for a savings-goal line: a withdrawal back out during the period lowers progress
    rather than only counting deposits. Future-dated transfers don't count until they arrive."""
    inbound = select(func.coalesce(func.sum(GriprTransaction.amount), 0)).where(
        GriprTransaction.counter_account_id == account_id,
        GriprTransaction.type == GriprTransactionType.TRANSFER,
        GriprTransaction.date >= date_from,
        GriprTransaction.date <= date_to,
        GriprTransaction.date <= date_.today(),
    )
    outbound = select(func.coalesce(func.sum(GriprTransaction.amount), 0)).where(
        GriprTransaction.account_id == account_id,
        GriprTransaction.type == GriprTransactionType.TRANSFER,
        GriprTransaction.date >= date_from,
        GriprTransaction.date <= date_to,
        GriprTransaction.date <= date_.today(),
    )
    return db.execute(inbound).scalar_one() - db.execute(outbound).scalar_one()


def _received_so_far():
    """Per expense (correlated): what its linked refunds have brought back up to today."""
    refund = aliased(GriprTransaction)
    return (
        select(func.coalesce(func.sum(refund.amount), 0))
        .where(
            refund.refund_of_id == GriprTransaction.id,
            refund.type == GriprTransactionType.REFUND,
            refund.date <= date_.today(),
        )
        .correlate(GriprTransaction)
        .scalar_subquery()
    )


def _net_spend_query(date_from: date_, date_to: date_, *group_by):
    """Expenses minus refunds, the building block for every "what did I spend" figure. A refund
    linked to an expense counts in the expense's period rather than its own (a Tikkie arriving
    on the 2nd lowers last month's dinner, not this month's groceries); an unlinked refund falls
    back to its own date. Nothing dated after today counts yet, judged on each row's own date --
    a refund still on its way hasn't come back. See docs/adr/0023.

    An expense expecting money back counts only the reader's share from the start: what's still
    to come back (expected minus what its refunds already brought) is left out too, alongside
    the refunds themselves. See docs/adr/0032."""
    original = aliased(GriprTransaction)
    effective_date = func.coalesce(original.date, GriprTransaction.date)
    received = _received_so_far()
    outstanding = case(
        (GriprTransaction.expected_back > received, GriprTransaction.expected_back - received),
        else_=0,
    )
    signed = case(
        (GriprTransaction.type == GriprTransactionType.REFUND, -GriprTransaction.amount),
        (GriprTransaction.expected_back.is_not(None), GriprTransaction.amount - outstanding),
        else_=GriprTransaction.amount,
    )
    return (
        select(*group_by, func.coalesce(func.sum(signed), 0))
        .select_from(GriprTransaction)
        .outerjoin(original, GriprTransaction.refund_of_id == original.id)
        .where(
            GriprTransaction.type.in_([GriprTransactionType.EXPENSE, GriprTransactionType.REFUND]),
            effective_date >= date_from,
            effective_date <= date_to,
            GriprTransaction.date <= date_.today(),
        )
    )


def sum_net_spend(
    db: Session, date_from: date_, date_to: date_, category_ids: list[int] | None = None
) -> Decimal:
    """Net spend in the range, optionally limited to these (pre-expanded) categories. Can come
    out negative for a category when more came back than went out in that period."""
    query = _net_spend_query(date_from, date_to)
    if category_ids is not None:
        query = query.where(GriprTransaction.category_id.in_(category_ids))
    return Decimal(db.execute(query).scalar_one())


def sum_net_spend_by_category(db: Session, date_from: date_, date_to: date_) -> dict[int, Decimal]:
    """Net spend grouped by category id (subcategories as-is, not rolled up) -- the Overview
    page's category breakdown."""
    query = (
        _net_spend_query(date_from, date_to, GriprTransaction.category_id)
        .where(GriprTransaction.category_id.is_not(None))
        .group_by(GriprTransaction.category_id)
    )
    return {row[0]: Decimal(row[1]) for row in db.execute(query).all()}


def refunded_totals(db: Session, expense_ids: list[int]) -> dict[int, Decimal]:
    """How much has come back so far for each of these expenses -- what the Transactions list
    shows as "€30 back" next to a €60 dinner. Only expenses with at least one refund appear."""
    if not expense_ids:
        return {}
    query = (
        select(GriprTransaction.refund_of_id, func.sum(GriprTransaction.amount))
        .where(GriprTransaction.refund_of_id.in_(expense_ids), GriprTransaction.type == GriprTransactionType.REFUND)
        .group_by(GriprTransaction.refund_of_id)
    )
    return {row[0]: Decimal(row[1]) for row in db.execute(query).all()}


def list_refunds_of(db: Session, expense_id: int) -> list[GriprTransaction]:
    query = select(GriprTransaction).where(GriprTransaction.refund_of_id == expense_id)
    return list(db.execute(query).scalars().all())


def list_expecting_back(db: Session) -> list[GriprTransaction]:
    """Every expense that expects money back, oldest first -- open or covered; the caller
    works out what's still outstanding."""
    query = (
        select(GriprTransaction)
        .options(joinedload(GriprTransaction.account), joinedload(GriprTransaction.category))
        .where(GriprTransaction.type == GriprTransactionType.EXPENSE, GriprTransaction.expected_back.is_not(None))
        .order_by(GriprTransaction.date, GriprTransaction.id)
    )
    return list(db.execute(query).scalars().unique().all())


def _flow_case(account_ids: set[int]):
    """Per-row signed contribution to this group of accounts: transfers in from outside the
    group and income or refunds on it are positive, transfers out of the group and expenses paid
    from it are negative, and a transfer between two accounts of the group is zero. Shared by
    `net_flow` and `daily_net_flow` so the two can't drift apart on sign conventions."""
    T = GriprTransactionType
    mine = GriprTransaction.account_id.in_(account_ids)
    counter_mine = GriprTransaction.counter_account_id.in_(account_ids)
    return case(
        (and_(GriprTransaction.type == T.TRANSFER, counter_mine, ~mine), GriprTransaction.amount),
        (and_(GriprTransaction.type == T.TRANSFER, mine, or_(GriprTransaction.counter_account_id.is_(None), ~counter_mine)), -GriprTransaction.amount),
        (and_(GriprTransaction.type.in_([T.INCOME, T.REFUND]), mine), GriprTransaction.amount),
        (and_(GriprTransaction.type == T.EXPENSE, mine), -GriprTransaction.amount),
        else_=0,
    )


def net_flow(db: Session, account_ids: set[int], date_from: date_, date_to: date_) -> Decimal:
    """What moved into this group of accounts in the range, net: transfers in from outside the group
    and income or refunds on it, minus transfers out of the group and expenses paid from it.
    Transfers between two accounts of the group cancel out. Nothing dated after today counts yet."""
    if not account_ids:
        return Decimal(0)
    mine = GriprTransaction.account_id.in_(account_ids)
    counter_mine = GriprTransaction.counter_account_id.in_(account_ids)
    query = select(func.coalesce(func.sum(_flow_case(account_ids)), 0)).where(
        or_(mine, counter_mine),
        GriprTransaction.date >= date_from,
        GriprTransaction.date <= date_to,
        GriprTransaction.date <= date_.today(),
    )
    return Decimal(db.execute(query).scalar_one())


def daily_net_flow(db: Session, account_ids: set[int], date_from: date_, date_to: date_) -> dict[date_, Decimal]:
    """Like `net_flow`, but one total per day -- the building block for a running daily balance
    of this account group. Only dated up to today, same as `net_flow`; a caller that also needs
    future-dated rows (a balance forecast) gets those from `list_touching` instead."""
    if not account_ids:
        return {}
    mine = GriprTransaction.account_id.in_(account_ids)
    counter_mine = GriprTransaction.counter_account_id.in_(account_ids)
    query = (
        select(GriprTransaction.date, func.coalesce(func.sum(_flow_case(account_ids)), 0))
        .where(
            or_(mine, counter_mine),
            GriprTransaction.date >= date_from,
            GriprTransaction.date <= date_to,
            GriprTransaction.date <= date_.today(),
        )
        .group_by(GriprTransaction.date)
    )
    return {row[0]: Decimal(row[1]) for row in db.execute(query).all()}


def list_touching(db: Session, account_ids: set[int], date_from: date_, date_to: date_) -> list[GriprTransaction]:
    """Real ledger rows touching this account group in the range, including future-dated ones
    (a recurring rule pre-booked a couple of days ahead, or a transaction entered by hand ahead of
    time) -- unlike every sum above, deliberately not capped at today, since a balance forecast
    needs to know about those too."""
    if not account_ids:
        return []
    query = select(GriprTransaction).where(
        or_(GriprTransaction.account_id.in_(account_ids), GriprTransaction.counter_account_id.in_(account_ids)),
        GriprTransaction.date >= date_from,
        GriprTransaction.date <= date_to,
    )
    return list(db.execute(query).scalars().all())


# A single payment above this is a purchase or a bill, not routine spending.
EVERYDAY_MAX = Decimal(500)


def everyday_expenses(db: Session, date_from: date_, date_to: date_) -> list[tuple[date_, Decimal]]:
    """(date, amount) of the routine expenses in the range -- what a spending pattern is learned
    from. Left out: recurring payments (a rent or subscription lands on its rule's day whatever
    the weekday, so it says nothing about when the reader spends; both the rows a rule booked
    itself and the bank entries filed under one), and any single payment above EVERYDAY_MAX (a
    large purchase would swamp the pattern). Nothing dated after today."""
    fulfilled = select(BankSyncedTransaction.gripr_transaction_id).where(
        BankSyncedTransaction.recurring_id.is_not(None), BankSyncedTransaction.gripr_transaction_id.is_not(None)
    )
    query = select(GriprTransaction.date, GriprTransaction.amount).where(
        GriprTransaction.type == GriprTransactionType.EXPENSE,
        GriprTransaction.amount <= EVERYDAY_MAX,
        GriprTransaction.date >= date_from,
        GriprTransaction.date <= min(date_to, date_.today()),
        or_(GriprTransaction.source_ref.is_(None), ~GriprTransaction.source_ref.startswith("pefi_recurring:")),
        GriprTransaction.id.not_in(fulfilled),
    )
    return [(row[0], Decimal(row[1])) for row in db.execute(query).all()]
