from sqlalchemy import func, select
from sqlalchemy.orm import Session, undefer

from app.models.gripr_transaction_attachment import GriprTransactionAttachment


def list_for_transaction(db: Session, transaction_id: int) -> list[GriprTransactionAttachment]:
    """Metadata only -- `content` is deferred and stays unread."""
    return list(
        db.execute(
            select(GriprTransactionAttachment)
            .where(GriprTransactionAttachment.transaction_id == transaction_id)
            .order_by(GriprTransactionAttachment.created_at, GriprTransactionAttachment.id)
        )
        .scalars()
        .all()
    )


def counts_by_transaction(db: Session, transaction_ids: list[int]) -> dict[int, int]:
    """One grouped query for a whole page of transactions, instead of one per row."""
    if not transaction_ids:
        return {}
    rows = db.execute(
        select(GriprTransactionAttachment.transaction_id, func.count())
        .where(GriprTransactionAttachment.transaction_id.in_(transaction_ids))
        .group_by(GriprTransactionAttachment.transaction_id)
    )
    return {transaction_id: count for transaction_id, count in rows}


def count_for_transaction(db: Session, transaction_id: int) -> int:
    return counts_by_transaction(db, [transaction_id]).get(transaction_id, 0)


def get_with_content(db: Session, attachment_id: int) -> GriprTransactionAttachment | None:
    return db.execute(
        select(GriprTransactionAttachment).options(undefer(GriprTransactionAttachment.content)).where(GriprTransactionAttachment.id == attachment_id)
    ).scalar_one_or_none()


def create(db: Session, **fields) -> GriprTransactionAttachment:
    attachment = GriprTransactionAttachment(**fields)
    db.add(attachment)
    db.flush()
    return attachment


def delete(db: Session, attachment: GriprTransactionAttachment) -> None:
    db.delete(attachment)
    db.flush()
