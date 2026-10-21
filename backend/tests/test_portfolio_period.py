from datetime import date
from decimal import Decimal

from app.models.transaction import Transaction, TransactionType
from app.services.portfolio_period import pct, portfolio_period

TT = TransactionType
D = Decimal
START, END = date(2026, 10, 9), date(2026, 10, 16)
ACME, YANK, GONE, COIN = 1, 2, 3, 4  # EUR stock, USD stock, sold out mid-period, staked crypto


def txn(day, type_, total, asset=None, qty=None, price=None, n=[0]):
    n[0] += 1
    return Transaction(id=n[0], portfolio_id=1, date=day, type=type_, asset_id=asset, quantity=qty, price=price,
                       value_eur=D(total), costs=D(0), total_eur=D(total))


# Closes per asset and day, in the asset's own currency; looked up "on or before".
CLOSES = {
    ACME: {date(2026, 10, 1): D(10), START: D(10), END: D(12)},
    YANK: {date(2026, 10, 1): D(100), START: D(100), END: D(100)},
    GONE: {date(2026, 10, 1): D(50), START: D(50), date(2026, 10, 13): D(55)},
    COIN: {date(2026, 10, 1): D(1), END: D(1)},
}
USD_EUR = {date(2026, 10, 1): D("0.90"), START: D("0.90"), END: D("0.95")}


def price_on(asset_id, day):
    known = [d for d in CLOSES.get(asset_id, {}) if d <= day]
    return CLOSES[asset_id][max(known)] if known else None


def fx_on(asset_id, day):
    if asset_id != YANK:
        return D(1)
    return USD_EUR[max(d for d in USD_EUR if d <= day)]


LEDGER = [
    txn(date(2026, 10, 1), TT.DEPOSIT, 5000),
    txn(date(2026, 10, 1), TT.BUY, 1000, ACME, D(100), D(10)),
    txn(date(2026, 10, 1), TT.BUY, 900, YANK, D(10), D(100)),
    txn(date(2026, 10, 1), TT.BUY, 500, GONE, D(10), D(50)),
    txn(date(2026, 10, 1), TT.BUY, 100, COIN, D(100), D(1)),
    # In the period:
    txn(date(2026, 10, 12), TT.DEPOSIT, 1000),
    txn(date(2026, 10, 12), TT.BUY, 220, ACME, D(20), D(11)),
    txn(date(2026, 10, 13), TT.SELL, 550, GONE, D(10), D(55)),
    txn(date(2026, 10, 14), TT.DIVIDEND, 15, ACME),
    txn(date(2026, 10, 14), TT.STAKING, 0, COIN, D(10)),
    txn(date(2026, 10, 15), TT.INTEREST, 4),
    txn(date(2026, 10, 15), TT.BROKER_FEE, 1),
    txn(date(2026, 10, 15), TT.WITHDRAW, 300),
    # After the period: never counted.
    txn(date(2026, 10, 17), TT.BUY, 999, ACME, D(1), D(999)),
]


def test_contributions_interest_and_fees_add_up_to_the_portfolios_change():
    p = portfolio_period(LEDGER, START, END, price_on, fx_on)

    # Start: cash 5000-2500 = 2500; ACME 1000, YANK 10*100*0.90 = 900, GONE 500, COIN 100.
    assert p.value_start_eur == D(5000)
    assert (p.deposits_eur, p.withdrawals_eur, p.interest_eur, p.fees_eur) == (D(1000), D(300), D(4), D(1))
    assert (p.buys, p.sells) == (1, 1)
    by_asset = {h.asset_id: h for h in p.holdings}
    assert by_asset[ACME].contribution_eur == D(120) * 12 - D(1000) - D(220) + D(15)  # 235
    assert by_asset[YANK].contribution_eur == D(950) - D(900)  # currency only: the price didn't move
    assert by_asset[GONE].contribution_eur == D(550) - D(500)  # sold out at 55
    assert by_asset[COIN].contribution_eur == D(110) - D(100)  # staking reward at the end price
    contributions = sum(h.contribution_eur for h in p.holdings)
    assert contributions + p.interest_eur - p.fees_eur == p.change_eur
    assert p.change_eur == p.value_end_eur - p.value_start_eur - D(1000) + D(300)


def test_price_change_is_in_the_assets_own_currency():
    by_asset = {h.asset_id: h for h in portfolio_period(LEDGER, START, END, price_on, fx_on).holdings}
    assert by_asset[ACME].price_change_pct == D(20)
    assert by_asset[YANK].price_change_pct == D(0)  # the 5.6% euro gain is currency, not price
    assert by_asset[GONE].price_change_pct == D(10)
    assert by_asset[GONE].quantity_end == D(0)


def test_points_and_weights_are_shares_of_the_start_and_end_value():
    p = portfolio_period(LEDGER, START, END, price_on, fx_on)
    acme = next(h for h in p.holdings if h.asset_id == ACME)
    assert p.contribution_pp(acme) == D(235) / D(5000) * 100
    assert p.weight_end_pct(acme) == D(1440) / p.value_end_eur * 100
    assert pct(D(1), D(0)) is None


def test_a_transaction_on_the_start_day_is_in_the_start_value_and_one_on_the_end_day_in_the_period():
    ledger = [txn(START, TT.DEPOSIT, 100), txn(END, TT.DEPOSIT, 50)]
    p = portfolio_period(ledger, START, END, price_on, fx_on)
    assert (p.value_start_eur, p.deposits_eur, p.value_end_eur, p.change_eur) == (D(100), D(50), D(150), D(0))


def test_a_holding_without_a_close_falls_back_to_its_last_trade_and_is_stale():
    ledger = [txn(date(2026, 10, 1), TT.BUY, 70, 9, D(7), D(10))]
    [holding] = portfolio_period(ledger, START, END, price_on, fx_on).holdings
    assert (holding.price_end, holding.value_end_eur, holding.price_end_stale) == (D(10), D(70), True)
    assert holding.price_change_pct == D(0)


def test_a_holding_bought_in_the_period_has_no_start_price_change():
    ledger = [txn(date(2026, 10, 12), TT.BUY, 30, 9, D(3), D(10))]
    [holding] = portfolio_period(ledger, START, END, price_on, fx_on).holdings
    assert holding.price_start is None and holding.price_change_pct is None
    assert holding.quantity_start == 0 and holding.contribution_eur == D(0)
