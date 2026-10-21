from datetime import date, timedelta
from decimal import Decimal

from app.services.money_weighted_return import money_weighted_return, xirr

START = date(2024, 1, 1)


def close(a, b, places=2):
    return abs(Decimal(a) - Decimal(b)) < Decimal(10) ** -places


def test_one_deposit_growing_ten_percent_in_a_year_is_ten_percent():
    rate = xirr([(START, Decimal(-1000)), (START + timedelta(days=365), Decimal(1100))])
    assert close(rate, "0.10", 4)


def test_a_loss_is_a_negative_rate():
    rate = xirr([(START, Decimal(-1000)), (START + timedelta(days=365), Decimal(800))])
    assert close(rate, "-0.20", 4)


def test_the_timing_of_a_deposit_changes_the_money_weighted_return():
    # Same start, same end value, same total paid in -- but money that arrived later had less
    # time to earn the same gain, so its rate is higher.
    end = START + timedelta(days=730)
    early = xirr([(START, Decimal(-1000)), (START + timedelta(days=30), Decimal(-1000)), (end, Decimal(2400))])
    late = xirr([(START, Decimal(-1000)), (START + timedelta(days=700), Decimal(-1000)), (end, Decimal(2400))])
    assert late > early > 0


def test_flows_all_one_way_or_on_one_day_have_no_rate():
    assert xirr([(START, Decimal(-1000)), (START + timedelta(days=10), Decimal(-5))]) is None
    assert xirr([(START, Decimal(-1000)), (START, Decimal(1100))]) is None
    assert xirr([]) is None


def test_a_period_shorter_than_a_year_has_no_yearly_figure_but_a_period_one():
    # 1,000 in, 50 more half way, worth 1,100 after 182 days.
    period, yearly = money_weighted_return(
        START, Decimal(1000), [(START + timedelta(days=91), Decimal(50))], START + timedelta(days=182), Decimal(1100)
    )
    assert yearly is None
    # Roughly the 50 gained on ~1,025 on average over the half year.
    assert close(period, "4.9", 0)


def test_cash_that_only_moved_in_and_out_earned_nothing():
    period, yearly = money_weighted_return(
        START,
        Decimal(1000),
        [(START + timedelta(days=100), Decimal(500)), (START + timedelta(days=200), Decimal(-300))],
        START + timedelta(days=400),
        Decimal(1200),
    )
    assert close(period, 0) and close(yearly, 0)


def test_a_withdrawal_counts_as_money_back():
    # 1,000 in, 550 taken out after a year, 550 left after two: 10% a year either way.
    period, yearly = money_weighted_return(
        START, Decimal(1000), [(START + timedelta(days=365), Decimal(-550))], START + timedelta(days=730), Decimal(605)
    )
    assert close(yearly, 10, 1)
