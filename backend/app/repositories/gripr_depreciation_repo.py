from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.gripr_depreciation import GriprDepreciation


def for_rule(db: Session, recurring_id: int) -> list[GriprDepreciation]:
    return list(db.execute(select(GriprDepreciation).where(GriprDepreciation.recurring_id == recurring_id).order_by(GriprDepreciation.id)).scalars().all())


def for_rules(db: Session, recurring_ids: list[int]) -> dict[int, list[GriprDepreciation]]:
    if not recurring_ids:
        return {}
    rows = db.execute(select(GriprDepreciation).where(GriprDepreciation.recurring_id.in_(recurring_ids)).order_by(GriprDepreciation.id)).scalars().all()
    grouped: dict[int, list[GriprDepreciation]] = {}
    for row in rows:
        grouped.setdefault(row.recurring_id, []).append(row)
    return grouped


def for_transaction(db: Session, transaction_id: int) -> list[GriprDepreciation]:
    return list(db.execute(select(GriprDepreciation).where(GriprDepreciation.transaction_id == transaction_id)).scalars().all())


def add(db: Session, account_id: int, amount: Decimal, *, recurring_id: int | None = None, transaction_id: int | None = None) -> GriprDepreciation:
    row = GriprDepreciation(account_id=account_id, amount=amount, recurring_id=recurring_id, transaction_id=transaction_id)
    db.add(row)
    db.flush()
    return row


def delete_for_rule(db: Session, recurring_id: int) -> None:
    db.execute(delete(GriprDepreciation).where(GriprDepreciation.recurring_id == recurring_id))


def delete_for_transaction(db: Session, transaction_id: int) -> None:
    db.execute(delete(GriprDepreciation).where(GriprDepreciation.transaction_id == transaction_id))
