from datetime import date, timedelta
from decimal import Decimal

from app.models.transaction import Transaction, TransactionType
from app.repositories import transaction_repo
from app.services.performance_service import performance_service


def make_deposit(db, portfolio_id, d, total_eur) -> Transaction:
    txn = Transaction(
        portfolio_id=portfolio_id, asset_id=None, date=d, type=TransactionType.DEPOSIT,
        value_eur=Decimal(0), costs=Decimal(0), total_eur=total_eur,
    )
    db.add(txn)
    db.flush()
    return txn


def test_full_series_is_flat_cash_between_deposits_with_no_assets_held(db_session, portfolio_id):
    # Pure cash, no assets -> no price-provider calls, fully deterministic.
    inception = date.today() - timedelta(days=100)
    mid = date.today() - timedelta(days=50)
    make_deposit(db_session, portfolio_id, inception, Decimal(1000))
    make_deposit(db_session, portfolio_id, mid, Decimal(500))
    db_session.commit()

    series = performance_service.get_full_series(db_session, portfolio_id)

    assert series[0].date == inception
    assert series[0].value_eur == Decimal(1000)
    # the day before the second deposit is still just the first deposit
    day_before_mid = next(p for p in series if p.date == mid - timedelta(days=1))
    assert day_before_mid.value_eur == Decimal(1000)
    assert series[-1].date == date.today()
    assert series[-1].value_eur == Decimal(1500)


def test_return_is_zero_for_pure_cash_deposits_with_no_market_exposure(db_session, portfolio_id):
    # A deposit contributes to portfolio value but is not investment performance — the
    # time-weighted series should back it out and report 0% for cash sitting still.
    inception = date.today() - timedelta(days=100)
    mid = date.today() - timedelta(days=50)
    make_deposit(db_session, portfolio_id, inception, Decimal(1000))
    make_deposit(db_session, portfolio_id, mid, Decimal(500))
    db_session.commit()

    result = performance_service.get_range(db_session, portfolio_id, "Max")

    assert result["start_value_eur"] == Decimal(1000)
    assert result["end_value_eur"] == Decimal(1500)
    assert result["change_eur"] == Decimal(0)
    assert result["change_pct"] == Decimal(0)


def test_a_withdrawal_without_asset_growth_also_nets_to_zero_return(db_session, portfolio_id):
    inception = date.today() - timedelta(days=60)
    withdraw_day = date.today() - timedelta(days=20)
    make_deposit(db_session, portfolio_id, inception, Decimal(1000))
    txn = Transaction(
        portfolio_id=portfolio_id, asset_id=None, date=withdraw_day, type=TransactionType.WITHDRAW,
        value_eur=Decimal(0), costs=Decimal(0), total_eur=Decimal(300),
    )
    db_session.add(txn)
    db_session.commit()

    result = performance_service.get_range(db_session, portfolio_id, "Max")

    assert result["start_value_eur"] == Decimal(1000)
    assert result["end_value_eur"] == Decimal(700)
    assert result["change_eur"] == Decimal(0)
    assert result["change_pct"] == Decimal(0)


def test_deposit_is_not_counted_as_investment_return(db_session, portfolio_id):
    """The guarantee that makes benchmark comparison honest: a mid-period deposit inflates
    portfolio value but must not show up as return. Here the only real performance is the
    asset doubling (+100%), while €1000 is paid in halfway through."""
    from app.models.asset import Asset
    from app.models.price_history import PriceHistory

    inception = date.today() - timedelta(days=10)
    # No yahoo_symbol -> the price provider is never consulted, so this stays offline.
    asset = Asset(ticker="TEST", name="Test Co", asset_class="equity", native_currency="EUR")
    db_session.add(asset)
    db_session.flush()

    # 10 units bought at €10; price doubles to €20 by the end of the window.
    for offset in range(11):
        db_session.add(
            PriceHistory(
                asset_id=asset.id,
                date=inception + timedelta(days=offset),
                close_price=Decimal(10) if offset < 5 else Decimal(20),
            )
        )
    make_deposit(db_session, portfolio_id, inception, Decimal(100))
    db_session.add(
        Transaction(
            portfolio_id=portfolio_id, asset_id=asset.id, date=inception, type=TransactionType.BUY,
            quantity=Decimal(10), price=Decimal(10),
            value_eur=Decimal(100), costs=Decimal(0), total_eur=Decimal(100),
        )
    )
    # Cash paid in after the price move, so it can't be confused with performance.
    make_deposit(db_session, portfolio_id, inception + timedelta(days=8), Decimal(1000))
    db_session.commit()

    result = performance_service.get_range(db_session, portfolio_id, "Max")

    # Value grew from €100 to €1200, but only the doubling is return.
    assert result["end_value_eur"] == Decimal(1200)
    assert result["change_pct"] is not None
    assert round(float(result["change_pct"])) == 100
    assert round(float(result["points"][-1]["return_pct"])) == 100


def test_full_series_is_reused_across_calls_with_no_intervening_write(db_session, portfolio_id, monkeypatch):
    make_deposit(db_session, portfolio_id, date.today() - timedelta(days=5), Decimal(1000))
    db_session.commit()

    calls = []
    original = transaction_repo.list_all_transactions
    monkeypatch.setattr(
        transaction_repo, "list_all_transactions",
        lambda db, portfolio_id: (calls.append(1) or original(db, portfolio_id)),
    )

    first = performance_service.get_full_series(db_session, portfolio_id)
    second = performance_service.get_full_series(db_session, portfolio_id)

    assert first == second
    # The second call must be served from cache, not replay the ledger again.
    assert len(calls) == 1


def test_full_series_cache_is_invalidated_after_a_write(db_session, portfolio_id):
    make_deposit(db_session, portfolio_id, date.today() - timedelta(days=5), Decimal(1000))
    db_session.commit()

    first = performance_service.get_full_series(db_session, portfolio_id)
    assert first[-1].value_eur == Decimal(1000)

    make_deposit(db_session, portfolio_id, date.today(), Decimal(500))
    db_session.commit()
    performance_service.invalidate_cache(portfolio_id)

    second = performance_service.get_full_series(db_session, portfolio_id)
    assert second[-1].value_eur == Decimal(1500)


def test_performance_series_is_isolated_per_portfolio(db_session, portfolio_id):
    from app.models.portfolio import Portfolio

    other = Portfolio(name="Other Portfolio")
    db_session.add(other)
    db_session.flush()

    make_deposit(db_session, portfolio_id, date.today() - timedelta(days=5), Decimal(1000))
    make_deposit(db_session, other.id, date.today() - timedelta(days=5), Decimal(200))
    db_session.commit()

    mine = performance_service.get_full_series(db_session, portfolio_id)
    theirs = performance_service.get_full_series(db_session, other.id)

    assert mine[-1].value_eur == Decimal(1000)
    assert theirs[-1].value_eur == Decimal(200)


def test_the_money_weighted_return_rides_along_and_is_zero_for_cash_sitting_still(db_session, portfolio_id):
    # Relative dates, but the outcome doesn't depend on which day it is: no prices are involved.
    make_deposit(db_session, portfolio_id, date.today() - timedelta(days=400), Decimal(1000))
    make_deposit(db_session, portfolio_id, date.today() - timedelta(days=100), Decimal(500))
    db_session.commit()

    full = performance_service.get_range(db_session, portfolio_id, "Max")
    ytd = performance_service.get_range(db_session, portfolio_id, "1M")
    day = performance_service.get_range(db_session, portfolio_id, "1D")

    assert abs(full["mwr_pct"]) < Decimal("0.0001") and abs(full["mwr_yearly_pct"]) < Decimal("0.0001")
    assert ytd["mwr_yearly_pct"] is None
    assert (day["mwr_pct"], day["mwr_yearly_pct"]) == (None, None)


def _held_asset_with_a_live_quote(db, portfolio_id, monkeypatch, quote: Decimal):
    """10 units bought at €10 five days ago, closing at €10 every day since, plus a live quote
    taken this afternoon. No yahoo_symbol, so nothing reaches the provider."""
    from datetime import datetime, time

    from app.models.asset import Asset
    from app.models.price_history import PriceHistory
    from app.services.price_service import price_service

    today = date.today()
    now = datetime.combine(today, time(14, 0))
    monkeypatch.setattr(price_service, "clock", lambda: now)
    inception = today - timedelta(days=5)
    asset = Asset(
        ticker="LIVE", name="Live Co", asset_class="equity", native_currency="EUR",
        quote_price=quote, quoted_at=now - timedelta(minutes=20), quote_checked_at=now - timedelta(minutes=5),
    )
    db.add(asset)
    db.flush()
    for offset in range(6):
        db.add(PriceHistory(asset_id=asset.id, date=inception + timedelta(days=offset), close_price=Decimal(10)))
    make_deposit(db, portfolio_id, inception, Decimal(100))
    db.add(
        Transaction(
            portfolio_id=portfolio_id, asset_id=asset.id, date=inception, type=TransactionType.BUY,
            quantity=Decimal(10), price=Decimal(10),
            value_eur=Decimal(100), costs=Decimal(0), total_eur=Decimal(100),
        )
    )
    db.commit()
    return asset


def test_todays_point_is_repriced_at_the_live_quote(db_session, portfolio_id, monkeypatch):
    _held_asset_with_a_live_quote(db_session, portfolio_id, monkeypatch, Decimal(11))

    result = performance_service.get_range(db_session, portfolio_id, "1D")

    # Yesterday at the €10 close, today at the €11 quote: the 1D change is the intraday move.
    assert result["start_value_eur"] == Decimal(100)
    assert result["end_value_eur"] == Decimal(110)
    assert result["change_eur"] == Decimal(10)
    assert result["change_pct"] == Decimal(10)


def test_the_closes_only_series_and_earlier_days_ignore_the_live_quote(db_session, portfolio_id, monkeypatch):
    _held_asset_with_a_live_quote(db_session, portfolio_id, monkeypatch, Decimal(11))

    closes = performance_service.get_full_series(db_session, portfolio_id)
    live = performance_service.get_live_series(db_session, portfolio_id)

    assert closes[-1].value_eur == Decimal(100)
    assert live[-1].value_eur == Decimal(110)
    assert live[:-1] == closes[:-1]
    # And the cached series itself was left alone for the next request.
    assert performance_service.get_full_series(db_session, portfolio_id)[-1].value_eur == Decimal(100)


def test_a_quote_gone_stale_leaves_today_on_the_close(db_session, portfolio_id, monkeypatch):
    from app.services.price_service import price_service

    asset = _held_asset_with_a_live_quote(db_session, portfolio_id, monkeypatch, Decimal(11))
    later = asset.quote_checked_at + timedelta(hours=3)
    monkeypatch.setattr(price_service, "clock", lambda: later)

    result = performance_service.get_range(db_session, portfolio_id, "1D")

    assert result["end_value_eur"] == Decimal(100)


def test_the_live_series_survives_the_request_that_cached_it(db_session, portfolio_id, monkeypatch):
    # The series is cached across requests, but each request has its own session, committed
    # and closed at the end (app.db.get_db). The cache must not hold on to that session's rows.
    from sqlalchemy.orm import sessionmaker

    _held_asset_with_a_live_quote(db_session, portfolio_id, monkeypatch, Decimal(11))
    performance_service.get_range(db_session, portfolio_id, "1D")
    db_session.commit()
    db_session.close()

    next_request = sessionmaker(bind=db_session.get_bind())()
    try:
        result = performance_service.get_range(next_request, portfolio_id, "1D")
    finally:
        next_request.close()

    assert result["end_value_eur"] == Decimal(110)
