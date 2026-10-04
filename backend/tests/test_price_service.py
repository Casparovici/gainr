from datetime import date, timedelta
from decimal import Decimal

from app.models.asset import Asset
from app.repositories import price_repo
from app.services.price_provider import PriceProvider
from app.services.price_service import PriceService

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


class FakeProvider(PriceProvider):
    """Stands in for Yahoo: `history` is the daily feed, `settled` the quote snapshot."""

    def __init__(self, history: dict[date, float], settled: tuple[date, float] | None = None):
        self.history = history
        self.settled = settled
        self.settled_calls = 0

    def get_history(self, symbol: str, start: date, end: date) -> dict[date, float]:
        return dict(self.history)

    def get_currency(self, symbol: str) -> str | None:
        return "EUR"

    def get_last_settled_close(self, symbol: str) -> tuple[date, float] | None:
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
    stale_daily = {TODAY - timedelta(days=2): 42.53}
    provider = FakeProvider(stale_daily, settled=(YESTERDAY, 42.64))

    price = PriceService(provider).get_daily_price(db_session, asset)

    assert price == Decimal("42.64")
    assert provider.settled_calls == 1
    assert price_repo.get_latest_price(db_session, asset.id).date == YESTERDAY


def test_a_current_daily_feed_is_left_alone_and_costs_no_extra_request(db_session):
    asset = make_asset(db_session)
    provider = FakeProvider({YESTERDAY: 251.89}, settled=(YESTERDAY, 999.0))

    price = PriceService(provider).get_daily_price(db_session, asset)

    assert price == Decimal("251.89")
    assert provider.settled_calls == 0


def test_a_real_daily_close_always_outranks_the_quote_snapshot(db_session):
    asset = make_asset(db_session)
    # Daily feed is behind, so the snapshot is fetched — but it lands on a day the feed already
    # covers, and the published close is the authoritative one.
    provider = FakeProvider({TODAY - timedelta(days=3): 10.0}, settled=(TODAY - timedelta(days=3), 99.0))

    price = PriceService(provider).get_daily_price(db_session, asset)

    assert price == Decimal("10.0")


def test_repair_is_scaled_like_any_other_price_for_pence_quoted_listings(db_session):
    # Yahoo quotes London listings in pence, so a repaired close needs the same *0.01 that
    # daily closes get — otherwise the repair would overvalue the position 100x.
    asset = make_asset(db_session, ticker="WISE", yahoo_symbol="WISE.L", price_scale=Decimal("0.01"))
    provider = FakeProvider({TODAY - timedelta(days=2): 900.0}, settled=(YESTERDAY, 915.0))

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
