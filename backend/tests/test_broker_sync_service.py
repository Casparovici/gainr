from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.asset import Asset
from app.models.broker_sync import BrokerConnection
from app.models.transaction import Transaction, TransactionType
from app.repositories import transaction_repo
from app.services import broker_sync_service
from app.services.trading212_provider import CashEntry, Dividend, Fill, Instrument, Trading212AuthError

TT = TransactionType
SINCE = date(2026, 10, 2)  # a Friday
AMZN = Instrument(isin="US0231351067", ticker="AMZN_US_EQ", name="Amazon", currency="USD")
TDIV = Instrument(isin="NL0011683594", ticker="TDIVa_EQ", name="VanEck Dividend Leaders", currency="EUR")
GRID = Instrument(isin="IE000J80JTL1", ticker="GRIDd_EQ", name="First Trust Clean Edge Smart Grid", currency="EUR")


class FakeTrading212:
    configured = True

    def __init__(self):
        self.fills: list[Fill] = []
        self.dividends: list[Dividend] = []
        self.cash: list[CashEntry] = []
        self.calls: list[tuple[str, date]] = []
        self.error: Exception | None = None

    def _call(self, name, since):
        if self.error is not None:
            raise self.error
        self.calls.append((name, since))

    def fills_since(self, since):
        self._call("fills", since)
        return list(self.fills)

    def dividends_since(self, since):
        self._call("dividends", since)
        return list(self.dividends)

    def cash_activity(self, since, until=None):
        self._call("cash", since)
        return list(self.cash)


class FakePrices:
    """0.90 EUR to the dollar, every day."""

    def ensure_fx_history(self, db, currency, start, end):
        pass

    def get_fx_rate(self, db, currency, on_date=None):
        return Decimal("0.9")


def noon(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)


_counter = 0


def fill(instrument=AMZN, day=date(2026, 10, 2), *, side="BUY", quantity="2", price="246.77", net="434.74", fees="0.65",
         wallet="EUR", fx="1.13695316", auto=False) -> Fill:
    global _counter
    _counter += 1
    return Fill(
        fill_id=str(_counter), side=side, instrument=instrument, quantity=Decimal(quantity), price=Decimal(price),
        filled_at=noon(day), wallet_currency=wallet, net_value=Decimal(net), fx_rate=Decimal(fx) if fx else None,
        fees=Decimal(fees), auto_invest=auto,
    )


def cash(amount: str, day: date, action: str, currency: str = "EUR") -> CashEntry:
    global _counter
    _counter += 1
    return CashEntry(entry_id=f"c{_counter}", action=action, at=noon(day), amount=Decimal(amount), currency=currency, merchant="", merchant_category="")


@pytest.fixture()
def t212():
    return FakeTrading212()


@pytest.fixture()
def assets(db_session):
    made = {
        "amzn": Asset(ticker="AMZN", name="Amazon", native_currency="USD", isin=AMZN.isin),
        "tdiv": Asset(ticker="AMS:TDIV", name="VanEck Dividend Leaders", native_currency="EUR", isin=TDIV.isin),
        "grid": Asset(ticker="GRIDINAV", name="Smart Grid", native_currency="EUR"),  # no ISIN yet
    }
    db_session.add_all(made.values())
    db_session.flush()
    return made


@pytest.fixture()
def connection(db_session, portfolio_id, assets) -> BrokerConnection:
    row = BrokerConnection(broker="Trading212", portfolio_id=portfolio_id, enabled=True, since=SINCE)
    db_session.add(row)
    db_session.flush()
    return row


def run(db_session, t212, as_of=date(2026, 10, 3)):
    return broker_sync_service.sync(db_session, t212, FakePrices(), as_of=as_of)


def rows(db_session) -> list[Transaction]:
    return list(db_session.query(Transaction).order_by(Transaction.id))


def hand(db_session, portfolio_id, asset, day, quantity, type_=TT.BUY, total="100"):
    return transaction_repo.create_transaction(
        db_session, portfolio_id=portfolio_id, asset_id=asset.id, date=day, type=type_, quantity=Decimal(quantity) if quantity is not None else None,
        total_eur=Decimal(total), value_eur=Decimal(total), broker="Trading212",
    )


def test_a_fill_paid_in_euros_is_booked_for_the_cash_it_moved(db_session, t212, connection, assets, portfolio_id):
    t212.fills = [fill()]

    result = run(db_session, t212)

    assert result.booked == 1
    (buy,) = rows(db_session)
    assert (buy.type, buy.asset_id, buy.portfolio_id, buy.broker, buy.date) == (TT.BUY, assets["amzn"].id, portfolio_id, "Trading212", date(2026, 10, 2))
    assert (buy.quantity, buy.price, buy.local_value) == (Decimal("2"), Decimal("246.77"), Decimal("493.54"))
    assert (buy.total_eur, buy.costs, buy.value_eur, buy.fx_rate) == (Decimal("434.74"), Decimal("0.65"), Decimal("434.09"), Decimal("1.13695316"))
    assert buy.source_ref == f"t212:fill:{t212.fills[0].fill_id}"
    assert buy.notes == "Trading 212"


def test_a_fill_paid_from_the_dollar_wallet_is_converted_at_that_days_rate(db_session, t212, connection, assets):
    t212.fills = [fill(net="327.13", fees="0", wallet="USD", fx="1", quantity="0.19308476", price="1694.23")]

    run(db_session, t212)

    (buy,) = rows(db_session)
    assert buy.total_eur == Decimal("294.41700000")  # 327.13 USD at 0.90
    assert buy.fx_rate == Decimal("1.11111111")


def test_a_sell_adds_its_fees_back_onto_the_value(db_session, t212, connection, assets):
    t212.fills = [fill(side="SELL", net="500.00", fees="0.75")]

    run(db_session, t212)

    (sell,) = rows(db_session)
    assert (sell.type, sell.total_eur, sell.costs, sell.value_eur) == (TT.SELL, Decimal("500.00"), Decimal("0.75"), Decimal("500.75"))


def test_an_auto_invest_buy_says_so(db_session, t212, connection, assets):
    t212.fills = [fill(TDIV, quantity="0.0199014", price="54.77", net="1.09", fees="0", fx="1", auto=True)]

    run(db_session, t212)

    (buy,) = rows(db_session)
    assert buy.notes == "Trading 212 · auto-invest"
    assert buy.fx_rate is None  # a euro instrument has no rate, like a hand-entered one


def test_a_fill_entered_by_hand_is_matched_not_booked_again(db_session, t212, connection, assets, portfolio_id):
    entered = hand(db_session, portfolio_id, assets["amzn"], date(2026, 10, 2), "2")
    t212.fills = [fill()]

    result = run(db_session, t212)

    assert (result.matched, result.booked) == (1, 0)
    assert rows(db_session) == [entered]
    assert entered.source_ref is None


def test_several_fills_entered_as_one_row_match_together(db_session, t212, connection, assets, portfolio_id):
    hand(db_session, portfolio_id, assets["tdiv"], date(2026, 10, 2), "45.67301730")
    t212.fills = [
        fill(TDIV, quantity="27", fx="1"),
        fill(TDIV, quantity="11.28243572", fx="1"),
        fill(TDIV, quantity="7.39058158", fx="1"),
    ]

    result = run(db_session, t212)

    assert (result.matched, result.booked) == (3, 0)
    assert len(rows(db_session)) == 1


def test_running_again_books_nothing_twice(db_session, t212, connection, assets):
    t212.fills = [fill()]
    run(db_session, t212)

    again = run(db_session, t212, as_of=date(2026, 10, 4))

    assert (again.booked, again.matched) == (0, 0)
    assert len(rows(db_session)) == 1


def test_an_instrument_no_asset_has_waits_until_one_is_linked(db_session, t212, connection, assets):
    t212.fills = [fill(GRID, quantity="7", fx="1", net="384.37", fees="0")]

    first = run(db_session, t212)

    assert first.booked == 0
    assert [(u["isin"], u["records"], u["first_date"]) for u in first.unmapped] == [(GRID.isin, 1, "2026-10-02")]
    assert broker_sync_service.unmapped_instruments(connection)[0]["name"] == GRID.name

    # Linked weeks later: the next run reads back to the held fill, not just the last week.
    assets["grid"].isin = GRID.isin
    later = run(db_session, t212, as_of=date(2026, 10, 30))

    assert later.booked == 1
    assert ("fills", SINCE) in t212.calls[-3:]
    assert connection.unmapped is None


def test_a_currency_that_differs_from_the_assets_is_held_back(db_session, t212, connection, assets):
    assets["tdiv"].native_currency = "USD"
    t212.fills = [fill(TDIV, fx="1")]

    result = run(db_session, t212)

    assert result.booked == 0
    assert "AMS:TDIV" in result.problems[0]


def test_dividends_match_a_hand_entered_one_or_are_booked(db_session, t212, connection, assets, portfolio_id):
    hand(db_session, portfolio_id, assets["tdiv"], date(2026, 10, 3), None, TT.DIVIDEND, total="20.54")
    t212.dividends = [
        Dividend(reference="d1", instrument=TDIV, amount_eur=Decimal("20.55"), paid_at=noon(date(2026, 10, 2))),
        Dividend(reference="d2", instrument=AMZN, amount_eur=Decimal("1.65"), paid_at=noon(date(2026, 10, 2))),
    ]

    result = run(db_session, t212)

    assert (result.matched, result.booked) == (1, 1)
    booked = rows(db_session)[-1]
    assert (booked.type, booked.asset_id, booked.total_eur, booked.source_ref) == (TT.DIVIDEND, assets["amzn"].id, Decimal("1.65"), "t212:dividend:d2")


def test_interest_and_cashback_are_one_deposit_per_completed_week(db_session, t212, connection, assets):
    t212.cash = [
        cash("0.05", date(2026, 10, 2), "Interest on cash"),
        cash("0.11", date(2026, 10, 3), "Spending cashback"),
        cash("0.03", date(2026, 10, 4), "Interest on cash", currency="USD"),
        cash("-15.99", date(2026, 10, 4), "Card debit"),
        cash("500", date(2026, 10, 4), "Deposit"),
    ]

    sunday = run(db_session, t212, as_of=date(2026, 10, 4))
    monday = run(db_session, t212, as_of=date(2026, 10, 5))
    tuesday = run(db_session, t212, as_of=date(2026, 10, 6))

    assert sunday.deposits == 0
    assert ("cash", SINCE) not in t212.calls[:3]  # no completed week yet: no export requested
    assert monday.deposits == 1
    (deposit,) = rows(db_session)
    assert (deposit.type, deposit.date, deposit.total_eur, deposit.broker) == (TT.DEPOSIT, date(2026, 10, 4), Decimal("0.19"), "Trading212")
    assert deposit.notes == "Trading 212: interest €0.08 + cashback €0.11, week 40 (02 Oct–04 Oct)"
    assert deposit.source_ref == "t212:week:2026-W40"
    assert tuesday.deposits == 0
    assert [c for c in t212.calls if c[0] == "cash"] == [("cash", SINCE)]


def test_a_week_without_interest_is_recorded_and_not_asked_for_again(db_session, t212, connection, assets):
    run(db_session, t212, as_of=date(2026, 10, 5))
    run(db_session, t212, as_of=date(2026, 10, 6))

    assert rows(db_session) == []
    assert [c for c in t212.calls if c[0] == "cash"] == [("cash", SINCE)]


def test_switched_off_or_without_a_portfolio_does_nothing(db_session, t212, connection):
    connection.portfolio_id = None
    assert run(db_session, t212) == broker_sync_service.BrokerSyncResult()
    connection.enabled = False
    assert run(db_session, t212) == broker_sync_service.BrokerSyncResult()
    assert t212.calls == []


def test_a_refused_key_is_kept_on_the_connection(db_session, t212, connection):
    t212.error = Trading212AuthError("refused")

    result = run(db_session, t212)

    assert "IP address" in result.problems[0]
    assert "IP address" in connection.last_error
    assert connection.last_synced_at is None


def test_later_runs_reread_a_week(db_session, t212, connection, assets):
    run(db_session, t212, as_of=date(2026, 10, 3))
    connection.last_synced_at = datetime(2026, 10, 20, 6)

    run(db_session, t212, as_of=date(2026, 10, 20))

    assert ("fills", date(2026, 10, 20) - timedelta(days=7)) in t212.calls
