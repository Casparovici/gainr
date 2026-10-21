"""Per-position analyst checklists: the handful of metrics that decide how each holding is
judged (a bank on CET1 and cost/income, a growth stock on margin vs growth, a thematic ETF on
concentration and holdings' valuation), filled in from Yahoo where Yahoo has them.

Yahoo only carries part of any checklist -- segment results (AWS, Google Cloud), bank capital,
cRPO or on-chain data live in company reports and other feeds. Those metrics stay on the list,
marked unavailable with a hint on where to look, so the checklist is complete and a gap is
visible instead of silently missing. Nothing is estimated or back-filled.

Computation is pure over `MetricInputs`, which the provider fills from yfinance, so the maths is
testable without a network.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable

HISTORY_PERIODS = 4

# Canonical statement rows the provider fills (annual, per period end).
REVENUE = "revenue"
OPERATING_INCOME = "operating_income"
NET_INCOME = "net_income"
OPERATING_EXPENSE = "operating_expense"
NET_INTEREST_INCOME = "net_interest_income"
FREE_CASH_FLOW = "free_cash_flow"
OPERATING_CASH_FLOW = "operating_cash_flow"
CAPEX = "capex"
DEPRECIATION = "depreciation"
INVENTORY = "inventory"


@dataclass
class FundSnapshot:
    # Largest first, weights as a percentage of the fund.
    top_holdings: list[tuple[str, Decimal]] = field(default_factory=list)
    sectors: dict[str, Decimal] = field(default_factory=dict)  # percentage of the fund
    # Aggregate earnings / price of the holdings (Yahoo's "Price/Earnings" is an earnings yield),
    # None when the holdings' earnings are zero or negative.
    holdings_earnings_yield: Decimal | None = None
    expense_ratio_pct: Decimal | None = None


@dataclass
class MetricInputs:
    info: dict = field(default_factory=dict)
    annual: dict[str, dict[date, Decimal]] = field(default_factory=dict)
    fund: FundSnapshot | None = None
    # Daily closes per symbol, for the cross-asset metrics (correlation, ratios).
    prices: dict[str, dict[date, Decimal]] = field(default_factory=dict)
    currency: str | None = None


@dataclass
class HistoryPoint:
    label: str
    value: Decimal


@dataclass
class Computed:
    value: Decimal | None = None
    text: str | None = None
    detail: str | None = None
    history: list[HistoryPoint] = field(default_factory=list)


@dataclass
class MetricSpec:
    key: str
    label: str
    unit: str  # "pct" | "multiple" | "amount" | "number" | "text"
    why: str | None = None
    compute: Callable[[MetricInputs], Computed | None] | None = None
    # Where to find it when Yahoo doesn't carry it.
    source_hint: str | None = None


@dataclass
class MetricResult:
    key: str
    label: str
    unit: str
    why: str | None
    value: Decimal | None
    text: str | None
    detail: str | None
    history: list[HistoryPoint]
    source_hint: str | None


@dataclass
class PositionMetrics:
    lens: str
    currency: str | None
    metrics: list[MetricResult]


@dataclass
class Profile:
    lens: str
    kind: str  # "equity" | "etf" | "crypto" | "gold" -- what the provider needs to fetch
    specs: list[MetricSpec]
    # Extra symbols whose daily closes the specs compare against.
    price_symbols: tuple[str, ...] = ()


# -- building blocks ---------------------------------------------------------------------------


def _d(value) -> Decimal | None:
    if value is None or value != value:
        return None
    try:
        return Decimal(str(float(value)))
    except (TypeError, ValueError):
        return None


def _series(inputs: MetricInputs, row: str) -> list[tuple[date, Decimal]]:
    """Newest first."""
    return sorted(inputs.annual.get(row, {}).items(), reverse=True)


def _label(period_end: date) -> str:
    return f"FY{period_end.year}"


def _history(points: list[tuple[date, Decimal]]) -> list[HistoryPoint]:
    """The newest few periods, oldest first, the way a trend reads."""
    return [HistoryPoint(_label(d), v) for d, v in reversed(points[:HISTORY_PERIODS])]


def info_pct(field_name: str, scale: int = 100, detail: str | None = None) -> Callable[[MetricInputs], Computed | None]:
    def compute(inputs: MetricInputs) -> Computed | None:
        value = _d(inputs.info.get(field_name))
        return Computed(value=value * scale, detail=detail) if value is not None else None

    return compute


def info_number(field_name: str, detail: str | None = None) -> Callable[[MetricInputs], Computed | None]:
    def compute(inputs: MetricInputs) -> Computed | None:
        value = _d(inputs.info.get(field_name))
        return Computed(value=value, detail=detail) if value is not None else None

    return compute


def margin_with_trend(numerator: str, info_field: str | None = None, detail: str | None = None) -> Callable[[MetricInputs], Computed | None]:
    """A margin on revenue: the latest figure from Yahoo's snapshot when it has one, the trend
    from the annual statements -- so a margin can be read as improving or squeezed."""

    def compute(inputs: MetricInputs) -> Computed | None:
        revenue = dict(_series(inputs, REVENUE))
        points = [
            (d, v / revenue[d] * 100) for d, v in _series(inputs, numerator) if revenue.get(d)
        ]
        latest = _d(inputs.info.get(info_field)) if info_field else None
        value = latest * 100 if latest is not None else (points[0][1] if points else None)
        if value is None:
            return None
        return Computed(value=value, history=_history(points), detail=detail)

    return compute


def ratio_of_rows(numerator: str, denominator: str, absolute: bool = False) -> Callable[[MetricInputs], Computed | None]:
    def compute(inputs: MetricInputs) -> Computed | None:
        den = dict(_series(inputs, denominator))
        points = []
        for d, v in _series(inputs, numerator):
            if den.get(d):
                points.append((d, (abs(v) if absolute else v) / abs(den[d]) * 100))
        return Computed(value=points[0][1], history=_history(points)) if points else None

    return compute


def row_amount(row: str, absolute: bool = False) -> Callable[[MetricInputs], Computed | None]:
    def compute(inputs: MetricInputs) -> Computed | None:
        points = [(d, abs(v) if absolute else v) for d, v in _series(inputs, row)]
        return Computed(value=points[0][1], history=_history(points)) if points else None

    return compute


def capex_to_depreciation(inputs: MetricInputs) -> Computed | None:
    depreciation = dict(_series(inputs, DEPRECIATION))
    points = [(d, abs(v) / depreciation[d]) for d, v in _series(inputs, CAPEX) if depreciation.get(d)]
    return Computed(value=points[0][1], history=_history(points)) if points else None


def cash_conversion(inputs: MetricInputs) -> Computed | None:
    """Operating cash flow as a share of EBITDA -- how much of the reported profit turned into
    cash, which for a hardware business is mostly an inventory story."""
    ocf = _series(inputs, OPERATING_CASH_FLOW)
    margin, revenue = _d(inputs.info.get("ebitdaMargins")), _d(inputs.info.get("totalRevenue"))
    if not ocf or margin is None or revenue is None or margin * revenue <= 0:
        return None
    return Computed(value=ocf[0][1] / (margin * revenue) * 100, detail=f"{_label(ocf[0][0])} operating cash flow vs EBITDA")


def ebitda_margin(inputs: MetricInputs) -> Computed | None:
    value = _d(inputs.info.get("ebitdaMargins"))
    return Computed(value=value * 100, detail="As Yahoo reports it: not adjusted for one-offs or share-based pay") if value else None


# -- funds -------------------------------------------------------------------------------------


def top_concentration(count: int) -> Callable[[MetricInputs], Computed | None]:
    def compute(inputs: MetricInputs) -> Computed | None:
        if inputs.fund is None or not inputs.fund.top_holdings:
            return None
        top = inputs.fund.top_holdings[:count]
        return Computed(value=sum((w for _, w in top), Decimal(0)), detail=f"Top {len(top)} of the fund's holdings")

    return compute


def top_holdings_text(count: int = 5) -> Callable[[MetricInputs], Computed | None]:
    def compute(inputs: MetricInputs) -> Computed | None:
        if inputs.fund is None or not inputs.fund.top_holdings:
            return None
        return Computed(text=", ".join(f"{symbol} {weight:.1f}%" for symbol, weight in inputs.fund.top_holdings[:count]))

    return compute


def sector_mix(count: int = 3) -> Callable[[MetricInputs], Computed | None]:
    def compute(inputs: MetricInputs) -> Computed | None:
        if inputs.fund is None:
            return None
        ranked = sorted(((n, w) for n, w in inputs.fund.sectors.items() if w > 0), key=lambda p: p[1], reverse=True)
        if not ranked:
            return None
        return Computed(text=", ".join(f"{name.replace('_', ' ').capitalize()} {weight:.0f}%" for name, weight in ranked[:count]))

    return compute


def holdings_pe(inputs: MetricInputs) -> Computed | None:
    if inputs.fund is None:
        return None
    yield_ = inputs.fund.holdings_earnings_yield
    if yield_ is None or yield_ <= 0:
        return Computed(detail="The holdings' combined earnings are zero or negative, so there is no P/E")
    return Computed(value=1 / yield_, detail="Trailing, across the fund's holdings")


def expense_ratio(inputs: MetricInputs) -> Computed | None:
    if inputs.fund is None or inputs.fund.expense_ratio_pct is None:
        return None
    return Computed(value=inputs.fund.expense_ratio_pct)


def fund_yield(inputs: MetricInputs) -> Computed | None:
    value = _d(inputs.info.get("yield"))
    return Computed(value=value * 100) if value else None


# -- cross-asset -------------------------------------------------------------------------------


def _aligned_returns(a: dict[date, Decimal], b: dict[date, Decimal]) -> tuple[list[float], list[float]]:
    """Returns between consecutive days both series traded: a coin that trades at the weekend
    against an index that doesn't would otherwise compare a one-day move with a three-day one."""
    days = sorted(set(a) & set(b))
    xs, ys = [], []
    for prev, day in zip(days, days[1:]):
        if a[prev] and b[prev]:
            xs.append(float(a[day] / a[prev] - 1))
            ys.append(float(b[day] / b[prev] - 1))
    return xs, ys


def correlation_with(symbol: str, other: str, label: str) -> Callable[[MetricInputs], Computed | None]:
    def compute(inputs: MetricInputs) -> Computed | None:
        xs, ys = _aligned_returns(inputs.prices.get(symbol, {}), inputs.prices.get(other, {}))
        if len(xs) < 30:
            return None
        mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        var_x, var_y = sum((x - mean_x) ** 2 for x in xs), sum((y - mean_y) ** 2 for y in ys)
        if var_x == 0 or var_y == 0:
            return None
        return Computed(value=Decimal(str(round(cov / (var_x * var_y) ** 0.5, 2))), detail=f"Daily returns over {len(xs)} shared trading days vs {label}")

    return compute


def price_ratio(numerator: str, denominator: str) -> Callable[[MetricInputs], Computed | None]:
    def compute(inputs: MetricInputs) -> Computed | None:
        a, b = inputs.prices.get(numerator, {}), inputs.prices.get(denominator, {})
        shared = sorted(set(a) & set(b))
        if not shared or not b[shared[-1]]:
            return None
        latest = a[shared[-1]] / b[shared[-1]]
        first = a[shared[0]] / b[shared[0]] if b[shared[0]] else None
        change = f"{(latest / first - 1) * 100:+.0f}% over the period" if first else None
        return Computed(value=latest, detail=change)

    return compute


def price_level(symbol: str) -> Callable[[MetricInputs], Computed | None]:
    def compute(inputs: MetricInputs) -> Computed | None:
        closes = inputs.prices.get(symbol, {})
        if not closes:
            return None
        days = sorted(closes)
        latest, first = closes[days[-1]], closes[days[0]]
        change = f"{(latest / first - 1) * 100:+.1f}% over the past year" if first else None
        return Computed(value=latest, detail=change)

    return compute


# -- the catalogue -----------------------------------------------------------------------------


def _na(key: str, label: str, unit: str, why: str | None, source: str) -> MetricSpec:
    return MetricSpec(key=key, label=label, unit=unit, why=why, source_hint=source)


def _spec(key: str, label: str, unit: str, compute, why: str | None = None, source: str | None = None) -> MetricSpec:
    return MetricSpec(key=key, label=label, unit=unit, why=why, compute=compute, source_hint=source)


QUARTERLY_REPORT = "The company's quarterly results"
NEWS_TAB = "Qualitative: follow it in the News tab"
WGC = "World Gold Council"
FRED = "FRED (St. Louis Fed)"

REVENUE_GROWTH = _spec("revenue_growth", "Revenue growth", "pct", info_pct("revenueGrowth", detail="Latest quarter vs a year earlier"))
OPERATING_MARGIN = _spec("operating_margin", "Operating margin", "pct", margin_with_trend(OPERATING_INCOME, "operatingMargins"))
FCF_MARGIN = _spec("fcf_margin", "Free cash flow margin", "pct", ratio_of_rows(FREE_CASH_FLOW, REVENUE))
FREE_CASH_FLOW_AMOUNT = _spec("free_cash_flow", "Free cash flow", "amount", row_amount(FREE_CASH_FLOW))
CAPEX_AMOUNT = _spec("capex", "Capital expenditure", "amount", row_amount(CAPEX, absolute=True))
CAPEX_TO_OCF = _spec("capex_to_ocf", "Capex / operating cash flow", "pct", ratio_of_rows(CAPEX, OPERATING_CASH_FLOW, absolute=True))
FORWARD_PE = _spec("forward_pe", "Forward P/E", "multiple", info_number("forwardPE"))
PEG = _spec("peg", "PEG ratio", "multiple", info_number("pegRatio"), why="Forward P/E against growth")
ROE = _spec("roe", "Return on equity", "pct", info_pct("returnOnEquity"))

PROFILES: dict[str, Profile] = {
    "ABN.AS": Profile("Established / value", "equity", [
        _spec("net_interest_income", "Net interest income", "amount", row_amount(NET_INTEREST_INCOME), why="Rate sensitivity"),
        _na("nim", "Net interest margin", "pct", "Rate sensitivity", QUARTERLY_REPORT),
        _spec("cost_income", "Cost/income ratio", "pct", ratio_of_rows(OPERATING_EXPENSE, REVENUE), why="The restructuring story"),
        _na("cet1", "CET1 ratio", "pct", "Capacity for buybacks and dividends", QUARTERLY_REPORT + " (capital section)"),
        _na("cost_of_risk", "Cost of risk", "pct", "Dutch mortgages and corporate loans", QUARTERLY_REPORT),
        _spec("roe", "Return on equity", "pct", info_pct("returnOnEquity"), why="Compare with cost of equity, which Yahoo doesn't carry"),
    ]),
    "GOOGL": Profile("Mature compounder", "equity", [
        _na("cloud_growth", "Google Cloud revenue growth", "pct", None, QUARTERLY_REPORT + " (segments)"),
        _na("cloud_margin", "Google Cloud operating margin", "pct", None, QUARTERLY_REPORT + " (segments)"),
        _na("search_growth", "Search & ads revenue growth", "pct", "AI disruption risk", QUARTERLY_REPORT + " (segments)"),
        CAPEX_AMOUNT, FREE_CASH_FLOW_AMOUNT,
        _spec("capex_to_ocf", "Capex / operating cash flow", "pct", ratio_of_rows(CAPEX, OPERATING_CASH_FLOW, absolute=True), why="Capex vs free cash flow"),
        OPERATING_MARGIN,
        _na("regulatory", "Regulatory exposure", "text", "EU fines, DOJ remedies", NEWS_TAB),
    ]),
    "AMZN": Profile("Mature compounder", "equity", [
        _na("aws_growth", "AWS revenue growth", "pct", None, QUARTERLY_REPORT + " (segments)"),
        _na("aws_margin", "AWS operating margin", "pct", None, QUARTERLY_REPORT + " (segments)"),
        _spec("free_cash_flow", "Free cash flow after capex", "amount", row_amount(FREE_CASH_FLOW)),
        _spec("operating_margin", "Operating margin (whole group)", "pct", margin_with_trend(OPERATING_INCOME, "operatingMargins", detail="Whole group; the retail segment on its own is in the company's results"), why="Ads and logistics efficiency"),
        _spec("capex_to_depreciation", "Capex / depreciation", "multiple", capex_to_depreciation, why="Capex and depreciation trend"),
        FORWARD_PE, PEG, REVENUE_GROWTH,
    ]),
    "NOW": Profile("Growth company", "equity", [
        _spec("revenue_growth", "Revenue growth", "pct", info_pct("revenueGrowth", detail="Total revenue, latest quarter vs a year earlier; subscriptions are nearly all of it"), why="Subscription revenue growth"),
        _na("crpo", "Current remaining performance obligations", "amount", "Forward bookings", QUARTERLY_REPORT),
        _na("nrr", "Net revenue retention", "pct", "The ~98% renewal rate", QUARTERLY_REPORT),
        FCF_MARGIN,
        _na("ai_revenue", "AI product revenue (Now Assist)", "amount", "Proof against the \"AI replaces SaaS\" fear", QUARTERLY_REPORT),
    ]),
    "MELI": Profile("Growth company", "equity", [
        _na("gmv", "GMV and total payment volume growth", "pct", None, QUARTERLY_REPORT),
        _spec("operating_margin", "Operating margin", "pct", margin_with_trend(OPERATING_INCOME, "operatingMargins"), why="The current debate: margin vs growth"),
        REVENUE_GROWTH,
        _na("credit", "Credit portfolio growth and NPL ratios", "pct", None, QUARTERLY_REPORT),
        _na("take_rate", "Take rate and ads revenue", "pct", None, QUARTERLY_REPORT),
        _na("logistics", "Logistics and free-shipping unit economics", "text", None, QUARTERLY_REPORT),
    ]),
    "NU": Profile("Growth company", "equity", [
        _na("customers", "Customer growth and activation rate", "number", None, QUARTERLY_REPORT),
        _na("risk_adjusted_nim", "Risk-adjusted net interest margin", "pct", None, QUARTERLY_REPORT),
        _na("delinquency", "90+ day delinquencies", "pct", "Credit quality as it expands abroad", QUARTERLY_REPORT),
        _spec("efficiency_ratio", "Efficiency ratio", "pct", ratio_of_rows(OPERATING_EXPENSE, REVENUE), source=QUARTERLY_REPORT),
        ROE,
    ]),
    "TNIE.DE": Profile("Growth company", "equity", [
        REVENUE_GROWTH,
        _na("installed_base", "Installed base of Toniebox households", "number", None, QUARTERLY_REPORT),
        _na("attach_rate", "Content attach rate (figurines per box)", "number", None, QUARTERLY_REPORT),
        _spec("gross_margin", "Gross margin", "pct", info_pct("grossMargins")),
        _spec("ebitda_margin", "EBITDA margin", "pct", ebitda_margin, why="Adjusted EBITDA is in the company's results", source=QUARTERLY_REPORT),
        _spec("cash_conversion", "Cash conversion", "pct", cash_conversion),
        _spec("inventory", "Inventory", "amount", row_amount(INVENTORY), why="Working capital"),
        _spec("inventory_pct_revenue", "Inventory / revenue", "pct", ratio_of_rows(INVENTORY, REVENUE), why="Working capital"),
    ]),
    "SMH.MI": Profile("Thematic ETF", "etf", [
        _spec("top10", "Top-10 concentration", "pct", top_concentration(10), why="NVIDIA, TSMC, ASML"),
        _spec("top_holdings", "Largest holdings", "text", top_holdings_text()),
        _spec("holdings_pe", "P/E of the holdings", "multiple", holdings_pe),
        _na("revisions", "Earnings revisions", "pct", None, "Analyst consensus (e.g. LSEG, FactSet)"),
        _na("cycle", "Semiconductor cycle indicators", "text", "Inventories, book-to-bill, memory pricing", "SIA, SEMI and memory price trackers"),
        _spec("ter", "TER", "pct", expense_ratio),
        _spec("aum", "Fund size", "amount", info_number("totalAssets")),
    ]),
    "JEDI.PA": Profile("Thematic ETF", "etf", [
        _na("profitable", "Share of holdings that are profitable", "pct", None, "The fund's holdings list and each company's results"),
        _na("space_revenue", "Holdings' revenue actually tied to space", "pct", None, "VanEck factsheet"),
        _spec("top10", "Top-10 concentration", "pct", top_concentration(10)),
        _spec("top_holdings", "Largest holdings", "text", top_holdings_text()),
        _spec("aum", "Fund size", "amount", info_number("totalAssets")),
        _spec("liquidity", "Average daily volume", "number", info_number("averageVolume"), why="Liquidity"),
        _spec("holdings_pe", "P/E of the holdings", "multiple", holdings_pe),
        _spec("ter", "TER", "pct", expense_ratio),
    ]),
    "GRID.MI": Profile("Thematic ETF", "etf", [
        _na("backlogs", "Order backlogs and capex of the holdings", "text", None, "The holdings' quarterly results"),
        _spec("sector_mix", "Sector mix", "text", sector_mix(), why="Utilities vs equipment"),
        _spec("top_holdings", "Largest holdings", "text", top_holdings_text()),
        _spec("holdings_pe", "P/E of the holdings", "multiple", holdings_pe),
        _na("geography", "Geographic split", "text", None, "First Trust factsheet"),
        _spec("ter", "TER", "pct", expense_ratio),
    ]),
    "TDIV.AS": Profile("Thematic ETF", "etf", [
        _spec("yield", "Dividend yield", "pct", fund_yield),
        _na("dividend_growth", "Dividend growth and payout sustainability", "pct", None, "VanEck factsheet"),
        _spec("sector_mix", "Sector mix", "text", sector_mix(), why="Concentration"),
        _spec("holdings_pe", "P/E of the holdings", "multiple", holdings_pe, why="Valuation of the holdings"),
        _spec("top10", "Top-10 concentration", "pct", top_concentration(10)),
        _spec("ter", "TER", "pct", expense_ratio),
    ]),
    "4GLD.DE": Profile("Macro asset", "gold", [
        _na("real_yields", "Real yields", "pct", "Gold's main driver", FRED + " (DFII10)"),
        _spec("eurusd", "EUR/USD", "number", price_level("EURUSD=X"), why="You hold it in euros, gold prices in dollars"),
        _na("central_banks", "Central bank buying", "number", None, WGC),
        _na("etf_flows", "Physical gold ETF flows", "number", None, WGC),
        _spec("change_52w", "Price change over 52 weeks", "pct", info_number("fiftyTwoWeekChangePercent")),
    ], price_symbols=("EURUSD=X",)),
    "BTC-EUR": Profile("Macro asset", "crypto", [
        _na("etf_flows", "Spot ETF net flows", "amount", None, "Farside Investors"),
        _na("liquidity", "Global liquidity and the Fed path", "text", "Real yields", FRED),
        _na("mvrv", "Realized price / MVRV", "multiple", "Cycle valuation", "Glassnode or CoinMetrics"),
        _na("lth_supply", "Long-term holder supply and exchange reserves", "pct", None, "Glassnode or CryptoQuant"),
        _spec("nasdaq_corr", "Correlation with Nasdaq", "number", correlation_with("BTC-EUR", "^IXIC", "the Nasdaq Composite")),
        _spec("market_cap", "Market cap", "amount", info_number("marketCap")),
        _spec("change_52w", "Price change over 52 weeks", "pct", info_number("fiftyTwoWeekChangePercent")),
    ], price_symbols=("^IXIC",)),
    "ETH-EUR": Profile("Macro asset", "crypto", [
        _na("flows", "ETF and staking flows", "amount", None, "Farside Investors"),
        _na("fees", "Network fee revenue and net issuance", "amount", None, "ultrasound.money or Token Terminal"),
        _na("staked", "Share of ETH staked", "pct", None, "beaconcha.in"),
        _na("layer2", "Layer-2 activity", "number", None, "L2Beat"),
        _spec("eth_btc", "ETH/BTC ratio", "number", price_ratio("ETH-EUR", "BTC-EUR")),
        _spec("market_cap", "Market cap", "amount", info_number("marketCap")),
        _spec("change_52w", "Price change over 52 weeks", "pct", info_number("fiftyTwoWeekChangePercent")),
    ], price_symbols=("BTC-EUR",)),
}


def profile_for(yahoo_symbol: str | None) -> Profile | None:
    return PROFILES.get(yahoo_symbol or "")


def build_metrics(profile: Profile, inputs: MetricInputs) -> PositionMetrics:
    results: list[MetricResult] = []
    for spec in profile.specs:
        computed = spec.compute(inputs) if spec.compute else None
        results.append(
            MetricResult(
                key=spec.key,
                label=spec.label,
                unit=spec.unit,
                why=spec.why,
                value=computed.value if computed else None,
                text=computed.text if computed else None,
                detail=computed.detail if computed else None,
                history=computed.history if computed else [],
                # The hint only matters while the figure is missing -- or, for the few metrics
                # that carry a standing caveat, always.
                source_hint=spec.source_hint if (computed is None or (computed.value is None and computed.text is None)) else None,
            )
        )
    return PositionMetrics(lens=profile.lens, currency=inputs.currency, metrics=results)
