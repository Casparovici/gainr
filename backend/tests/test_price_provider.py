"""YFinanceProvider against a stand-in for yfinance's Ticker: no network."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
import pytest
import yfinance

from app.services.price_provider import PriceProvider, Quote, YFinanceProvider

AMS = timezone(timedelta(hours=2))


class FakeTicker:
    def __init__(self, history=None, metadata=None, fast_info=None, fail=False):
        self._history, self._metadata, self._fast_info, self._fail = history, metadata, fast_info, fail
        self.requested = None

    def history(self, start=None, end=None, **kwargs):
        if self._fail:
            raise RuntimeError("Yahoo is down")
        self.requested = (start, end) if not kwargs else kwargs
        return self._history

    @property
    def history_metadata(self):
        if self._fail:
            raise RuntimeError("Yahoo is down")
        return self._metadata

    @property
    def fast_info(self):
        if self._fail:
            raise RuntimeError("Yahoo is down")
        return self._fast_info


@pytest.fixture()
def ticker(monkeypatch):
    def install(**kw) -> FakeTicker:
        fake = FakeTicker(**kw)
        monkeypatch.setattr(yfinance, "Ticker", lambda symbol: fake)
        return fake

    return install


def test_history_is_decimal_closes_by_day_without_the_nan_sessions(ticker):
    index = pd.to_datetime(["2026-10-05", "2026-10-06", "2026-10-07"]).tz_localize("Europe/Amsterdam")
    fake = ticker(history=pd.DataFrame({"Close": [42.64, float("nan"), 43.1]}, index=index))

    closes = YFinanceProvider().get_history("IWDA.AS", date(2026, 10, 5), date(2026, 10, 7))

    assert closes == {date(2026, 10, 5): Decimal("42.64"), date(2026, 10, 7): Decimal("43.1")}
    assert fake.requested == ("2026-10-05", "2026-10-08")  # Yahoo's end is exclusive


def test_no_history_or_a_failure_is_an_empty_series(ticker):
    ticker(history=pd.DataFrame({"Close": []}))
    assert YFinanceProvider().get_history("X", date(2026, 10, 5), date(2026, 10, 7)) == {}
    ticker(fail=True)
    assert YFinanceProvider().get_history("X", date(2026, 10, 5), date(2026, 10, 7)) == {}


def test_currency_comes_from_the_quote_and_a_failure_is_unknown(ticker):
    ticker(fast_info={"currency": "GBp"})
    assert YFinanceProvider().get_currency("WISE.L") == "GBp"
    ticker(fail=True)
    assert YFinanceProvider().get_currency("WISE.L") is None


def test_a_settled_close_is_dated_by_the_exchanges_own_clock(ticker):
    # 23:30 UTC on 5 Oct is already 6 Oct in Amsterdam (+2h).
    stamped = datetime(2026, 10, 5, 23, 30, tzinfo=timezone.utc).timestamp()
    ticker(metadata={"regularMarketPrice": 42.64, "regularMarketTime": stamped, "gmtoffset": 7200})
    assert YFinanceProvider().get_last_settled_close("IWDA.AS") == (date(2026, 10, 6), Decimal("42.64"))


def test_a_timezone_aware_stamp_is_taken_as_it_is(ticker):
    ticker(metadata={"regularMarketPrice": 10, "regularMarketTime": datetime(2026, 10, 5, 17, 30, tzinfo=AMS)})
    assert YFinanceProvider().get_last_settled_close("X") == (date(2026, 10, 5), Decimal("10"))


@pytest.mark.parametrize(
    "metadata",
    [
        {"regularMarketPrice": None, "regularMarketTime": 1_759_000_000, "gmtoffset": 0},
        {"regularMarketPrice": 10, "regularMarketTime": None},
        {"regularMarketPrice": 10, "regularMarketTime": datetime(2026, 10, 5, 17, 30)},  # no timezone
        {"regularMarketPrice": 10, "regularMarketTime": 1_759_000_000},  # epoch without an offset
        {"regularMarketPrice": 10, "regularMarketTime": "yesterday"},
    ],
)
def test_a_snapshot_that_cant_be_dated_or_priced_repairs_nothing(ticker, metadata):
    ticker(metadata=metadata)
    assert YFinanceProvider().get_last_settled_close("X") is None


def test_a_session_still_trading_is_not_a_close(ticker):
    ticker(metadata={"regularMarketPrice": 10, "regularMarketTime": datetime.now(AMS)})
    assert YFinanceProvider().get_last_settled_close("X") is None


def test_a_failing_snapshot_repairs_nothing(ticker):
    ticker(fail=True)
    assert YFinanceProvider().get_last_settled_close("X") is None


def test_a_quote_is_the_last_trade_with_its_moment(ticker):
    stamped = datetime(2026, 10, 19, 13, 45, tzinfo=timezone.utc)
    ticker(metadata={"regularMarketPrice": 43.1, "regularMarketTime": stamped.timestamp(), "gmtoffset": 7200})

    quote = YFinanceProvider().get_quote("IWDA.AS")

    assert quote == Quote(price=Decimal("43.1"), quoted_at=stamped.astimezone(AMS))


def test_a_quote_that_cant_be_dated_or_fetched_is_none(ticker):
    ticker(metadata={"regularMarketPrice": 10, "regularMarketTime": None})
    assert YFinanceProvider().get_quote("X") is None
    ticker(fail=True)
    assert YFinanceProvider().get_quote("X") is None


def test_a_provider_without_quotes_has_none():
    class ClosesOnly(PriceProvider):
        def get_history(self, symbol, start, end):
            return {}

        def get_currency(self, symbol):
            return None

    assert ClosesOnly().get_quote("X") is None


# -- intraday bars (the 1D price chart, docs/adr/0053) ----------------------------------------


def test_intraday_is_the_last_sessions_bars_in_order_without_nan(ticker):
    index = pd.to_datetime(
        ["2026-10-16 16:15", "2026-10-16 16:30", "2026-10-19 09:00", "2026-10-19 09:15", "2026-10-19 09:30"]
    ).tz_localize("Europe/Amsterdam")
    frame = pd.DataFrame({"Close": [10.0, 10.5, 20.25, float("nan"), 20.5]}, index=index)
    fake = ticker(history=frame)

    bars = YFinanceProvider().get_intraday("ASML.AS")

    assert fake.requested == {"period": "5d", "interval": "15m"}
    assert [p for _, p in bars] == [Decimal("20.25"), Decimal("20.5")]
    assert all(isinstance(p, Decimal) for _, p in bars)
    assert [ts.hour for ts, _ in bars] == [9, 9] and bars[0][0].tzinfo is not None
    # one session only: the Friday bars are left out
    assert {ts.date() for ts, _ in bars} == {date(2026, 10, 19)}


def test_intraday_is_empty_when_yahoo_has_nothing_or_fails(ticker):
    ticker(history=pd.DataFrame({"Close": []}))
    assert YFinanceProvider().get_intraday("X") == []

    ticker(fail=True)
    assert YFinanceProvider().get_intraday("X") == []


def test_a_provider_without_intraday_returns_nothing():
    class Bare(PriceProvider):
        def get_history(self, symbol, start, end):
            return {}

        def get_currency(self, symbol):
            return None

    assert Bare().get_intraday("X") == []
