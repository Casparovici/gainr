"""A position's analyst checklist: computed from Yahoo's figures where it has them, listed as
unavailable (with where to look) where it doesn't."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.asset import Asset
from app.services import fundamentals_metrics as fm
from app.services.fundamentals_metrics import FundSnapshot, MetricInputs
from app.services.fundamentals_provider import CompanyEvents, Financials, FundamentalsProvider
from app.services.fundamentals_service import FundamentalsService

D = Decimal


def years(**by_row) -> dict[str, dict[date, Decimal]]:
    """{row: [newest, ..., oldest]} -> {row: {FY end: value}} with one annual period per entry."""
    return {
        row: {date(2025 - i, 12, 31): D(str(v)) for i, v in enumerate(values)}
        for row, values in by_row.items()
    }


def metric(result: fm.PositionMetrics, key: str) -> fm.MetricResult:
    return next(m for m in result.metrics if m.key == key)


def test_a_bank_gets_cost_income_from_its_statements_and_a_gap_for_what_yahoo_lacks():
    inputs = MetricInputs(
        info={"returnOnEquity": 0.0912},
        annual=years(revenue=[9000, 8000], operating_expense=[5400, 5200], net_interest_income=[6500, 6000]),
        currency="EUR",
    )

    result = fm.build_metrics(fm.PROFILES["ABN.AS"], inputs)

    assert result.lens == "Established / value" and result.currency == "EUR"
    assert metric(result, "cost_income").value == D(60)
    assert [(h.label, h.value) for h in metric(result, "cost_income").history] == [("FY2024", D(65)), ("FY2025", D(60))]
    assert metric(result, "net_interest_income").value == D(6500)
    assert metric(result, "roe").value == D("9.12")
    cet1 = metric(result, "cet1")
    assert cet1.value is None and cet1.text is None
    assert "quarterly results" in cet1.source_hint


def test_an_available_metric_carries_no_source_hint():
    inputs = MetricInputs(info={"revenueGrowth": 0.5}, annual={})

    result = fm.build_metrics(fm.PROFILES["MELI"], inputs)

    growth = metric(result, "revenue_growth")
    assert growth.value == D(50) and growth.source_hint is None


def test_margin_trend_uses_the_statements_and_the_latest_figure_uses_yahoos_snapshot():
    inputs = MetricInputs(
        info={"operatingMargins": 0.067},
        annual=years(revenue=[1000, 800, 600], operating_income=[80, 56, 30]),
    )

    margin = metric(fm.build_metrics(fm.PROFILES["MELI"], inputs), "operating_margin")

    assert margin.value == D("6.7")
    assert [h.value for h in margin.history] == [D(5), D(7), D(8)]


def test_capex_against_cash_flow_and_depreciation():
    inputs = MetricInputs(annual=years(capex=[-150, -100], operating_cash_flow=[300, 250], depreciation=[75, 80], free_cash_flow=[150, 150]))

    result = fm.build_metrics(fm.PROFILES["AMZN"], inputs)
    googl = fm.build_metrics(fm.PROFILES["GOOGL"], inputs)

    assert metric(result, "capex_to_depreciation").value == D(2)
    assert metric(googl, "capex_to_ocf").value == D(50)
    assert metric(googl, "capex").value == D(150)  # shown as spend, not as a negative


def test_cash_conversion_needs_positive_ebitda():
    profitable = MetricInputs(info={"ebitdaMargins": 0.1, "totalRevenue": 1000}, annual=years(operating_cash_flow=[-50]))
    loss_making = MetricInputs(info={"ebitdaMargins": -0.1, "totalRevenue": 1000}, annual=years(operating_cash_flow=[-50]))

    assert metric(fm.build_metrics(fm.PROFILES["TNIE.DE"], profitable), "cash_conversion").value == D(-50)
    assert metric(fm.build_metrics(fm.PROFILES["TNIE.DE"], loss_making), "cash_conversion").value is None


def test_fund_concentration_mix_valuation_and_cost():
    fund = FundSnapshot(
        top_holdings=[("NVDA", D("11.3")), ("MU", D("11.0")), ("AMD", D("10.7"))],
        sectors={"technology": D(100), "utilities": D(0)},
        holdings_earnings_yield=D("0.025"),
        expense_ratio_pct=D("0.35"),
    )
    result = fm.build_metrics(fm.PROFILES["SMH.MI"], MetricInputs(info={"totalAssets": 8e9}, fund=fund))

    assert metric(result, "top10").value == D("33.0")
    assert metric(result, "top_holdings").text.startswith("NVDA 11.3%")
    assert metric(result, "holdings_pe").value == D(40)
    assert metric(result, "ter").value == D("0.35")
    assert metric(result, "aum").value == D(8000000000)


def test_a_fund_whose_holdings_lose_money_has_no_pe_and_says_why():
    fund = FundSnapshot(top_holdings=[("RKLB", D(6))], holdings_earnings_yield=None)

    pe = metric(fm.build_metrics(fm.PROFILES["JEDI.PA"], MetricInputs(fund=fund)), "holdings_pe")

    assert pe.value is None and "zero or negative" in pe.detail


def test_sector_mix_names_the_largest_sectors():
    fund = FundSnapshot(sectors={"industrials": D("69.7"), "utilities": D("14.0"), "technology": D("12.9"), "energy": D(0)})

    mix = metric(fm.build_metrics(fm.PROFILES["GRID.MI"], MetricInputs(fund=fund)), "sector_mix")

    assert mix.text == "Industrials 70%, Utilities 14%, Technology 13%"


def prices(daily_returns: list[float], start=date(2026, 1, 1)) -> dict[date, Decimal]:
    closes, level = {}, 100.0
    for i, r in enumerate([0.0] + daily_returns):
        level *= 1 + r
        closes[start + timedelta(days=i)] = D(str(level))
    return closes


def test_correlation_with_the_nasdaq_uses_the_days_both_traded():
    moves = [0.01 * ((-1) ** i) * (1 + i % 3) for i in range(60)]
    same = MetricInputs(prices={"BTC-EUR": prices(moves), "^IXIC": prices(moves)})
    opposite = MetricInputs(prices={"BTC-EUR": prices(moves), "^IXIC": prices([-m for m in moves])})

    assert metric(fm.build_metrics(fm.PROFILES["BTC-EUR"], same), "nasdaq_corr").value == D("1.0")
    assert metric(fm.build_metrics(fm.PROFILES["BTC-EUR"], opposite), "nasdaq_corr").value == D("-1.0")


def test_too_little_overlap_gives_no_correlation():
    short = MetricInputs(prices={"BTC-EUR": prices([0.01] * 10), "^IXIC": prices([0.01] * 10)})

    assert metric(fm.build_metrics(fm.PROFILES["BTC-EUR"], short), "nasdaq_corr").value is None


def test_eth_btc_ratio_and_its_change():
    eth = {date(2026, 1, 1): D(100), date(2026, 6, 1): D(150)}
    btc = {date(2026, 1, 1): D(1000), date(2026, 6, 1): D(1000)}

    ratio = metric(fm.build_metrics(fm.PROFILES["ETH-EUR"], MetricInputs(prices={"ETH-EUR": eth, "BTC-EUR": btc})), "eth_btc")

    assert ratio.value == D("0.15") and "+50%" in ratio.detail


def test_every_profile_lists_each_metric_once_and_hints_at_what_yahoo_lacks():
    for symbol, profile in fm.PROFILES.items():
        keys = [s.key for s in profile.specs]
        assert len(keys) == len(set(keys)), symbol
        for spec in profile.specs:
            if spec.compute is None:
                assert spec.source_hint, f"{symbol}/{spec.key} is unavailable but says nowhere to look"


class FakeProvider(FundamentalsProvider):
    def __init__(self, inputs: MetricInputs):
        self.inputs, self.calls = inputs, []

    def get_news(self, symbol):
        return []

    def get_financials(self, symbol):
        return Financials()

    def get_company_events(self, symbol):
        return CompanyEvents()

    def get_metric_inputs(self, symbol, kind, price_symbols=()):
        self.calls.append((symbol, kind, price_symbols))
        return self.inputs


def make_asset(db, yahoo_symbol: str) -> Asset:
    asset = Asset(ticker=yahoo_symbol, name="X", asset_class="equity", native_currency="EUR", yahoo_symbol=yahoo_symbol)
    db.add(asset)
    db.flush()
    return asset


def test_a_position_without_a_checklist_answers_empty_without_fetching(db_session):
    provider = FakeProvider(MetricInputs())

    out = FundamentalsService(provider).get_metrics(db_session, make_asset(db_session, "AAPL"))

    assert out.metrics == [] and out.lens is None
    assert provider.calls == []


def test_the_checklist_is_fetched_once_and_then_served_from_cache(db_session):
    provider = FakeProvider(MetricInputs(info={"revenueGrowth": 0.5}, currency="USD"))
    service = FundamentalsService(provider)
    asset = make_asset(db_session, "MELI")

    first = service.get_metrics(db_session, asset)
    second = service.get_metrics(db_session, asset)

    assert provider.calls == [("MELI", "equity", ())]
    assert first == second
    assert first.lens == "Growth company" and first.currency == "USD"
    assert next(m for m in first.metrics if m.key == "revenue_growth").value == D(50)


def test_the_crypto_checklist_asks_for_the_index_it_compares_against(db_session):
    provider = FakeProvider(MetricInputs())

    FundamentalsService(provider).get_metrics(db_session, make_asset(db_session, "BTC-EUR"))

    assert provider.calls == [("BTC-EUR", "crypto", ("^IXIC",))]


@pytest.mark.parametrize("symbol", sorted(fm.PROFILES))
def test_an_empty_provider_answer_degrades_to_an_all_unavailable_list(db_session, symbol):
    out = FundamentalsService(FakeProvider(MetricInputs())).get_metrics(db_session, make_asset(db_session, symbol))

    assert out.metrics and all(m.value is None and m.text is None for m in out.metrics)
