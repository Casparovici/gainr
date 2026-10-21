"""Money-weighted return (XIRR): the one constant yearly rate that turns what you put in, when you
put it in, into what the portfolio is worth now. Pure arithmetic on dated cash flows, no
framework or database.

It answers a different question than the time-weighted return performance_service charts. That
one measures the investments and ignores your timing, which makes it the right figure to hold up
against a benchmark. This one includes the timing: a big deposit just before a dip lowers it, one
before a rally raises it (docs/adr/0041).

Flows are from the investor's side: money in is negative (the start value and every deposit),
money out is positive (every withdrawal, and the end value as if cashed out on the last day).
"""

from datetime import date
from decimal import Decimal, localcontext

ZERO = Decimal(0)
ONE = Decimal(1)
DAYS_PER_YEAR = Decimal(365)
# The bracket the rate is searched in, per year: from -99.99% to +10,000%.
_LOW = Decimal("-0.9999")
_HIGH = Decimal(100)
# Bisection stops once the bracket is narrower than this (a thousandth of a percent per year).
_TOLERANCE = Decimal("0.00001")
_MAX_STEPS = 80


def _npv(rate: Decimal, flows: list[tuple[Decimal, Decimal]]) -> Decimal:
    """Net present value at `rate` of (years since the first flow, amount) pairs."""
    log_growth = (ONE + rate).ln()
    return sum((amount * (-years * log_growth).exp() for years, amount in flows), ZERO)


def xirr(flows: list[tuple[date, Decimal]]) -> Decimal | None:
    """The yearly rate at which the flows' present value is zero, as a fraction (0.084 = 8.4%).
    None when there's no such rate in the search bracket -- flows all one sign, or a span of
    less than a day -- rather than a number that would mean nothing."""
    flows = [(d, a) for d, a in flows if a != ZERO]
    if not flows:
        return None
    start = min(d for d, _ in flows)
    if max(d for d, _ in flows) == start:
        return None
    if all(a > ZERO for _, a in flows) or all(a < ZERO for _, a in flows):
        return None

    with localcontext() as ctx:
        ctx.prec = 20
        timed = [(Decimal((d - start).days) / DAYS_PER_YEAR, a) for d, a in flows]
        low, high = _LOW, _HIGH
        npv_low = _npv(low, timed)
        if npv_low == ZERO:
            return low
        if (npv_low > ZERO) == (_npv(high, timed) > ZERO):
            return None
        for _ in range(_MAX_STEPS):
            mid = (low + high) / 2
            npv_mid = _npv(mid, timed)
            if npv_mid == ZERO or high - low < _TOLERANCE:
                break
            if (npv_mid > ZERO) == (npv_low > ZERO):
                low, npv_low = mid, npv_mid
            else:
                high = mid
        return +((low + high) / 2)


def money_weighted_return(
    start: date,
    start_value: Decimal,
    flows: list[tuple[date, Decimal]],
    end: date,
    end_value: Decimal,
) -> tuple[Decimal | None, Decimal | None]:
    """(return over the period, return per year), both in percent, for a portfolio worth
    `start_value` on `start` and `end_value` on `end`, with `flows` the deposits (positive) and
    withdrawals (negative) in between as the ledger books them.

    The period figure is the yearly rate compounded over the period's length, so a YTD figure
    reads like the YTD time-weighted one next to it. The yearly figure is None for a period
    shorter than a year: scaling a few weeks up to a year exaggerates it."""
    cash_flows = [(start, -start_value)] + [(d, -amount) for d, amount in flows] + [(end, end_value)]
    rate = xirr(cash_flows)
    if rate is None:
        return None, None
    days = (end - start).days
    with localcontext() as ctx:
        ctx.prec = 20
        period = ((ONE + rate) ** (Decimal(days) / DAYS_PER_YEAR) - ONE) * 100
    yearly = rate * 100 if days >= 365 else None
    return period, yearly
