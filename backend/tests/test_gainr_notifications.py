from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.asset import Asset
from app.models.broker_sync import BrokerConnection
from app.models.transaction import TransactionType
from app.repositories import transaction_repo
from app.services import gainr_notification_service

TT = TransactionType
NOW = datetime(2026, 10, 5, 7, 0)
SINCE = (NOW - timedelta(days=1)).replace(tzinfo=timezone.utc)


def txn(db, portfolio_id, type_, ref, created=NOW - timedelta(hours=2), notes="Trading 212", asset=None):
    t = transaction_repo.create_transaction(
        db, portfolio_id=portfolio_id, asset_id=asset.id if asset else None, date=created.date(), type=type_,
        total_eur=Decimal("10"), value_eur=Decimal("10"), broker="Trading212", notes=notes, source_ref=ref,
    )
    t.created_at = created
    db.flush()
    return t


def test_what_the_trading_212_sync_booked_is_summarised(db_session, portfolio_id):
    asset = Asset(ticker="TDIV", name="TDIV")
    db_session.add(asset)
    db_session.flush()
    txn(db_session, portfolio_id, TT.BUY, "t212:fill:1", notes="Trading 212 · auto-invest", asset=asset)
    txn(db_session, portfolio_id, TT.BUY, "t212:fill:2", asset=asset)
    txn(db_session, portfolio_id, TT.DIVIDEND, "t212:dividend:a", asset=asset)
    txn(db_session, portfolio_id, TT.DEPOSIT, "t212:week:2026-W40")
    txn(db_session, portfolio_id, TT.INTEREST, "t212:week:2026-W41")
    txn(db_session, portfolio_id, TT.BUY, "t212:fill:old", created=NOW - timedelta(days=3), asset=asset)  # already seen
    txn(db_session, portfolio_id, TT.BUY, None, asset=asset)  # typed in by hand

    (item,) = gainr_notification_service.list_notifications(db_session, SINCE)

    assert item.title == "5 new transactions from Trading 212"
    assert item.detail == "2 buys and sells (1 auto-invest), 1 dividend, weekly interest, weekly interest and cashback"


def test_held_back_instruments_and_a_failing_sync_stay_listed(db_session):
    db_session.add(BrokerConnection(
        broker="Trading212", enabled=True, last_synced_at=datetime(2026, 10, 3, 5, 0),
        last_error="Trading 212 refused the API key.",
        unmapped='[{"isin": "IE000J80JTL1", "name": "Smart Grid", "ticker": "GRIDd_EQ", "currency": "EUR", "records": 2, "first_date": "2026-10-02"}]',
    ))
    db_session.flush()

    items = {n.key: n for n in gainr_notification_service.list_notifications(db_session, SINCE)}

    assert items["unmapped"].title == "1 instrument is waiting for an asset"
    assert "Smart Grid" in items["unmapped"].detail
    assert items["broker:error"].detail == "Trading 212 refused the API key."
    assert items["broker:error"].at == datetime(2026, 10, 3, 5, 0, tzinfo=timezone.utc)


def test_a_switched_off_sync_and_a_quiet_day_say_nothing(db_session):
    db_session.add(BrokerConnection(broker="Trading212", enabled=False, last_error="old"))
    db_session.flush()

    assert gainr_notification_service.list_notifications(db_session, SINCE) == []
