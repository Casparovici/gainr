from datetime import date, timedelta
from decimal import Decimal

from app.models.asset import Asset
from app.models.price_history import PriceHistory
from app.models.transaction import Transaction, TransactionType
from app.services.summary_service import summary_service


def make_asset(db, ticker="ACME") -> Asset:
    # No yahoo_symbol: every price lookup then resolves out of the seeded price_history cache
    # below and no provider (network) call is made, so these tests are deterministic.
    asset = Asset(ticker=ticker, name=f"{ticker} Inc", asset_class="equity", native_currency="EUR")
    db.add(asset)
    db.flush()
    return asset


def set_price(db, asset, close_price, on_date=None) -> None:
    db.add(PriceHistory(asset_id=asset.id, date=on_date or date.today(), close_price=Decimal(close_price)))
    db.flush()


def make_txn(db, portfolio_id, asset, type_, d, quantity=None, total_eur=Decimal(0), broker=None, to_broker=None) -> Transaction:
    txn = Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset.id if asset else None,
        date=d,
        type=type_,
        quantity=quantity,
        value_eur=total_eur,
        costs=Decimal(0),
        total_eur=total_eur,
        broker=broker,
        to_broker=to_broker,
    )
    db.add(txn)
    db.flush()
    return txn


def test_unrealized_pnl_marks_open_positions_to_the_latest_close(db_session, portfolio_id):
    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(2000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(1000))
    set_price(db_session, asset, Decimal(130))
    db_session.commit()

    summary = summary_service.get_summary(db_session, portfolio_id)

    # 10 units held at 130 = 1300 against a 1000 cost basis
    assert summary["unrealized_pnl_eur"] == Decimal(300)
    assert summary["unrealized_pnl_pct"] == Decimal(30)
    assert summary["realized_pnl_eur"] == Decimal(0)


def test_realized_pnl_counts_partial_sells_on_positions_that_are_still_open(db_session, portfolio_id):
    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(2000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(1000))
    # cost 100/unit; selling 4 at 150 banks 200
    make_txn(db_session, portfolio_id, asset, TransactionType.SELL, date(2024, 2, 1), quantity=Decimal(4), total_eur=Decimal(600))
    set_price(db_session, asset, Decimal(150))
    db_session.commit()

    summary = summary_service.get_summary(db_session, portfolio_id)

    assert summary["realized_pnl_eur"] == Decimal(200)
    # 6 units left at 150 = 900, against the 600 of cost basis still attached to them
    assert summary["unrealized_pnl_eur"] == Decimal(300)


def test_realized_pnl_includes_fully_closed_positions(db_session, portfolio_id):
    open_asset = make_asset(db_session, ticker="OPEN")
    closed_asset = make_asset(db_session, ticker="GONE")
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(5000))
    make_txn(db_session, portfolio_id, open_asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, closed_asset, TransactionType.BUY, date(2024, 1, 3), quantity=Decimal(5), total_eur=Decimal(500))
    make_txn(db_session, portfolio_id, closed_asset, TransactionType.SELL, date(2024, 3, 1), quantity=Decimal(5), total_eur=Decimal(800))
    set_price(db_session, open_asset, Decimal(110))
    db_session.commit()

    summary = summary_service.get_summary(db_session, portfolio_id)

    assert summary["realized_pnl_eur"] == Decimal(300)
    assert summary["unrealized_pnl_eur"] == Decimal(100)


def test_dividends_are_cash_income_and_land_in_neither_gain_bucket(db_session, portfolio_id):
    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(2000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, asset, TransactionType.DIVIDEND, date(2024, 4, 1), total_eur=Decimal(50))
    set_price(db_session, asset, Decimal(100))
    db_session.commit()

    summary = summary_service.get_summary(db_session, portfolio_id)

    assert summary["realized_pnl_eur"] == Decimal(0)
    assert summary["unrealized_pnl_eur"] == Decimal(0)
    # it does still show up as cash, and therefore in the total return over what was paid in
    assert summary["cash_eur"] == Decimal(1050)
    assert summary["total_return_eur"] == Decimal(50)


def test_summary_includes_cash_split_by_broker(db_session, portfolio_id):
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000), broker="DEGIRO")
    make_txn(db_session, portfolio_id, None, TransactionType.TRANSFER, date(2024, 1, 2), total_eur=Decimal(300), broker="DEGIRO", to_broker="IBKR")
    db_session.commit()

    summary = summary_service.get_summary(db_session, portfolio_id)

    assert summary["cash_by_broker_eur"] == {"DEGIRO": Decimal(700), "IBKR": Decimal(300)}
    assert sum(summary["cash_by_broker_eur"].values()) == summary["cash_eur"] == Decimal(1000)


def test_unvalued_position_is_left_out_of_the_unrealized_percentage_base(db_session, portfolio_id):
    valued = make_asset(db_session, ticker="PRICED")
    unpriced = make_asset(db_session, ticker="NOPRICE")
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(5000))
    make_txn(db_session, portfolio_id, valued, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, unpriced, TransactionType.BUY, date(2024, 1, 3), quantity=Decimal(10), total_eur=Decimal(3000))
    set_price(db_session, valued, Decimal(120), on_date=date.today() - timedelta(days=1))
    db_session.commit()

    summary = summary_service.get_summary(db_session, portfolio_id)

    # The €3000 holding has no price at all, so measuring the €200 gain against its cost too
    # would understate the return on what we could actually value.
    assert summary["unrealized_pnl_eur"] == Decimal(200)
    assert summary["unrealized_pnl_pct"] == Decimal(20)


def test_get_summary_does_not_refetch_the_ledger_via_get_positions(db_session, portfolio_id, monkeypatch):
    """get_summary already fetches the transaction ledger itself; it must reuse that fetch to
    build positions (via get_positions_from) rather than having position_service fetch it
    again internally (via get_positions)."""
    from app.services.position_service import position_service

    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(2000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(1000))
    set_price(db_session, asset, Decimal(120))
    db_session.commit()

    def fail_if_called(db, portfolio_id):
        raise AssertionError("get_summary should call get_positions_from, not get_positions")

    monkeypatch.setattr(position_service, "get_positions", fail_if_called)

    summary_service.get_summary(db_session, portfolio_id)


def test_summary_is_isolated_per_portfolio(db_session, portfolio_id):
    from app.models.portfolio import Portfolio

    other = Portfolio(name="Other Portfolio")
    db_session.add(other)
    db_session.flush()

    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000))
    make_txn(db_session, other.id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(200))
    db_session.commit()

    mine = summary_service.get_summary(db_session, portfolio_id)
    theirs = summary_service.get_summary(db_session, other.id)

    assert mine["cash_eur"] == Decimal(1000)
    assert theirs["cash_eur"] == Decimal(200)
