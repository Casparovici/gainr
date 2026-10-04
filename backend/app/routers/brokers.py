"""gainr's broker sync: Trading 212's fills, dividends and weekly interest/cashback into one
portfolio -- see docs/adr/0031-trading212-sync.md."""

from datetime import date as date_
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import broker_sync_repo, portfolio_repo
from app.schemas.broker import BrokerSettingsUpdate, BrokerStatusOut, BrokerSyncResultOut, BrokerUnmappedOut, NotificationOut
from app.services import broker_sync_service, gainr_notification_service

router = APIRouter(prefix="/api/brokers", tags=["brokers"])


def _connection_or_404(db: Session):
    connection = broker_sync_service.get_connection(db)
    if connection is None:
        raise HTTPException(status_code=404, detail="Trading 212 isn't set up in this database")
    return connection


def _unmapped(raw: list[dict]) -> list[BrokerUnmappedOut]:
    out: list[BrokerUnmappedOut] = []
    for item in raw:
        try:
            out.append(BrokerUnmappedOut(**item))
        except (TypeError, ValueError):
            continue  # a row from an older format -- the next run rewrites the list
    return out


def _status(db: Session) -> BrokerStatusOut:
    c = _connection_or_404(db)
    return BrokerStatusOut(
        configured=broker_sync_service.is_configured(),
        enabled=c.enabled,
        since=c.since,
        portfolio_id=c.portfolio_id,
        # Stored naive in UTC; sent with the zone so the browser shows its own local time.
        last_synced_at=c.last_synced_at.replace(tzinfo=timezone.utc) if c.last_synced_at else None,
        last_error=c.last_error,
        unmapped=_unmapped(broker_sync_service.unmapped_instruments(c)),
    )


@router.get("/trading212", response_model=BrokerStatusOut)
def trading212_status(db: Session = Depends(get_db)):
    return _status(db)


@router.put("/trading212", response_model=BrokerStatusOut)
def update_trading212(payload: BrokerSettingsUpdate, db: Session = Depends(get_db)):
    connection = _connection_or_404(db)
    portfolio_id = payload.portfolio_id if payload.portfolio_id is not None else connection.portfolio_id
    if portfolio_id is not None and portfolio_repo.get_portfolio(db, portfolio_id) is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    if payload.enabled and portfolio_id is None:
        raise HTTPException(status_code=422, detail="Pick the portfolio Trading 212 books into")
    since = payload.since or connection.since
    if payload.enabled and since is None:
        since = date_.today()
    broker_sync_repo.update_connection(db, connection, enabled=payload.enabled, since=since, portfolio_id=portfolio_id)
    db.commit()
    return _status(db)


@router.post("/trading212/sync", response_model=BrokerSyncResultOut)
def sync_trading212(db: Session = Depends(get_db)):
    """Syncs now. Takes up to a couple of minutes when a week's interest is due: Trading 212
    writes the export that carries it in the background."""
    _connection_or_404(db)
    result = broker_sync_service.sync(db)
    db.commit()
    return BrokerSyncResultOut(
        booked=result.booked, matched=result.matched, deposits=result.deposits,
        unmapped=_unmapped(result.unmapped), problems=result.problems,
    )


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(since: datetime | None = None, db: Session = Depends(get_db)):
    """What's new in gainr since `since` (when this device last opened the bell), newest first. A
    device that has never looked sees the last week."""
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=7)
    elif since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return [NotificationOut(**vars(n)) for n in gainr_notification_service.list_notifications(db, since)]
