from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.asset import DltJudgment
from app.models.transaction import TransactionType as T
from app.repositories import portfolio_asset_target_repo, portfolio_settings_repo
from app.routers import positions as positions_router
from app.services.rebalance import CASH_ID, Bucket, plan
from tests.test_summary_service import make_asset, make_txn, set_price

D = Decimal


def by_id(purchases):
    return {p.asset_id: p for p in purchases}


def test_new_money_goes_to_the_holdings_below_target_in_proportion_to_how_far_below():
    # Total 1,000 + 500 = 1,500. A wants 50% (750, has 600: 150 short), B wants 50% (750, has
    # 400: 350 short). 500 covers exactly both.
    buckets = [Bucket(1, D(600), D(50), D(10)), Bucket(2, D(400), D(50), D(20))]
    p = by_id(plan(buckets, D(1000), D(500), from_cash=False))
    assert (p[1].amount_eur, p[2].amount_eur) == (D(150), D(350))
    assert p[1].quantity == D(15)
    assert p[2].weight_after_pct == D(50)


def test_an_amount_smaller_than_the_shortfalls_is_shared_by_them_and_nothing_is_sold():
    # Total 1,000 + 100: A 60% wants 660, has 700 (over, gets nothing); B 20% wants 220, has
    # 100 (120 short); C 20% wants 220, has 200 (20 short). 100 split 120:20.
    buckets = [Bucket(1, D(700), D(60)), Bucket(2, D(100), D(20)), Bucket(3, D(200), D(20))]
    p = by_id(plan(buckets, D(1000), D(100), from_cash=False))
    assert p[1].amount_eur == D(0)
    assert p[2].amount_eur + p[3].amount_eur == D(100)
    assert p[2].amount_eur == D("85.72")  # 85.714..., the rounding cent goes to the largest
    assert p[1].quantity is None


def test_more_than_the_shortfalls_spreads_the_rest_over_the_targets():
    buckets = [Bucket(1, D(500), D(50)), Bucket(2, D(500), D(50))]
    p = by_id(plan(buckets, D(1000), D(200), from_cash=False))
    assert (p[1].amount_eur, p[2].amount_eur) == (D(100), D(100))


def test_cash_put_to_work_shrinks_cash_and_never_goes_back_to_cash():
    # 1,000 total: cash 400 (target 10%), A 600 (target 90%, wants 900). Investing 300 of the
    # cash: total stays 1,000, A gets all 300, cash ends at 100 = its target.
    buckets = [Bucket(CASH_ID, D(400), D(10)), Bucket(1, D(600), D(90))]
    p = by_id(plan(buckets, D(1000), D(300), from_cash=True))
    assert p[1].amount_eur == D(300)
    assert p[CASH_ID].amount_eur == D(0)
    assert p[CASH_ID].weight_after_pct == D(10)


def test_a_deposit_tops_up_cash_below_its_target():
    buckets = [Bucket(CASH_ID, D(0), D(10)), Bucket(1, D(1000), D(90))]
    p = by_id(plan(buckets, D(1000), D(100), from_cash=False))
    # Total 1,100: cash wants 110 (110 short), A wants 990 (over). All 100 stays cash.
    assert p[CASH_ID].amount_eur == D(100)


def test_nothing_to_plan_without_an_amount_or_targets():
    assert plan([], D(1000), D(100), False) == []
    assert plan([Bucket(1, D(10), D(100))], D(10), D(0), False) == []


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(positions_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _set_rating(db, asset, judgment):
    asset.dlt_judgment = judgment
    db.flush()


def test_the_endpoint_plans_from_the_positions_targets_and_dlt_ratings(client, db_session, portfolio_id):
    a, b, c = make_asset(db_session, "AAA"), make_asset(db_session, "BBB"), make_asset(db_session, "CCC")
    crit, unrated = make_asset(db_session, "CRT"), make_asset(db_session, "UNR")
    make_txn(db_session, portfolio_id, None, T.DEPOSIT, date(2025, 1, 1), total_eur=D(1700))
    for asset, qty in ((a, 6), (b, 4), (c, 2), (crit, 2), (unrated, 2)):
        make_txn(db_session, portfolio_id, asset, T.BUY, date(2025, 1, 2), quantity=D(qty), total_eur=D(qty * 100))
        set_price(db_session, asset, "100")
    _set_rating(db_session, a, DltJudgment.ATTRACTIVE)
    _set_rating(db_session, b, DltJudgment.NEUTRAL)
    _set_rating(db_session, c, DltJudgment.ATTRACTIVE)
    _set_rating(db_session, crit, DltJudgment.CRITICAL)
    for asset, target in ((a, 40), (b, 30), (crit, 20), (unrated, 10)):
        portfolio_asset_target_repo.set_target(db_session, portfolio_id, asset.id, D(target))
    portfolio_settings_repo.set_cash_target_weight_pct(db_session, portfolio_id, None)
    db_session.commit()

    body = client.get("/api/positions/rebalance", params={"portfolio_id": portfolio_id, "amount_eur": "100", "from_cash": "true"}).json()

    # Total 1,700 (100 cash). A wants 680 (80 short), B wants 510 (110 short). The Critical and
    # the unrated holding are short too, but get nothing.
    amounts = {p["ticker"]: D(p["amount_eur"]) for p in body["purchases"]}
    assert amounts == {"BBB": D("57.90"), "AAA": D("42.10")}  # the rounding cent goes to the largest
    assert [(p["ticker"], p["dlt_judgment"]) for p in body["purchases"]] == [("BBB", "neutral"), ("AAA", "attractive")]
    assert D(body["purchases"][0]["quantity"]) == D("0.579")
    assert body["left_out"] == [
        {"name": "CCC Inc", "dlt_judgment": "attractive", "reason": "no_target"},
        {"name": "CRT Inc", "dlt_judgment": "critical", "reason": "critical"},
        {"name": "UNR Inc", "dlt_judgment": None, "reason": "unrated"},
    ]
    assert D(body["cash_eur"]) == D(100)


def test_the_endpoint_refuses_more_cash_than_there_is(client, db_session, portfolio_id):
    make_txn(db_session, portfolio_id, None, T.DEPOSIT, date(2025, 1, 1), total_eur=D(50))
    db_session.commit()
    resp = client.get("/api/positions/rebalance", params={"portfolio_id": portfolio_id, "amount_eur": "100", "from_cash": "true"})
    assert resp.status_code == 400
    assert client.get("/api/positions/rebalance", params={"portfolio_id": portfolio_id, "amount_eur": "0"}).status_code == 422
