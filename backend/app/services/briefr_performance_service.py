"""briefr: daily, weekly and monthly performance reports on the gainr portfolios, written by the
server itself (docs/adr/0045). Unlike the cloud agents, this one needs no model and no
repository: the figures come from gainr's own ledger and prices (portfolio_period_service), the
amounts never leave the server, and the report goes straight into briefr's tables.

The periods, all from close to close, are run each morning after the price refresh:

- daily, Tuesday to Saturday: the last weekday against the one before (Monday's covers the
  weekend too, which matters for crypto);
- weekly, Saturday: Friday against the Friday before;
- monthly, on the 1st: the last day of the month against the last day of the month before.

Each portfolio gets its own report per period, so Main, Kids and the others can be read, marked
and archived on their own. Re-running a period replaces a report only when its content changed,
so a rerun leaves an already-read report read.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.briefr_report import BriefrAttention, BriefrVerdict
from app.repositories import portfolio_repo
from app.schemas.briefr import ReportFileItem
from app.services import briefr_report_service, portfolio_period_service
from app.services.briefr_report_service import ParsedReport
from app.services.portfolio_period import HoldingPeriod, PortfolioPeriod

AGENT = "portfolio-performance"
ZERO = Decimal(0)
DAILY, WEEKLY, MONTHLY = "daily", "weekly", "monthly"
# A price move this large (in %, either way) is a finding of its own, not just a line in the list.
MOVE_THRESHOLD = {DAILY: Decimal(5), WEEKLY: Decimal(10), MONTHLY: Decimal(15)}
# Drift from the target weight (in percentage points) worth flagging; weekly and monthly only, so
# the daily report doesn't repeat it every morning.
DRIFT_THRESHOLD = Decimal(5)
TOP = 3

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass(frozen=True)
class Period:
    kind: str
    start: date  # the close the period is measured from
    end: date  # the close it's measured to

    @property
    def label(self) -> str:
        if self.kind == DAILY:
            return f"{WEEKDAYS[self.end.weekday()]} {self.end.day} {MONTHS[self.end.month - 1][:3]}"
        if self.kind == WEEKLY:
            monday = self.end - timedelta(days=self.end.weekday())
            return f"Week {self.end.isocalendar().week} ({_day_month(monday)} – {_day_month(self.end)})"
        return f"{MONTHS[self.end.month - 1]} {self.end.year}"

    def source_path(self, portfolio_id: int) -> str:
        """One key per period and portfolio: by id, so renaming a portfolio updates its reports
        rather than starting new ones."""
        return f"server/{AGENT}/{self.kind}/{self.end.isoformat()}/portfolio-{portfolio_id}"


def _day_month(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1][:3]}"


def _previous_weekday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def daily_period(today: date) -> Period:
    end = _previous_weekday(today)
    return Period(DAILY, _previous_weekday(end), end)


def weekly_period(today: date) -> Period:
    end = today - timedelta(days=(today.weekday() - 4) % 7 or 7)  # the last Friday before today
    return Period(WEEKLY, end - timedelta(days=7), end)


def monthly_period(today: date) -> Period:
    end = today.replace(day=1) - timedelta(days=1)
    return Period(MONTHLY, end.replace(day=1) - timedelta(days=1), end)


def due_periods(today: date) -> list[Period]:
    """What the morning run on `today` reports on."""
    due = []
    if 1 <= today.weekday() <= 5:  # Tuesday to Saturday
        due.append(daily_period(today))
    if today.weekday() == 5:
        due.append(weekly_period(today))
    if today.day == 1:
        due.append(monthly_period(today))
    return due


# -- formatting --------------------------------------------------------------------------------


def _q(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _pct(value: Decimal | None, places: str = "0.01") -> str:
    if value is None:
        return "n/a"
    rounded = _q(value, places)
    return f"{'+' if rounded > 0 else ''}{rounded}%".replace("-", "−")


def _pp(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    rounded = _q(value, "0.01")
    return f"{'+' if rounded > 0 else ''}{rounded} pp".replace("-", "−")


def _eur(value: Decimal, signed: bool = False) -> str:
    rounded = _q(value, "1")
    text = f"€{abs(rounded):,.0f}"
    if rounded < 0:
        return f"−{text}"
    return f"+{text}" if signed and rounded > 0 else text


# -- the report --------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Section:
    portfolio_id: int
    name: str
    report: portfolio_period_service.PeriodReport

    @property
    def period(self) -> PortfolioPeriod:
        return self.report.period

    def ticker(self, holding: HoldingPeriod) -> str:
        asset = self.report.assets.get(holding.asset_id)
        return asset.ticker if asset else f"asset {holding.asset_id}"

    def name_of(self, holding: HoldingPeriod) -> str:
        asset = self.report.assets.get(holding.asset_id)
        return asset.name if asset else self.ticker(holding)

    @property
    def holdings(self) -> list[HoldingPeriod]:
        """The holdings still held at the period's end: the report is about active positions, so
        one sold out (or an old one paying a late dividend) is left out of the tables, findings and
        summary. The portfolio's own return and change still include it."""
        return [h for h in self.period.holdings if h.quantity_end != ZERO]


def _cell(text: str) -> str:
    """Text safe inside a Markdown table cell."""
    return " ".join(text.replace("|", "/").split())


def _holding_table(section: _Section, holdings: list[HoldingPeriod]) -> list[str]:
    """One row per holding: price change, contribution in euros and points, weight and target."""
    period, targets = section.period, section.report.targets
    lines = [
        "| Holding | Price | Contribution | Points | Weight | Target |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for h in holdings:
        price = _pct(h.price_change_pct) + (" (stale)" if h.price_end_stale else "")
        contribution = _eur(h.contribution_eur, signed=True)
        if h.dividends_eur:
            contribution += f" (incl. {_eur(h.dividends_eur)} div.)"
        weight = period.weight_end_pct(h)
        weight_text = f"{_q(weight, '0.1')}%" if weight is not None else "n/a"
        target = targets.get(h.asset_id)
        target_text = f"{_q(target, '0.1')}%" if target is not None else ""
        lines.append(
            f"| **{_cell(section.ticker(h))}** {_cell(section.name_of(h))} | {price} | {contribution} "
            f"| {_pp(period.contribution_pp(h))} | {weight_text} | {target_text} |"
        )
    return lines


def _section_body(section: _Section, kind: str) -> list[str]:
    period, report = section.period, section.report
    lines = []
    flows = period.deposits_eur - period.withdrawals_eur
    lines.append(
        f"**{_pct(report.twr_pct)}** time-weighted, {_eur(period.change_eur, signed=True)}. "
        f"Value {_eur(period.value_start_eur)} → {_eur(period.value_end_eur)}"
        + (f", with {_eur(flows, signed=True)} net deposits" if flows else "")
        + "."
    )
    extras = []
    if period.dividends_eur:
        extras.append(f"dividends {_eur(period.dividends_eur)}")
    if period.interest_eur:
        extras.append(f"interest {_eur(period.interest_eur)}")
    if period.fees_eur:
        extras.append(f"fees {_eur(period.fees_eur)}")
    if period.buys or period.sells:
        extras.append(f"{period.buys} buy{'s' if period.buys != 1 else ''}, {period.sells} sell{'s' if period.sells != 1 else ''}")
    if extras:
        lines.append("Also: " + ", ".join(extras) + ".")
    if report.best_day and report.worst_day:
        best, worst = report.best_day, report.worst_day
        lines.append(
            f"Best day {WEEKDAYS[best[0].weekday()]} {_day_month(best[0])} ({_pct(best[1])}), "
            f"worst {WEEKDAYS[worst[0].weekday()]} {_day_month(worst[0])} ({_pct(worst[1])})."
        )

    # The holdings table, by contribution with what cost the most at the top. The daily
    # report keeps it to the few that moved the day: the three biggest drags and the three
    # biggest contributors; the weekly and monthly ones list every holding.
    ranked = sorted(section.holdings, key=lambda h: h.contribution_eur)
    if kind == DAILY:
        drags = [h for h in ranked if h.contribution_eur < 0][:TOP]
        lifts = [h for h in reversed(ranked) if h.contribution_eur > 0][:TOP]
        shown, heading = drags + lifts[::-1], "### Biggest movers"
    else:
        shown, heading = ranked, "### Holdings, by contribution"
    if shown:
        lines += ["", heading, *_holding_table(section, shown)]
    if kind != DAILY:
        untargeted = [section.ticker(h) for h in ranked if h.asset_id not in report.targets]
        if untargeted:
            lines += ["", f"No target weight set: {', '.join(untargeted)}."]
    return lines


def _findings(section: _Section, kind: str) -> list[ReportFileItem]:
    period, report = section.period, section.report
    findings = []
    ordered = sorted(section.holdings, key=lambda h: abs(h.price_change_pct or ZERO), reverse=True)
    for holding in ordered:
        move = holding.price_change_pct
        if move is not None and abs(move) >= MOVE_THRESHOLD[kind]:
            findings.append(ReportFileItem(
                symbol=section.ticker(holding), verdict=BriefrVerdict.WATCH,
                headline=f"{section.ticker(holding)} {_pct(move, '0.1')}",
                detail=f"Contributed {_eur(holding.contribution_eur, signed=True)} "
                       f"({_pp(period.contribution_pp(holding))}) to {section.name}.",
            ))
    for holding in section.holdings:
        if holding.price_end_stale:
            findings.append(ReportFileItem(
                symbol=section.ticker(holding), verdict=BriefrVerdict.WATCH,
                headline=f"{section.ticker(holding)}: no current price",
                detail="Valued at its last transaction price; check its Yahoo symbol.",
            ))
    if kind != DAILY:
        for holding in section.holdings:
            target, weight = report.targets.get(holding.asset_id), period.weight_end_pct(holding)
            if target is None or weight is None:
                continue
            drift = weight - target
            if abs(drift) >= DRIFT_THRESHOLD:
                findings.append(ReportFileItem(
                    symbol=section.ticker(holding), verdict=BriefrVerdict.WATCH,
                    headline=f"{section.ticker(holding)} {_pp(drift)} from its target",
                    detail=f"{_q(weight, '0.1')}% of {section.name} against a {_q(target, '0.1')}% target.",
                ))
    return findings


@dataclass(frozen=True)
class PortfolioReport:
    portfolio: str
    source_path: str  # the key it's saved under
    report: ParsedReport


def build_reports(db: Session, period: Period, now: datetime) -> list[PortfolioReport]:
    """One report for `period` per portfolio that isn't archived and had money in it, largest
    portfolio first. Empty when none did."""
    sections = []
    for portfolio in portfolio_repo.list_portfolios(db):
        report = portfolio_period_service.period_report(db, portfolio.id, period.start, period.end)
        if report.period.value_start_eur > ZERO or report.period.value_end_eur > ZERO:
            sections.append(_Section(portfolio.id, portfolio.name, report))
    if not sections:
        return []
    sections.sort(key=lambda s: s.period.value_end_eur, reverse=True)
    benchmarks = portfolio_period_service.benchmark_returns(db, period.start, period.end)
    return [
        PortfolioReport(s.name, period.source_path(s.portfolio_id), _build_report(s, period, benchmarks, now))
        for s in sections
    ]


def _build_report(section: _Section, period: Period, benchmarks: dict[str, Decimal], now: datetime) -> ParsedReport:
    ranked = sorted(section.holdings, key=lambda h: h.contribution_eur)
    summary = f"{section.name} {_pct(section.report.twr_pct)} ({_eur(section.period.change_eur, signed=True)})"
    world = next((value for label, value in benchmarks.items() if "MSCI World" in label), None)
    if world is not None:
        summary += f", MSCI World {_pct(world)}"
    if ranked and ranked[-1].contribution_eur > 0:
        summary += f". Top contributor {section.ticker(ranked[-1])} {_pp(section.period.contribution_pp(ranked[-1]))}"
    if ranked and ranked[0].contribution_eur < 0:
        summary += f", biggest drag {section.ticker(ranked[0])} {_pp(section.period.contribution_pp(ranked[0]))}"
    summary += "."

    title = f"{period.label} · {section.name}: {_pct(section.report.twr_pct)}"
    body = [
        f"{section.name}, from the close of {_day_month(period.start)} {period.start.year} to the close of "
        f"{_day_month(period.end)} {period.end.year}. Returns are time-weighted, so deposits and "
        "withdrawals don't count as performance; a contribution is what a holding earned in euros "
        "(price, currency and dividends), and in points of the start value.",
    ]
    if benchmarks:
        body += ["", "Benchmarks, in their own currency: "
                 + ", ".join(f"{label} {_pct(value)}" for label, value in benchmarks.items()) + "."]
    body += ["", *_section_body(section, period.kind)]

    findings = _findings(section, period.kind)
    return ParsedReport(
        agent=AGENT,
        run_at=now,
        title=title[:200],
        summary=summary[:1000],
        attention=BriefrAttention.WATCH if findings else BriefrAttention.INFO,
        body="\n".join(body),
        items=findings,
    )


def run(db: Session, today: date, now: datetime, periods: list[Period] | None = None) -> list[tuple[Period, str, str]]:
    """Writes each portfolio's report for each period due `today` (or the ones given), and says
    per period and portfolio whether it was created, updated or unchanged; a period with no
    portfolio to report on is one "skipped" row without a portfolio."""
    outcomes = []
    for period in periods if periods is not None else due_periods(today):
        reports = build_reports(db, period, now)
        if not reports:
            outcomes.append((period, "", "skipped"))
        for built in reports:
            outcome = briefr_report_service.save_generated_report(db, built.source_path, built.report)
            outcomes.append((period, built.portfolio, outcome))
    return outcomes
