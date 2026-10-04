from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.asset import Asset
from app.models.transaction import Transaction, TransactionType
from app.repositories import portfolio_asset_target_repo
from app.routers import positions as positions_router


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(positions_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def make_txn(db, portfolio_id, asset, type_, d, quantity=None, total_eur=Decimal(0), price=None) -> Transaction:
    txn = Transaction(
        portfolio_id=portfolio_id, asset_id=asset.id if asset else None, date=d, type=type_,
        quantity=quantity, value_eur=total_eur, costs=Decimal(0), total_eur=total_eur, price=price,
    )
    db.add(txn)
    db.flush()
    return txn


def test_target_weight_shows_up_for_a_real_position(client, db_session, portfolio_id):
    asset = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.flush()
    portfolio_asset_target_repo.set_target(db_session, portfolio_id, asset.id, Decimal(15))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(1), total_eur=Decimal(100))
    db_session.commit()

    positions = client.get("/api/positions", params={"portfolio_id": portfolio_id}).json()

    acme = next(p for p in positions if p["ticker"] == "ACME")
    assert Decimal(acme["target_weight_pct"]) == Decimal(15)


def test_target_weight_is_null_by_default(client, db_session, portfolio_id):
    asset = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.flush()
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000))
    db_session.commit()

    positions = client.get("/api/positions", params={"portfolio_id": portfolio_id}).json()

    cash = next(p for p in positions if p["ticker"] == "CASH")
    assert cash["target_weight_pct"] is None


def test_cash_target_weight_round_trips_through_the_endpoint(client, db_session, portfolio_id):
    updated = client.put(
        "/api/positions/cash-target-weight", params={"portfolio_id": portfolio_id}, json={"target_weight_pct": "10"}
    )
    assert updated.status_code == 200

    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000))
    db_session.commit()

    positions = client.get("/api/positions", params={"portfolio_id": portfolio_id}).json()
    cash = next(p for p in positions if p["ticker"] == "CASH")
    assert Decimal(cash["target_weight_pct"]) == Decimal(10)


def test_cash_target_weight_past_100_percent_is_a_400(client, db_session, portfolio_id):
    asset = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.flush()
    portfolio_asset_target_repo.set_target(db_session, portfolio_id, asset.id, Decimal(95))
    db_session.commit()

    response = client.put(
        "/api/positions/cash-target-weight", params={"portfolio_id": portfolio_id}, json={"target_weight_pct": "10"}
    )

    assert response.status_code == 400


def test_target_weight_drift_for_cash_against_the_whole_portfolio(client, db_session, portfolio_id):
    # Cash-only portfolio keeps this deterministic without mocking a price feed: total value
    # is exactly the deposit, so cash sits at 100% weight against its 10% target.
    updated = client.put(
        "/api/positions/cash-target-weight", params={"portfolio_id": portfolio_id}, json={"target_weight_pct": "10"}
    )
    assert updated.status_code == 200
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000))
    db_session.commit()

    cash = next(p for p in client.get("/api/positions", params={"portfolio_id": portfolio_id}).json() if p["ticker"] == "CASH")

    assert Decimal(cash["target_weight_diff_pct"]) == Decimal(90)  # 100% actual - 10% target
    assert Decimal(cash["target_weight_diff_eur"]) == Decimal(900)  # 1000 - (10% of 1000)


def test_target_weight_drift_for_a_real_position(client, db_session, portfolio_id):
    asset = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.flush()
    portfolio_asset_target_repo.set_target(db_session, portfolio_id, asset.id, Decimal(15))
    # price=60 gives last_txn_price_native a value, so the position values deterministically
    # (60 * 2 = 120 EUR) without needing a live/cached price feed.
    # Deposit covers the buy's own 100 EUR cash outflow plus the 880 that should remain,
    # since cash is derived from the whole ledger (a BUY spends cash, it doesn't sit outside it).
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(980))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(2), total_eur=Decimal(100), price=Decimal(60))
    db_session.commit()

    acme = next(p for p in client.get("/api/positions", params={"portfolio_id": portfolio_id}).json() if p["ticker"] == "ACME")

    # total value = 120 (position) + 880 (cash) = 1000; weight = 12%, target = 15%.
    assert Decimal(acme["target_weight_pct"]) == Decimal(15)
    assert Decimal(acme["weight_pct"]) == Decimal(12)
    assert Decimal(acme["target_weight_diff_pct"]) == Decimal(-3)  # underweight
    assert Decimal(acme["target_weight_diff_eur"]) == Decimal(-30)  # 120 - (15% of 1000)


def test_target_weight_drift_is_null_without_a_target(client, db_session, portfolio_id):
    asset = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.flush()
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(1), total_eur=Decimal(100), price=Decimal(100))
    db_session.commit()

    acme = next(p for p in client.get("/api/positions", params={"portfolio_id": portfolio_id}).json() if p["ticker"] == "ACME")

    assert acme["target_weight_pct"] is None
    assert acme["target_weight_diff_pct"] is None
    assert acme["target_weight_diff_eur"] is None


def test_positions_are_scoped_to_the_requested_portfolio(client, db_session, portfolio_id):
    from app.models.portfolio import Portfolio

    other = Portfolio(name="Other Portfolio")
    db_session.add(other)
    db_session.flush()

    asset = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.flush()
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(1), total_eur=Decimal(100))
    make_txn(db_session, other.id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(50))
    db_session.commit()

    mine = client.get("/api/positions", params={"portfolio_id": portfolio_id}).json()
    theirs = client.get("/api/positions", params={"portfolio_id": other.id}).json()

    assert {p["ticker"] for p in mine} == {"ACME", "CASH"}
    assert {p["ticker"] for p in theirs} == {"CASH"}
    assert Decimal(next(p for p in theirs if p["ticker"] == "CASH")["market_value_eur"]) == Decimal(50)


def test_dlt_judgment_is_null_when_theres_no_coverage(client, db_session, portfolio_id):
    """Null, not a fake "neutral" -- no DLT coverage and an explicit neutral call are different
    facts even though they used to render identically on the wire (see docs/adr and
    stock-analyst.md)."""
    asset = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.flush()
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(1), total_eur=Decimal(100))
    db_session.commit()

    positions = client.get("/api/positions", params={"portfolio_id": portfolio_id}).json()

    acme = next(p for p in positions if p["ticker"] == "ACME")
    cash = next(p for p in positions if p["ticker"] == "CASH")
    assert acme["dlt_judgment"] is None
    assert cash["dlt_judgment"] is None  # cash isn't a security DLT would ever rate


def test_dlt_judgment_reflects_an_explicit_rating(client, db_session, portfolio_id):
    from app.models.asset import DltJudgment

    asset = Asset(ticker="ACME", name="Acme", asset_class="equity", native_currency="EUR", dlt_judgment=DltJudgment.CRITICAL)
    db_session.add(asset)
    db_session.flush()
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(1), total_eur=Decimal(100))
    db_session.commit()

    positions = client.get("/api/positions", params={"portfolio_id": portfolio_id}).json()

    acme = next(p for p in positions if p["ticker"] == "ACME")
    assert acme["dlt_judgment"] == "critical"
