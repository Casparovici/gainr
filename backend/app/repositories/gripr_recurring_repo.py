from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.gripr_recurring import GriprRecurrenceFrequency, GriprRecurringTransaction
from app.models.gripr_transaction import GriprTransactionType

_CENTS = Decimal("0.01")
# What one occurrence at this frequency is worth per calendar month on average.
_MONTHLY_FACTOR = {
    GriprRecurrenceFrequency.WEEKLY: Decimal(52) / 12,
    GriprRecurrenceFrequency.MONTHLY: Decimal(1),
    GriprRecurrenceFrequency.YEARLY: Decimal(1) / 12,
}


def list_recurring(db: Session, include_inactive: bool = True) -> list[GriprRecurringTransaction]:
    query = (
        select(GriprRecurringTransaction)
        .options(
            joinedload(GriprRecurringTransaction.account),
            joinedload(GriprRecurringTransaction.counter_account),
            joinedload(GriprRecurringTransaction.category),
        )
        .order_by(GriprRecurringTransaction.next_due_date, GriprRecurringTransaction.name)
    )
    if not include_inactive:
        query = query.where(GriprRecurringTransaction.is_active.is_(True))
    return list(db.execute(query).unique().scalars().all())


def get_recurring(db: Session, recurring_id: int) -> GriprRecurringTransaction | None:
    return db.get(GriprRecurringTransaction, recurring_id)


def create_recurring(db: Session, **fields) -> GriprRecurringTransaction:
    rule = GriprRecurringTransaction(**fields)
    db.add(rule)
    db.flush()
    return rule


def update_recurring(db: Session, rule: GriprRecurringTransaction, **fields) -> GriprRecurringTransaction:
    # Present key means "apply this", including an explicit None to clear -- callers pass
    # model_dump(exclude_unset=True). See gripr_transaction_repo.update_transaction.
    for key, value in fields.items():
        setattr(rule, key, value)
    db.flush()
    return rule


def delete_recurring(db: Session, rule: GriprRecurringTransaction) -> None:
    db.delete(rule)
    db.flush()


def monthly_equivalent_for_categories(
    db: Session, category_ids: list[int], type_: GriprTransactionType
) -> Decimal:
    """Every active rule filed under any of these categories, normalized to what it costs per
    calendar month on average — a weekly rule counted at 52/12 occurrences, a yearly one at
    1/12 — so a budget suggestion can add a rule paid quarterly or biweekly to one paid
    monthly. Used to suggest a budget from what's already committed via Recurring."""
    query = select(GriprRecurringTransaction).where(
        GriprRecurringTransaction.is_active.is_(True),
        GriprRecurringTransaction.type == type_,
        GriprRecurringTransaction.category_id.in_(category_ids),
    )
    total = Decimal(0)
    for rule in db.execute(query).scalars().all():
        total += rule.amount * _MONTHLY_FACTOR[rule.frequency]
    return total.quantize(_CENTS, rounding=ROUND_HALF_UP)


def monthly_equivalent_for_account(db: Session, account_id: int) -> Decimal:
    """Every active TRANSFER rule whose destination is this account, normalized to a monthly
    average -- the "Recurring" suggestion for a savings goal, mirroring
    monthly_equivalent_for_categories."""
    query = select(GriprRecurringTransaction).where(
        GriprRecurringTransaction.is_active.is_(True),
        GriprRecurringTransaction.type == GriprTransactionType.TRANSFER,
        GriprRecurringTransaction.counter_account_id == account_id,
    )
    total = Decimal(0)
    for rule in db.execute(query).scalars().all():
        total += rule.amount * _MONTHLY_FACTOR[rule.frequency]
    return total.quantize(_CENTS, rounding=ROUND_HALF_UP)
