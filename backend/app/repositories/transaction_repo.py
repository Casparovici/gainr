from datetime import date as date_

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.asset import Asset
from app.models.transaction import Transaction


def list_transactions(
    db: Session,
    portfolio_id: int,
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "date",
    sort_dir: str = "desc",
    asset_name: str | None = None,
    asset_id: int | None = None,
    type_filter: str | None = None,
    broker: str | None = None,
    date_from: date_ | None = None,
    date_to: date_ | None = None,
) -> tuple[list[Transaction], int]:
    query = select(Transaction).options(joinedload(Transaction.asset)).where(Transaction.portfolio_id == portfolio_id)
    count_query = select(func.count()).select_from(Transaction).where(Transaction.portfolio_id == portfolio_id)

    if asset_name:
        query = query.join(Transaction.asset).where(Asset.name.ilike(f"%{asset_name}%"))
        count_query = count_query.join(Transaction.asset).where(Asset.name.ilike(f"%{asset_name}%"))
    if asset_id is not None:
        # Exact identity rather than the asset-name filter above — the position card already
        # knows which asset it's showing, and a name is free text that can be edited.
        query = query.where(Transaction.asset_id == asset_id)
        count_query = count_query.where(Transaction.asset_id == asset_id)
    if type_filter:
        query = query.where(Transaction.type == type_filter)
        count_query = count_query.where(Transaction.type == type_filter)
    if broker:
        query = query.where(Transaction.broker == broker)
        count_query = count_query.where(Transaction.broker == broker)
    if date_from:
        query = query.where(Transaction.date >= date_from)
        count_query = count_query.where(Transaction.date >= date_from)
    if date_to:
        query = query.where(Transaction.date <= date_to)
        count_query = count_query.where(Transaction.date <= date_to)

    sort_col = getattr(Transaction, sort_by, Transaction.date)
    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc(), Transaction.id.desc())
    query = query.offset(offset).limit(limit)

    total = db.execute(count_query).scalar_one()
    items = list(db.execute(query).scalars().all())
    return items, total


def list_distinct_brokers(db: Session, portfolio_id: int) -> list[str]:
    rows = db.execute(
        select(Transaction.broker)
        .where(Transaction.broker.is_not(None), Transaction.portfolio_id == portfolio_id)
        .distinct()
        .order_by(Transaction.broker)
    )
    return [r[0] for r in rows]


def get_transaction(db: Session, transaction_id: int) -> Transaction | None:
    return db.get(Transaction, transaction_id)


def list_all_transactions(db: Session, portfolio_id: int) -> list[Transaction]:
    return list(
        db.execute(
            select(Transaction)
            .options(joinedload(Transaction.asset))
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.date, Transaction.id)
        )
        .scalars()
        .all()
    )


def create_transaction(db: Session, **fields) -> Transaction:
    txn = Transaction(**fields)
    db.add(txn)
    db.flush()
    return txn


def update_transaction(db: Session, txn: Transaction, **fields) -> Transaction:
    # Present key means "apply this", including an explicit None to clear -- callers pass
    # model_dump(exclude_unset=True). See gripr_transaction_repo.update_transaction.
    for key, value in fields.items():
        setattr(txn, key, value)
    db.flush()
    return txn


def delete_transaction(db: Session, txn: Transaction) -> None:
    db.delete(txn)
    db.flush()


def exists_by_source_ref(db: Session, source_ref: str) -> bool:
    """Used by the import script to make re-running it idempotent."""
    query = select(Transaction).where(Transaction.source_ref == source_ref)
    return db.execute(query).first() is not None


def get_by_source_ref(db: Session, source_ref: str) -> Transaction | None:
    """The row a given source owns, for sources that keep updating their own rows rather than
    only inserting them once (the gripr transfer mirror) — `source_ref` is unique."""
    query = select(Transaction).where(Transaction.source_ref == source_ref)
    return db.execute(query).scalar_one_or_none()
