from sqlalchemy import func, select
from sqlalchemy.orm import Session, undefer

from app.models.transaction_attachment import TransactionAttachment


def list_for_transaction(db: Session, transaction_id: int) -> list[TransactionAttachment]:
    """Metadata only -- `content` is deferred and stays unread."""
    return list(
        db.execute(
            select(TransactionAttachment)
            .where(TransactionAttachment.transaction_id == transaction_id)
            .order_by(TransactionAttachment.created_at, TransactionAttachment.id)
        )
        .scalars()
        .all()
    )


def counts_by_transaction(db: Session, transaction_ids: list[int]) -> dict[int, int]:
    """One grouped query for a whole page of transactions, instead of one per row."""
    if not transaction_ids:
        return {}
    rows = db.execute(
        select(TransactionAttachment.transaction_id, func.count())
        .where(TransactionAttachment.transaction_id.in_(transaction_ids))
        .group_by(TransactionAttachment.transaction_id)
    )
    return {transaction_id: count for transaction_id, count in rows}


def count_for_transaction(db: Session, transaction_id: int) -> int:
    return counts_by_transaction(db, [transaction_id]).get(transaction_id, 0)


def get_with_content(db: Session, attachment_id: int) -> TransactionAttachment | None:
    return db.execute(
        select(TransactionAttachment).options(undefer(TransactionAttachment.content)).where(TransactionAttachment.id == attachment_id)
    ).scalar_one_or_none()


def create(db: Session, **fields) -> TransactionAttachment:
    attachment = TransactionAttachment(**fields)
    db.add(attachment)
    db.flush()
    return attachment


def delete(db: Session, attachment: TransactionAttachment) -> None:
    db.delete(attachment)
    db.flush()
