from datetime import date
from decimal import Decimal

from app.models.asset import Asset
from app.models.price_history import PriceHistory
from app.models.transaction import Transaction, TransactionType
from app.repositories import portfolio_asset_target_repo, transaction_repo
from app.services.position_service import cash_balance_by_broker_eur, cash_balance_eur, net_invested_eur, position_service


def make_asset(db, ticker="ACME") -> Asset:
    asset = Asset(ticker=ticker, name=f"{ticker} Inc", asset_class="equity", native_currency="EUR")
    db.add(asset)
    db.flush()
    return asset


def make_txn(db, portfolio_id, asset, type_, d, quantity=None, total_eur=Decimal(0), price=None, broker=None, to_broker=None) -> Transaction:
    txn = Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset.id if asset else None,
        date=d,
        type=type_,
        quantity=quantity,
        price=price,
        value_eur=total_eur,
        costs=Decimal(0),
        total_eur=total_eur,
        broker=broker,
        to_broker=to_broker,
    )
    db.add(txn)
    db.flush()
    return txn


def test_weighted_average_cost_basis_accumulates_across_buys(db_session, portfolio_id):
    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(10), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 2, 1), quantity=Decimal(10), total_eur=Decimal(1200))
    db_session.commit()

    active, closed = position_service.get_positions(db_session, portfolio_id)

    assert closed == []
    assert len(active) == 1
    position = active[0]
    assert position.quantity == Decimal(20)
    assert position.cost_basis_eur == Decimal(2200)  # avg cost/unit = 110


def test_partial_sell_realizes_pnl_at_weighted_average_cost(db_session, portfolio_id):
    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(10), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 2, 1), quantity=Decimal(10), total_eur=Decimal(1200))
    # avg cost/unit at this point = 2200/20 = 110
    make_txn(db_session, portfolio_id, asset, TransactionType.SELL, date(2024, 3, 1), quantity=Decimal(5), total_eur=Decimal(700))
    db_session.commit()

    active, _closed = position_service.get_positions(db_session, portfolio_id)

    position = active[0]
    assert position.quantity == Decimal(15)
    assert position.cost_basis_eur == Decimal(2200) - Decimal(5) * Decimal(110)  # 1650
    # realized pnl isn't on the active Position dataclass; verify via a full close below.


def test_fully_sold_position_moves_to_closed_with_correct_realized_pnl(db_session, portfolio_id):
    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(10), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, asset, TransactionType.SELL, date(2024, 6, 1), quantity=Decimal(10), total_eur=Decimal(1300))
    db_session.commit()

    active, closed = position_service.get_positions(db_session, portfolio_id)

    assert active == []
    assert len(closed) == 1
    c = closed[0]
    assert c.total_bought_eur == Decimal(1000)
    assert c.total_sold_eur == Decimal(1300)
    assert c.realized_pnl_eur == Decimal(300)
    assert c.first_buy_date == date(2024, 1, 1)
    assert c.last_sell_date == date(2024, 6, 1)


def test_staking_reward_has_zero_cost_basis_and_is_pure_gain_on_sale(db_session, portfolio_id):
    asset = make_asset(db_session, ticker="ETH")
    make_txn(db_session, portfolio_id, asset, TransactionType.STAKING, date(2024, 1, 1), quantity=Decimal("0.5"))
    make_txn(db_session, portfolio_id, asset, TransactionType.SELL, date(2024, 2, 1), quantity=Decimal("0.5"), total_eur=Decimal(150))
    db_session.commit()

    active, closed = position_service.get_positions(db_session, portfolio_id)

    assert active == []
    assert len(closed) == 1
    # cost basis of the staked reward is 0, so the entire €150 proceeds is realized gain
    assert closed[0].realized_pnl_eur == Decimal(150)
    assert closed[0].total_bought_eur == Decimal(0)


def test_dividend_does_not_affect_position_quantity_or_cost_basis(db_session, portfolio_id):
    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(10), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, asset, TransactionType.DIVIDEND, date(2024, 4, 1), total_eur=Decimal(20))
    db_session.commit()

    active, _closed = position_service.get_positions(db_session, portfolio_id)

    assert active[0].quantity == Decimal(10)
    assert active[0].cost_basis_eur == Decimal(1000)


def test_cash_balance_sign_convention_across_all_transaction_types(db_session, portfolio_id):
    asset = make_asset(db_session)
    transactions = [
        make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000)),
        make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(1), total_eur=Decimal(300)),
        make_txn(db_session, portfolio_id, asset, TransactionType.SELL, date(2024, 1, 3), quantity=Decimal(1), total_eur=Decimal(350)),
        make_txn(db_session, portfolio_id, None, TransactionType.INTEREST, date(2024, 1, 4), total_eur=Decimal(5)),
        make_txn(db_session, portfolio_id, asset, TransactionType.DIVIDEND, date(2024, 1, 5), total_eur=Decimal(10)),
        make_txn(db_session, portfolio_id, None, TransactionType.BROKER_FEE, date(2024, 1, 6), total_eur=Decimal(2)),
        make_txn(db_session, portfolio_id, None, TransactionType.WITHDRAW, date(2024, 1, 7), total_eur=Decimal(400)),
    ]
    db_session.commit()

    # 1000 - 300 + 350 + 5 + 10 - 2 - 400 = 663
    assert cash_balance_eur(transactions) == Decimal(663)


def test_cash_balance_by_broker_attributes_each_movement_to_its_own_broker(db_session, portfolio_id):
    asset = make_asset(db_session)
    transactions = [
        make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000), broker="DEGIRO"),
        make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(1), total_eur=Decimal(300), broker="DEGIRO"),
        make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 3), total_eur=Decimal(500), broker="IBKR"),
    ]
    db_session.commit()

    assert cash_balance_by_broker_eur(transactions) == {"DEGIRO": Decimal(700), "IBKR": Decimal(500)}


def test_cash_balance_by_broker_buckets_a_missing_broker_as_unassigned(db_session, portfolio_id):
    transactions = [make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(50))]
    db_session.commit()

    assert cash_balance_by_broker_eur(transactions) == {"Unassigned": Decimal(50)}


def test_transfer_moves_the_balance_between_brokers_and_nets_to_zero_overall(db_session, portfolio_id):
    transactions = [
        make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000), broker="DEGIRO"),
        make_txn(db_session, portfolio_id, None, TransactionType.TRANSFER, date(2024, 1, 2), total_eur=Decimal(400), broker="DEGIRO", to_broker="IBKR"),
    ]
    db_session.commit()

    by_broker = cash_balance_by_broker_eur(transactions)
    assert by_broker == {"DEGIRO": Decimal(600), "IBKR": Decimal(400)}
    assert sum(by_broker.values()) == cash_balance_eur(transactions) == Decimal(1000)


def test_batched_valuations_match_per_position_valuation(db_session, portfolio_id):
    eur_asset = make_asset(db_session, ticker="EURCO")
    usd_asset = Asset(ticker="USDCO", name="USD Co", asset_class="equity", native_currency="USD")
    db_session.add(usd_asset)
    db_session.flush()

    make_txn(db_session, portfolio_id, eur_asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(10), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, usd_asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(5), total_eur=Decimal(500))
    db_session.add(PriceHistory(asset_id=eur_asset.id, date=date.today(), close_price=Decimal(120)))
    db_session.add(PriceHistory(asset_id=usd_asset.id, date=date.today(), close_price=Decimal(80)))
    db_session.commit()

    active, _closed = position_service.get_positions(db_session, portfolio_id)
    batched = position_service.valuations(db_session, active)

    for position in active:
        single = position_service.valuation(db_session, position)
        assert batched[position.asset_id].market_value_eur == single.market_value_eur
        assert batched[position.asset_id].price_native == single.price_native
        assert batched[position.asset_id].price_stale == single.price_stale


def test_net_invested_counts_only_deposits_and_withdrawals(db_session, portfolio_id):
    transactions = [
        make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000)),
        make_txn(db_session, portfolio_id, None, TransactionType.WITHDRAW, date(2024, 2, 1), total_eur=Decimal(200)),
        make_txn(db_session, portfolio_id, None, TransactionType.INTEREST, date(2024, 3, 1), total_eur=Decimal(50)),
    ]
    db_session.commit()

    assert net_invested_eur(transactions) == Decimal(800)


def _rows_by_ticker(db, portfolio_id):
    return {row.ticker: row for row in position_service.list_position_rows(db, portfolio_id)}


def test_position_rows_weigh_every_holding_against_a_total_that_includes_cash(db_session, portfolio_id):
    """The cash row isn't cosmetic — leaving it out of the denominator would inflate every
    other holding's weight, and a target allocation is only meaningful against the whole
    portfolio."""
    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(250))
    db_session.add(PriceHistory(asset_id=asset.id, date=date.today(), close_price=Decimal(25)))
    db_session.commit()

    rows = _rows_by_ticker(db_session, portfolio_id)

    # 750 cash left after a 250 buy, holding now worth 10 * 25 = 250 → 1000 total.
    assert rows["CASH"].market_value_eur == Decimal(750)
    assert rows["ACME"].market_value_eur == Decimal(250)
    assert rows["ACME"].weight_pct == Decimal(25)
    assert rows["CASH"].weight_pct == Decimal(75)


def test_position_rows_report_average_cost_and_unrealized_pnl(db_session, portfolio_id):
    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(200))
    db_session.add(PriceHistory(asset_id=asset.id, date=date.today(), close_price=Decimal(25)))
    db_session.commit()

    acme = _rows_by_ticker(db_session, portfolio_id)["ACME"]

    assert acme.avg_cost_eur == Decimal(20)  # 200 / 10
    assert acme.unrealized_pnl_eur == Decimal(50)  # 250 market - 200 cost
    assert acme.unrealized_pnl_pct == Decimal(25)


def test_position_rows_report_target_weight_drift_in_points_and_euros(db_session, portfolio_id):
    asset = make_asset(db_session)
    portfolio_asset_target_repo.set_target(db_session, portfolio_id, asset.id, Decimal(10))
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(250))
    db_session.add(PriceHistory(asset_id=asset.id, date=date.today(), close_price=Decimal(25)))
    db_session.commit()

    acme = _rows_by_ticker(db_session, portfolio_id)["ACME"]

    # Actually 25% of a 1000 portfolio against a 10% target: 15 points, or 150 euro, overweight.
    assert acme.target_weight_diff_pct == Decimal(15)
    assert acme.target_weight_diff_eur == Decimal(150)


def test_position_rows_leave_drift_null_when_no_target_is_set(db_session, portfolio_id):
    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(250))
    db_session.add(PriceHistory(asset_id=asset.id, date=date.today(), close_price=Decimal(25)))
    db_session.commit()

    acme = _rows_by_ticker(db_session, portfolio_id)["ACME"]

    assert acme.target_weight_pct is None
    assert acme.target_weight_diff_pct is None
    assert acme.target_weight_diff_eur is None


def test_position_rows_sort_largest_holding_first(db_session, portfolio_id):
    small = make_asset(db_session, ticker="SMALL")
    big = make_asset(db_session, ticker="BIG")
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, small, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(1), total_eur=Decimal(50))
    make_txn(db_session, portfolio_id, big, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(1), total_eur=Decimal(600))
    db_session.add(PriceHistory(asset_id=small.id, date=date.today(), close_price=Decimal(50)))
    db_session.add(PriceHistory(asset_id=big.id, date=date.today(), close_price=Decimal(600)))
    db_session.commit()

    assert [row.ticker for row in position_service.list_position_rows(db_session, portfolio_id)] == ["BIG", "CASH", "SMALL"]


# -- portfolio isolation ----------------------------------------------------------------------


def test_positions_in_one_portfolio_do_not_leak_into_another(db_session, portfolio_id):
    from app.models.portfolio import Portfolio

    other = Portfolio(name="Other Portfolio")
    db_session.add(other)
    db_session.flush()

    asset = make_asset(db_session)
    make_txn(db_session, portfolio_id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(1000))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 2), quantity=Decimal(10), total_eur=Decimal(250))
    make_txn(db_session, other.id, None, TransactionType.DEPOSIT, date(2024, 1, 1), total_eur=Decimal(50))
    db_session.commit()

    active, _closed = position_service.get_positions(db_session, portfolio_id)
    other_active, _other_closed = position_service.get_positions(db_session, other.id)

    assert len(active) == 1 and active[0].ticker == "ACME"
    assert other_active == []
    assert cash_balance_eur(transaction_repo.list_all_transactions(db_session, portfolio_id)) == Decimal(750)
    assert cash_balance_eur(transaction_repo.list_all_transactions(db_session, other.id)) == Decimal(50)


def test_target_weight_set_in_one_portfolio_does_not_apply_in_another(db_session, portfolio_id):
    from app.models.portfolio import Portfolio

    other = Portfolio(name="Other Portfolio")
    db_session.add(other)
    db_session.flush()

    asset = make_asset(db_session)
    portfolio_asset_target_repo.set_target(db_session, portfolio_id, asset.id, Decimal(20))
    make_txn(db_session, portfolio_id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(1), total_eur=Decimal(100))
    make_txn(db_session, other.id, asset, TransactionType.BUY, date(2024, 1, 1), quantity=Decimal(1), total_eur=Decimal(100))
    db_session.commit()

    mine = _rows_by_ticker(db_session, portfolio_id)["ACME"]
    theirs = _rows_by_ticker(db_session, other.id)["ACME"]

    assert mine.target_weight_pct == Decimal(20)
    assert theirs.target_weight_pct is None
