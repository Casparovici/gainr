"""What's worth telling the reader when they come back to gainr: what the Trading 212 sync booked
(fills, dividends, the weekly interest/cashback deposit), instruments it is holding back for lack of
an asset, and a sync that isn't working. Worked out from what's stored; the frontend remembers per
device when the reader last looked and passes it as `since`. Same shape as gripr's
(gripr_notification_service)."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType
from app.services import broker_sync_service

TT = TransactionType
PREFIX = f"{broker_sync_service.PREFIX}:"


@dataclass(frozen=True)
class Notification:
    key: str
    kind: str  # "synced" | "unmapped" | "broker"
    at: datetime
    title: str
    detail: str | None
    link: str


def _utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _synced(db: Session, since: datetime) -> list[Notification]:
    since_naive = since.astimezone(timezone.utc).replace(tzinfo=None)
    rows = db.execute(
        select(Transaction).where(Transaction.created_at > since_naive, Transaction.source_ref.startswith(PREFIX))
    ).scalars().all()
    if not rows:
        return []
    trades = [t for t in rows if t.type in (TT.BUY, TT.SELL)]
    dividends = [t for t in rows if t.type == TT.DIVIDEND]
    deposits = [t for t in rows if t.type == TT.DEPOSIT]
    interest = [t for t in rows if t.type == TT.INTEREST]
    auto = sum(1 for t in trades if "auto-invest" in (t.notes or ""))
    parts = [
        _plural(len(trades), "buy or sell", "buys and sells") + (f" ({auto} auto-invest)" if auto else "") if trades else None,
        _plural(len(dividends), "dividend", "dividends") if dividends else None,
        "weekly interest" if interest else None,
        "weekly interest and cashback" if deposits else None,
    ]
    return [Notification(
        key="synced:Trading 212", kind="synced", at=_utc(max(t.created_at for t in rows)),
        title=f"{_plural(len(rows), 'new transaction', 'new transactions')} from Trading 212",
        detail=", ".join(p for p in parts if p), link="/transactions",
    )]


def _broker(db: Session) -> list[Notification]:
    connection = broker_sync_service.get_connection(db)
    if connection is None or not connection.enabled:
        return []
    last_ok = _utc(connection.last_synced_at) if connection.last_synced_at else datetime(2000, 1, 1, tzinfo=timezone.utc)
    items = []
    unmapped = broker_sync_service.unmapped_instruments(connection)
    if unmapped:
        names = ", ".join(str(u.get("name") or u.get("isin")) for u in unmapped[:3])
        items.append(Notification(
            key="unmapped", kind="unmapped", at=last_ok,
            title=f"{_plural(len(unmapped), 'instrument is', 'instruments are')} waiting for an asset",
            detail=f"{names}: their Trading 212 transactions are held back until you link them.", link="/transactions",
        ))
    if connection.last_error:
        items.append(Notification(
            key="broker:error", kind="broker", at=last_ok, title="Trading 212 isn't syncing",
            detail=connection.last_error, link="/transactions",
        ))
    return items


def list_notifications(db: Session, since: datetime) -> list[Notification]:
    """Everything worth mentioning, newest first."""
    return sorted(_synced(db, since) + _broker(db), key=lambda n: n.at, reverse=True)
