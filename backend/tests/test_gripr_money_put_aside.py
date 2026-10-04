"""Overview's "money put aside": the net money that went into investments, savings and
reservations (virtual pots) per period."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_transaction import GriprTransactionType
from app.services import gripr_overview_service, gripr_transaction_service

T = GriprTransactionType


@pytest.fixture()
def accounts(db_session):
    def make(name, type_, held_in=None, mode=GriprBalanceMode.TRANSACTIONAL):
        a = GriprAccount(name=name, type=type_, balance_mode=mode, held_in_account_id=held_in)
        db_session.add(a)
        db_session.flush()
        return a

    ing = make("ING", GriprAccountType.CHECKING)
    tr = make("Trade Republic", GriprAccountType.SAVINGS)
    return {
        "ing": ing, "tr": tr,
        "kids": make("Spaarrekening Sam", GriprAccountType.SAVINGS),
        "vakantie": make("Reservering Vakantie", GriprAccountType.SAVINGS, held_in=tr.id),
        "onderhoud": make("Onderhoud Auto", GriprAccountType.SAVINGS, held_in=tr.id),
        "beleggen": make("Beleggen", GriprAccountType.INVESTMENT, mode=GriprBalanceMode.MANUAL),
    }


def move(db, day, type_, amount, account, counter=None):
    gripr_transaction_service.create_transaction(
        db, date=day, type=type_, amount=Decimal(amount), account_id=account.id,
        counter_account_id=counter.id if counter else None,
    )


def test_money_into_each_group_per_period(db_session, accounts):
    a = accounts
    sept = date(2026, 9, 10)
    move(db_session, sept, T.TRANSFER, "1000", a["ing"], a["tr"])          # +1000 savings
    move(db_session, sept, T.TRANSFER, "50", a["tr"], a["kids"])           # within savings: nothing
    move(db_session, sept, T.TRANSFER, "200", a["tr"], a["vakantie"])      # -200 savings, +200 reservations
    move(db_session, sept, T.TRANSFER, "75", a["tr"], a["onderhoud"])      # -75 savings, +75 reservations
    move(db_session, sept, T.EXPENSE, "30", a["onderhoud"])                # a repair paid from the pot: -30
    move(db_session, sept, T.INCOME, "4", a["tr"])                         # interest: +4 savings
    move(db_session, sept, T.EXPENSE, "12", a["tr"])                       # card payment from savings: -12
    move(db_session, sept, T.TRANSFER, "300", a["ing"], a["beleggen"])     # +300 investments
    move(db_session, date(2026, 10, 2), T.TRANSFER, "100", a["beleggen"], a["ing"])  # next month: -100

    points = gripr_overview_service.money_put_aside(db_session, months=2, as_of=date(2026, 10, 15))

    sept_point, oct_point = points
    assert sept_point.month == date(2026, 9, 1)
    assert (sept_point.investments, sept_point.savings, sept_point.reservations) == (Decimal("300"), Decimal("717"), Decimal("245"))
    assert (oct_point.investments, oct_point.savings, oct_point.reservations) == (Decimal("-100"), 0, 0)


def test_an_empty_group_is_zero(db_session):
    (point,) = gripr_overview_service.money_put_aside(db_session, months=1, as_of=date(2026, 10, 15))

    assert (point.investments, point.savings, point.reservations) == (0, 0, 0)
