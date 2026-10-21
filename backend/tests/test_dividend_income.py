from datetime import date
from decimal import Decimal

from app.models.transaction import TransactionType
from app.repositories import transaction_repo
from app.services import dividend_service
from app.services.dividend_income import add_months, dividend_income
from tests.test_summary_service import make_asset, make_txn, set_price

TODAY = date(2026, 10, 18)
D = TransactionType


def ledger(db, portfolio_id):
    """10 shares bought in 2025, a quarterly-ish dividend, 10 more shares bought in July 2026."""
    asset = make_asset(db, "ACME")
    make_txn(db, portfolio_id, None, D.DEPOSIT, date(2025, 1, 2), total_eur=Decimal(5000))
    make_txn(db, portfolio_id, asset, D.BUY, date(2025, 1, 3), quantity=Decimal(10), total_eur=Decimal(1000))
    make_txn(db, portfolio_id, asset, D.DIVIDEND, date(2025, 6, 15), total_eur=Decimal(5))  # before the window
    make_txn(db, portfolio_id, asset, D.DIVIDEND, date(2025, 12, 15), total_eur=Decimal(6))
    make_txn(db, portfolio_id, asset, D.DIVIDEND, date(2026, 6, 15), total_eur=Decimal(6))
    # Bought on the day of a payment: that payment was earned on the 10 shares held before.
    make_txn(db, portfolio_id, asset, D.BUY, date(2026, 7, 1), quantity=Decimal(10), total_eur=Decimal(1200))
    make_txn(db, portfolio_id, asset, D.DIVIDEND, date(2026, 7, 1), total_eur=Decimal(1))
    return asset


def test_received_per_month_year_and_holding(db_session, portfolio_id):
    asset = ledger(db_session, portfolio_id)

    income = dividend_income(transaction_repo.list_all_transactions(db_session, portfolio_id), TODAY)

    assert income.received_by_month[(2025, 12)] == Decimal(6)
    h = income.holdings[asset.id]
    assert h.received_total_eur == Decimal(18)
    assert h.received_12m_eur == Decimal(13)
    assert h.payments_12m == 3
    assert h.last_paid_on == date(2026, 7, 1)


def test_the_coming_year_repeats_the_last_one_per_share_on_what_is_held_now(db_session, portfolio_id):
    asset = ledger(db_session, portfolio_id)

    income = dividend_income(transaction_repo.list_all_transactions(db_session, portfolio_id), TODAY)

    # Each payment was 0.60, 0.60 and 0.10 a share on 10 shares; 20 are held now.
    assert income.expected_by_month[(2026, 12)] == Decimal(12)
    assert income.expected_by_month[(2027, 6)] == Decimal(12)
    assert income.expected_by_month[(2027, 7)] == Decimal(2)
    assert income.holdings[asset.id].expected_12m_eur == Decimal(26)


def test_a_sold_holding_expects_nothing_and_a_future_dated_dividend_is_not_received(db_session, portfolio_id):
    asset = ledger(db_session, portfolio_id)
    make_txn(db_session, portfolio_id, asset, D.SELL, date(2026, 8, 1), quantity=Decimal(20), total_eur=Decimal(2500))
    make_txn(db_session, portfolio_id, asset, D.DIVIDEND, date(2026, 11, 1), total_eur=Decimal(9))

    income = dividend_income(transaction_repo.list_all_transactions(db_session, portfolio_id), TODAY)

    assert income.expected_by_month == {}
    assert income.holdings[asset.id].received_total_eur == Decimal(18)


def test_months_wrap_over_the_year():
    assert add_months((2026, 11), 3) == (2027, 2)
    assert add_months((2026, 1), -1) == (2025, 12)


def test_the_income_page_joins_names_and_yields(db_session, portfolio_id):
    asset = ledger(db_session, portfolio_id)
    set_price(db_session, asset, "130")

    out = dividend_service.get_income(db_session, portfolio_id, TODAY)

    assert out.received_this_year_eur == Decimal(7)
    assert out.received_last_year_eur == Decimal(11)
    assert out.received_12m_eur == Decimal(13)
    assert out.expected_12m_eur == Decimal(26)
    assert out.paying_holdings == 1
    [h] = out.holdings
    assert (h.name, h.is_held) == ("ACME Inc", True)
    # 26 a year on 2,200 cost and on 2,600 market value.
    assert round(h.yield_on_cost_pct, 2) == Decimal("1.18")
    assert h.current_yield_pct == Decimal(1)
    # 12 months back including this one, then 12 ahead.
    assert [m.month for m in out.months][0] == "2025-11"
    assert [m.month for m in out.months][-1] == "2027-10"
    assert len(out.months) == 24
    december = next(m for m in out.months if m.month == "2026-12")
    assert (december.received_eur, december.expected_eur) == (Decimal(0), Decimal(12))
    assert [y.year for y in out.years] == [2026, 2025]
    assert out.years[1].months[11] == Decimal(6)
