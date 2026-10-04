from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.broker_sync import BrokerConnection, BrokerSyncedItem
from app.models.transaction import Transaction, TransactionType


# -- connections -------------------------------------------------------------------------------


def get_connection(db: Session, broker: str) -> BrokerConnection | None:
    return db.execute(select(BrokerConnection).where(BrokerConnection.broker == broker)).scalar_one_or_none()


def update_connection(db: Session, connection: BrokerConnection, **fields) -> BrokerConnection:
    for key, value in fields.items():
        setattr(connection, key, value)
    db.flush()
    return connection


# -- assets ------------------------------------------------------------------------------------


def assets_by_isin(db: Session, isins: set[str]) -> dict[str, list[Asset]]:
    if not isins:
        return {}
    found: dict[str, list[Asset]] = {}
    for asset in db.execute(select(Asset).where(Asset.isin.in_(isins))).scalars().all():
        found.setdefault(asset.isin, []).append(asset)
    return found


# -- handled records ---------------------------------------------------------------------------


def handled_references(db: Session, references: list[str]) -> set[str]:
    if not references:
        return set()
    query = select(BrokerSyncedItem.reference).where(BrokerSyncedItem.reference.in_(references))
    return set(db.execute(query).scalars().all())


def record(db: Session, reference: str, outcome: str, transaction_id: int | None = None) -> BrokerSyncedItem:
    row = BrokerSyncedItem(reference=reference, outcome=outcome, transaction_id=transaction_id, synced_at=datetime.now())
    db.add(row)
    db.flush()
    return row


def find_unclaimed(
    db: Session,
    portfolio_id: int,
    broker: str,
    type_: TransactionType,
    asset_id: int,
    around: date,
    days: int,
    prefix: str,
) -> list[Transaction]:
    """The reader's own rows that could be this broker record: same portfolio, broker, type and
    asset, dated within `days` of `around`, neither booked by this sync (its `source_ref` starts
    with `prefix`) nor already claimed by another record. Closest-dated first."""
    claimed = select(BrokerSyncedItem.transaction_id).where(
        BrokerSyncedItem.transaction_id.is_not(None), BrokerSyncedItem.reference.startswith(f"{prefix}:")
    )
    query = select(Transaction).where(
        Transaction.portfolio_id == portfolio_id,
        Transaction.broker == broker,
        Transaction.type == type_,
        Transaction.asset_id == asset_id,
        Transaction.date >= around - timedelta(days=days),
        Transaction.date <= around + timedelta(days=days),
        Transaction.id.not_in(claimed),
    )
    rows = [t for t in db.execute(query).scalars().all() if not (t.source_ref or "").startswith(f"{prefix}:")]
    return sorted(rows, key=lambda t: (abs((t.date - around).days), t.id))


def quantity_close(a: Decimal | None, b: Decimal, tolerance: Decimal = Decimal("0.000001")) -> bool:
    return a is not None and abs(abs(a) - b) <= tolerance
