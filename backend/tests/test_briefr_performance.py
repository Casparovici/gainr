from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.asset import Asset
from app.models.portfolio import Portfolio
from app.models.transaction import Transaction, TransactionType
from app.repositories import briefr_report_repo, portfolio_asset_target_repo, price_repo
from app.services import briefr_performance_service as perf
from app.services import portfolio_period_service
from scripts import briefr_performance

TT = TransactionType
D = Decimal
SATURDAY = date(2026, 10, 17)
NOW = datetime(2026, 10, 17, 5, 0)


def test_what_is_due_each_morning():
    assert perf.due_periods(date(2026, 10, 19)) == []  # Monday: the weekend had no close of its own
    assert perf.due_periods(date(2026, 10, 20)) == [perf.Period(perf.DAILY, date(2026, 10, 16), date(2026, 10, 19))]
    assert perf.due_periods(SATURDAY) == [
        perf.Period(perf.DAILY, date(2026, 10, 15), date(2026, 10, 16)),
        perf.Period(perf.WEEKLY, date(2026, 10, 9), date(2026, 10, 16)),
    ]
    assert perf.due_periods(date(2026, 10, 18)) == []  # Sunday
    assert perf.due_periods(date(2026, 11, 1)) == [perf.Period(perf.MONTHLY, date(2026, 9, 30), date(2026, 10, 31))]
    assert perf.weekly_period(date(2026, 10, 16)) == perf.Period(perf.WEEKLY, date(2026, 10, 2), date(2026, 10, 9))


def test_periods_have_readable_labels_and_one_key_each():
    assert perf.daily_period(SATURDAY).label == "Fri 16 Oct"
    assert perf.weekly_period(SATURDAY).label == "Week 42 (12 Oct – 16 Oct)"
    assert perf.monthly_period(date(2026, 10, 1)).label == "September 2026"
    assert perf.weekly_period(SATURDAY).source_path(3) == "server/portfolio-performance/weekly/2026-10-16/portfolio-3"


def add(db, *rows):
    db.add_all(rows)
    db.flush()
    return rows


def txn(portfolio, day, type_, total, asset=None, qty=None, price=None):
    return Transaction(portfolio_id=portfolio.id, date=day, type=type_, asset_id=asset.id if asset else None,
                       quantity=qty, price=price, value_eur=D(total), costs=D(0), total_eur=D(total))


@pytest.fixture()
def ledger(db_session, monkeypatch):
    main, kids, old = add(db_session, Portfolio(name="Main"), Portfolio(name="Kids"),
                          Portfolio(name="Old", is_archived=True))
    acme, move, stale = add(
        db_session,
        Asset(ticker="ACME", name="Acme NV", native_currency="EUR"),
        Asset(ticker="MOVE", name="Mover Inc", native_currency="EUR"),
        Asset(ticker="STALE", name="Unpriced", native_currency="EUR"),
    )
    day1 = date(2026, 10, 1)
    add(
        db_session,
        txn(main, day1, TT.DEPOSIT, 10000),
        txn(main, day1, TT.BUY, 1000, acme, D(100), D(10)),
        txn(main, day1, TT.BUY, 1000, move, D(10), D(100)),
        txn(main, day1, TT.BUY, 100, stale, D(5), D(20)),
        txn(kids, day1, TT.DEPOSIT, 500),
        txn(old, day1, TT.DEPOSIT, 999),
    )
    price_repo.upsert_prices(db_session, acme.id, {day1: D(10), date(2026, 10, 9): D(10), date(2026, 10, 15): D(11),
                                                   date(2026, 10, 16): D(12)})
    price_repo.upsert_prices(db_session, move.id, {day1: D(100), date(2026, 10, 9): D(100),
                                                   date(2026, 10, 15): D(118), date(2026, 10, 16): D(115)})
    portfolio_asset_target_repo.set_target(db_session, main.id, acme.id, D(5))
    db_session.flush()
    closes = [(date(2026, 10, 9), D(100)), (date(2026, 10, 15), D(101)), (date(2026, 10, 16), D(102))]
    monkeypatch.setattr(portfolio_period_service.benchmark_service, "get_series", lambda db, key, s, e: closes)
    return main, kids


def _report(db, kind, portfolio):
    return briefr_report_repo.get_by_source_path(
        db, f"server/portfolio-performance/{kind}/2026-10-16/portfolio-{portfolio.id}"
    )


def test_each_portfolio_gets_its_own_report_per_period(db_session, ledger):
    main, kids = ledger
    outcomes = perf.run(db_session, SATURDAY, NOW)

    # Largest portfolio first; the archived one gets none.
    assert [(p.kind, name, o) for p, name, o in outcomes] == [
        ("daily", "Main", "created"), ("daily", "Kids", "created"),
        ("weekly", "Main", "created"), ("weekly", "Kids", "created"),
    ]
    kids_weekly = _report(db_session, "weekly", kids)
    assert kids_weekly.title == "Week 42 (12 Oct – 16 Oct) · Kids: 0.00%"
    assert kids_weekly.summary == "Kids 0.00% (€0), MSCI World +2.00%."
    assert kids_weekly.attention.value == "info"
    assert kids_weekly.items == []
    assert "ACME" not in kids_weekly.body and "Main" not in kids_weekly.body
    assert kids_weekly.body.startswith("Kids, from the close of 9 Oct 2026")


def test_the_weekly_report_has_returns_contributions_benchmarks_and_findings(db_session, ledger):
    main, kids = ledger
    perf.run(db_session, SATURDAY, NOW)

    weekly = _report(db_session, "weekly", main)
    # Main: 10000 at Friday 9's close (cash 7900, ACME 1000, MOVE 1000, STALE 100) to 10350.
    assert weekly.title == "Week 42 (12 Oct – 16 Oct) · Main: +3.50%"
    assert weekly.summary == "Main +3.50% (+€350), MSCI World +2.00%. Top contributor ACME +2.00 pp."
    assert weekly.attention.value == "watch"
    assert weekly.agent == "portfolio-performance"
    assert [(i.symbol, i.headline) for i in weekly.items] == [
        ("ACME", "ACME +20.0%"),  # the biggest move first
        ("MOVE", "MOVE +15.0%"),
        ("STALE", "STALE: no current price"),
        ("ACME", "ACME +6.59 pp from its target"),
    ]
    assert all(i.asset_id is not None for i in weekly.items)  # each links to its position
    body = weekly.body
    assert "Benchmarks, in their own currency: S&P 500 +2.00%" in body
    assert "**+3.50%** time-weighted, +€350. Value €10,000 → €10,350." in body
    assert "### Holdings, by contribution\n| Holding | Price | Contribution | Points | Weight | Target |\n|---|---:|" in body
    assert "| **ACME** Acme NV | +20.00% | +€200 | +2.00 pp | 11.6% | 5.0% |" in body
    assert "| **STALE** Unpriced | 0.00% (stale) | €0 | 0.00 pp | 1.0% |  |" in body
    # Every holding once, what cost the most first: STALE (€0), MOVE (+€150), ACME (+€200).
    assert body.index("**STALE**") < body.index("**MOVE**") < body.index("**ACME**")
    assert body.count("| **ACME**") == 1
    assert "No target weight set: STALE, MOVE." in body
    assert "Kids" not in body and "Old" not in body


def test_the_daily_report_leaves_drift_and_the_full_list_to_the_week(db_session, ledger):
    main, _kids = ledger
    perf.run(db_session, SATURDAY, NOW)
    daily = _report(db_session, "daily", main)

    assert daily.title.startswith("Fri 16 Oct · Main: ")
    # ACME's +9.1% clears the daily bar of 5%; MOVE's −2.5% doesn't.
    assert [i.headline for i in daily.items] == ["ACME +9.1%", "STALE: no current price"]
    assert "### Biggest movers" in daily.body
    assert "| **MOVE** Mover Inc | −2.54% | −€30 | −0.29 pp | 11.1% |  |" in daily.body
    assert daily.body.index("**MOVE**") < daily.body.index("**ACME**")  # the drag first
    assert "| **STALE**" not in daily.body  # €0 is neither a drag nor a lift


def test_only_positions_still_held_are_reported_on(db_session, ledger):
    main, _kids = ledger
    gone, old = add(db_session, Asset(ticker="GONE", name="Sold Out", native_currency="EUR"),
                    Asset(ticker="OLD", name="Long Gone", native_currency="EUR"))
    add(
        db_session,
        txn(main, date(2026, 10, 1), TT.BUY, 1000, gone, D(10), D(100)),
        txn(main, date(2026, 10, 14), TT.SELL, 1500, gone, D(10), D(150)),  # sold out mid-week, +50%
        txn(main, date(2026, 10, 1), TT.BUY, 100, old, D(10), D(10)),
        txn(main, date(2026, 10, 2), TT.SELL, 100, old, D(10), D(10)),
        txn(main, date(2026, 10, 14), TT.DIVIDEND, 20, old),  # a late dividend on a closed position
    )
    price_repo.upsert_prices(db_session, gone.id, {date(2026, 10, 9): D(100), date(2026, 10, 15): D(150),
                                                   date(2026, 10, 16): D(150)})
    db_session.flush()

    perf.run(db_session, SATURDAY, NOW)
    weekly = _report(db_session, "weekly", main)

    assert {i.symbol for i in weekly.items} == {"ACME", "MOVE", "STALE"}
    assert "GONE" not in weekly.body and "OLD" not in weekly.body and "sold out" not in weekly.body
    assert "GONE" not in weekly.summary and "OLD" not in weekly.summary
    # The portfolio's own figures still count what they earned.
    assert "1 sell" in weekly.body and "dividends €20" in weekly.body


def test_running_again_changes_nothing_and_keeps_a_report_read(db_session, ledger):
    main, _kids = ledger
    perf.run(db_session, SATURDAY, NOW)
    weekly = _report(db_session, "weekly", main)
    weekly.read_at = datetime(2026, 10, 17, 8)

    again = perf.run(db_session, SATURDAY, datetime(2026, 10, 17, 9))

    assert [o for _, _, o in again] == ["unchanged"] * 4
    assert _report(db_session, "weekly", main).read_at == datetime(2026, 10, 17, 8)


def test_renaming_a_portfolio_updates_its_report_rather_than_adding_one(db_session, ledger):
    main, _kids = ledger
    perf.run(db_session, SATURDAY, NOW, [perf.weekly_period(SATURDAY)])
    main.name = "Long term"
    db_session.flush()

    again = perf.run(db_session, SATURDAY, NOW, [perf.weekly_period(SATURDAY)])

    assert [(name, o) for _, name, o in again] == [("Long term", "updated"), ("Kids", "unchanged")]
    assert _report(db_session, "weekly", main).title.endswith("· Long term: +3.50%")


def test_nothing_to_report_without_money_in_a_portfolio(db_session):
    outcomes = perf.run(db_session, SATURDAY, NOW, [perf.weekly_period(SATURDAY)])
    assert [(name, o) for _, name, o in outcomes] == [("", "skipped")]


def test_the_script_runs_what_is_due_or_the_period_asked_for(db_session, ledger, monkeypatch, capsys):
    class Unclosed:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            pass

    monkeypatch.setattr(briefr_performance, "SessionLocal", Unclosed)
    assert briefr_performance.main(["--date", "2026-10-18"], now=NOW) == 0
    assert "nothing due on 2026-10-18" in capsys.readouterr().out

    assert briefr_performance.main(["--date", "2026-10-17", "--period", "weekly"], now=NOW) == 0
    out = capsys.readouterr().out
    assert "weekly 2026-10-09 → 2026-10-16 Main: created" in out
    assert "weekly 2026-10-09 → 2026-10-16 Kids: created" in out
