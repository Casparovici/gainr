from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.asset import Asset
from app.models.price_history import PriceHistory
from app.repositories import price_repo
from app.services.price_provider import PriceProvider, Quote, to_price
from app.services.price_service import PriceService

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


class FakeProvider(PriceProvider):
    """Stands in for Yahoo: `history` is the daily feed, `settled` the quote snapshot."""

    def __init__(
        self, history: dict[date, Decimal], settled: tuple[date, Decimal] | None = None, quote: Quote | None = None
    ):
        self.history = history
        self.settled = settled
        self.settled_calls = 0
        self.quote = quote
        self.quote_calls = 0

    def get_quote(self, symbol: str) -> Quote | None:
        self.quote_calls += 1
        return self.quote

    def get_history(self, symbol: str, start: date, end: date) -> dict[date, Decimal]:
        return dict(self.history)

    def get_currency(self, symbol: str) -> str | None:
        return "EUR"

    def get_last_settled_close(self, symbol: str) -> tuple[date, Decimal] | None:
        self.settled_calls += 1
        return self.settled


def make_asset(db, **overrides) -> Asset:
    fields = {"ticker": "ACME", "name": "Acme Inc", "asset_class": "equity",
              "native_currency": "EUR", "yahoo_symbol": "ACME", "price_scale": Decimal(1)}
    fields.update(overrides)
    asset = Asset(**fields)
    db.add(asset)
    db.flush()
    return asset


def test_session_missing_from_the_daily_feed_is_repaired_from_the_quote_snapshot(db_session):
    asset = make_asset(db_session)
    # What a European listing looks like today: the daily feed stops two days back even though
    # yesterday's session traded and settled.
    stale_daily = {TODAY - timedelta(days=2): Decimal("42.53")}
    provider = FakeProvider(stale_daily, settled=(YESTERDAY, Decimal("42.64")))

    price = PriceService(provider).get_daily_price(db_session, asset)

    assert price == Decimal("42.64")
    assert provider.settled_calls == 1
    assert price_repo.get_latest_price(db_session, asset.id).date == YESTERDAY


def test_a_current_daily_feed_is_left_alone_and_costs_no_extra_request(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider({YESTERDAY: Decimal("251.89")}, settled=(YESTERDAY, Decimal("999.0")))

    price = PriceService(provider).get_daily_price(db_session, asset)

    assert price == Decimal("251.89")
    assert provider.settled_calls == 0


def test_a_real_daily_close_always_outranks_the_quote_snapshot(db_session):
    asset = make_asset(db_session)
    # Daily feed is behind, so the snapshot is fetched — but it lands on a day the feed already
    # covers, and the published close is the authoritative one.
    provider = FakeProvider({TODAY - timedelta(days=3): Decimal("10.0")}, settled=(TODAY - timedelta(days=3), Decimal("99.0")))

    price = PriceService(provider).get_daily_price(db_session, asset)

    assert price == Decimal("10.0")


def test_repair_is_scaled_like_any_other_price_for_pence_quoted_listings(db_session):
    # Yahoo quotes London listings in pence, so a repaired close needs the same *0.01 that
    # daily closes get — otherwise the repair would overvalue the position 100x.
    asset = make_asset(db_session, ticker="WISE", yahoo_symbol="WISE.L", price_scale=Decimal("0.01"))
    provider = FakeProvider({TODAY - timedelta(days=2): Decimal("900.0")}, settled=(YESTERDAY, Decimal("915.0")))

    price = PriceService(provider).get_daily_price(db_session, asset)

    assert price == Decimal("9.15")


def test_nothing_to_repair_leaves_the_cache_untouched(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider({}, settled=None)

    assert PriceService(provider).get_daily_price(db_session, asset) is None
    assert provider.settled_calls == 1


def test_yfinance_search_keeps_holdable_listings_with_their_exchange(monkeypatch):
    import yfinance

    from app.services.price_provider import YFinanceProvider

    class FakeSearch:
        def __init__(self, query, max_results, news_count):
            self.quotes = [
                {"symbol": "IQQW.DE", "longname": "iShares MSCI World UCITS ETF USD (Dist)", "exchDisp": "XETRA", "quoteType": "ETF", "typeDisp": "ETF"},
                {"symbol": "IQQW.MU", "shortname": "iShs-MSCI World UCITS ETF R", "exchDisp": "Munich", "quoteType": "ETF", "typeDisp": "ETF"},
                {"symbol": "IQ=F", "shortname": "a future", "exchDisp": "CME", "quoteType": "FUTURE"},  # not something to hold
                {"symbol": "", "quoteType": "ETF"},
            ]

    monkeypatch.setattr(yfinance, "Search", FakeSearch)

    matches = YFinanceProvider().search("IQQW")

    assert [(m.symbol, m.exchange) for m in matches] == [("IQQW.DE", "XETRA"), ("IQQW.MU", "Munich")]
    assert matches[1].name == "iShs-MSCI World UCITS ETF R"  # the short name when there's no long one


def test_yfinance_search_failing_finds_nothing(monkeypatch):
    import yfinance

    from app.services.price_provider import YFinanceProvider

    def boom(*args, **kwargs):
        raise RuntimeError("Yahoo is down")

    monkeypatch.setattr(yfinance, "Search", boom)

    assert YFinanceProvider().search("IQQW") == []


def test_pence_quotes_scale_to_exact_pounds(db_session):
    # 1234.5p is exactly £12.345; float arithmetic would make it 12.345000000000001.
    asset = make_asset(db_session, ticker="WISE", yahoo_symbol="WISE.L", price_scale=Decimal("0.01"))
    provider = FakeProvider({YESTERDAY: Decimal("1234.5")})

    PriceService(provider).get_daily_price(db_session, asset)

    assert price_repo.get_latest_price(db_session, asset.id).close_price == Decimal("12.345")


def test_a_provider_float_becomes_the_decimal_it_was_published_as():
    assert to_price(42.64) == Decimal("42.64")
    assert to_price(0.1 + 0.2) == Decimal("0.30000000000000004")  # what the float actually holds
    assert isinstance(to_price(3), Decimal)


# -- live quotes -----------------------------------------------------------

NOW = datetime(2026, 10, 19, 14, 0)  # naive UTC, like the columns
AMS = timezone(timedelta(hours=2))
QUOTE = Quote(price=Decimal("43.10"), quoted_at=datetime(2026, 10, 19, 15, 45, tzinfo=AMS))


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def test_a_quote_is_stored_scaled_and_in_utc(db_session):
    asset = make_asset(db_session, ticker="WISE", yahoo_symbol="WISE.L", price_scale=Decimal("0.01"))
    provider = FakeProvider({}, quote=Quote(price=Decimal("1234.5"), quoted_at=QUOTE.quoted_at))

    assert PriceService(provider, clock=Clock(NOW)).refresh_quote(db_session, asset) is True

    assert asset.quote_price == Decimal("12.345")
    assert asset.quoted_at == datetime(2026, 10, 19, 13, 45)
    assert asset.quote_checked_at == NOW


def test_a_quote_is_fetched_at_most_once_an_hour(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider({}, quote=QUOTE)
    clock = Clock(NOW)
    service = PriceService(provider, clock=clock)

    assert service.refresh_quote(db_session, asset) is True
    clock.now = NOW + timedelta(minutes=30)
    assert service.refresh_quote(db_session, asset) is False
    # The hourly timer firing a few seconds early still finds it due.
    clock.now = NOW + timedelta(minutes=59, seconds=50)
    assert service.refresh_quote(db_session, asset) is True
    assert provider.quote_calls == 2


def test_a_failed_quote_keeps_the_previous_one_and_still_waits_an_hour(db_session):
    asset = make_asset(db_session)
    clock = Clock(NOW)
    service = PriceService(FakeProvider({}, quote=QUOTE), clock=clock)
    service.refresh_quote(db_session, asset)

    clock.now = NOW + timedelta(hours=1)
    service.provider = FakeProvider({}, quote=None)
    assert service.refresh_quote(db_session, asset) is True
    assert asset.quote_price == Decimal("43.10")
    assert asset.quote_checked_at == NOW + timedelta(hours=1)

    clock.now = NOW + timedelta(hours=1, minutes=10)
    assert service.refresh_quote(db_session, asset) is False


def test_an_asset_without_a_symbol_is_never_quoted(db_session):
    asset = make_asset(db_session, yahoo_symbol=None)
    provider = FakeProvider({}, quote=QUOTE)
    assert PriceService(provider, clock=Clock(NOW)).refresh_quote(db_session, asset) is False
    assert provider.quote_calls == 0


def _quoted_asset(db, close_on: date, **overrides) -> Asset:
    fields = {"quote_price": Decimal("43.10"), "quoted_at": datetime(2026, 10, 19, 13, 45),
              "quote_checked_at": NOW - timedelta(minutes=10), "price_checked_at": date.today()}
    fields.update(overrides)
    asset = make_asset(db, **fields)
    db.add(PriceHistory(asset_id=asset.id, date=close_on, close_price=Decimal("42.00")))
    db.flush()
    return asset


def test_the_current_price_is_the_live_quote_while_it_is_fresh(db_session):
    asset = _quoted_asset(db_session, close_on=date(2026, 10, 18))

    current = PriceService(FakeProvider({}), clock=Clock(NOW)).get_current_price(db_session, asset)

    assert current.price == Decimal("43.10")
    assert current.price_date == date(2026, 10, 19)
    assert current.quoted_at == datetime(2026, 10, 19, 13, 45, tzinfo=timezone.utc)


def test_a_quote_two_hours_without_a_refresh_falls_back_to_the_close(db_session):
    asset = _quoted_asset(db_session, close_on=date(2026, 10, 18))
    clock = Clock(NOW + timedelta(hours=2))

    current = PriceService(FakeProvider({}), clock=clock).get_current_price(db_session, asset)

    assert current.price == Decimal("42.00")
    assert current.quoted_at is None


def test_a_quote_older_than_the_latest_close_never_outranks_it(db_session):
    asset = _quoted_asset(db_session, close_on=date(2026, 10, 20))

    current = PriceService(FakeProvider({}), clock=Clock(NOW)).get_current_price(db_session, asset)

    assert current.price == Decimal("42.00")
    assert current.quoted_at is None


def test_todays_fx_rate_is_the_live_quote(db_session):
    service = PriceService(FakeProvider({}, quote=Quote(Decimal("0.92"), QUOTE.quoted_at)), clock=Clock(NOW))
    fx_asset = service._fx_asset(db_session, "USD")
    fx_asset.price_checked_at = date.today()
    db_session.add(PriceHistory(asset_id=fx_asset.id, date=date(2026, 10, 18), close_price=Decimal("0.90")))
    assert service.refresh_fx_quote(db_session, "USD") is True
    assert service.refresh_fx_quote(db_session, "EUR") is False

    assert service.get_fx_rate(db_session, "USD") == Decimal("0.92")
    assert service.get_fx_rate(db_session, "USD", date(2026, 10, 18)) == Decimal("0.90")
