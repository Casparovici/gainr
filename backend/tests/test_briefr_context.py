import subprocess
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.asset import Asset
from app.models.portfolio import Portfolio
from app.models.transaction import Transaction, TransactionType
from app.repositories import portfolio_asset_target_repo
from app.schemas.fundamentals import NewsItemOut, NewsOut
from app.services import briefr_context_service, news_sources
from app.services.position_service import Valuation, position_service
from scripts import export_briefr_context

AS_OF = date(2026, 10, 19)
# Midday UTC, so the server's calendar day is the 19th in any time zone a test machine is in.
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def buy(db, portfolio_id, asset, total) -> None:
    db.add(Transaction(
        portfolio_id=portfolio_id, asset_id=asset.id if asset else None, date=date(2026, 1, 5),
        type=TransactionType.BUY if asset else TransactionType.DEPOSIT, quantity=Decimal(1) if asset else None,
        value_eur=Decimal(total), costs=Decimal(0), total_eur=Decimal(total), price=Decimal(total) if asset else None,
    ))
    db.flush()


@pytest.fixture()
def holdings(db_session, portfolio_id, monkeypatch):
    asml = Asset(ticker="ASML", name="ASML | Holding", yahoo_symbol="ASML.AS", native_currency="EUR")
    gold = Asset(
        ticker="4GLD", name="Xetra-Gold", asset_class="commodity", native_currency="EUR",
        news_sources='["ticker:GC=F"]',
    )
    db_session.add_all([asml, gold])
    db_session.flush()
    buy(db_session, portfolio_id, None, 1000)  # deposit
    buy(db_session, portfolio_id, asml, 600)
    buy(db_session, portfolio_id, gold, 200)
    portfolio_asset_target_repo.set_target(db_session, portfolio_id, asml.id, Decimal(50))
    db_session.add(Portfolio(name="Old", is_archived=True))
    db_session.flush()
    # Valued at cost, without asking Yahoo: ASML 600, gold 200, cash 200 of 1000.
    monkeypatch.setattr(
        position_service, "valuations",
        lambda db, positions: {p.asset_id: Valuation(p.cost_basis_eur, None, None, False) for p in positions},
    )
    return asml, gold


def test_the_holdings_file_has_tickers_names_and_weights_but_no_amounts(db_session, holdings):
    text = briefr_context_service.holdings_markdown(db_session, AS_OF)

    assert "As of 2026-10-19" in text
    assert "## Test Portfolio" in text
    assert "| ASML | ASML.AS | ASML / Holding | equity | 60.0 | 50.0 |" in text
    assert "| 4GLD |  | Xetra-Gold | commodity | 20.0 |  |" in text
    assert text.index("ASML") < text.index("4GLD")  # largest first
    assert "Cash: 20.0% of the portfolio." in text
    assert "600" not in text and "1000" not in text
    assert "Old" not in text  # archived portfolios are left out


def test_a_portfolio_without_holdings_says_so(db_session, portfolio_id, monkeypatch):
    text = briefr_context_service.holdings_markdown(db_session, AS_OF)
    assert "No open holdings" in text


def story(title, hours_ago, source=None, summary=""):
    return NewsItemOut(
        title=title, summary=summary, publisher="", url=f"https://example.com/{title.split()[0].lower()}",
        published_at=NOW - timedelta(hours=hours_ago),
        source=source,
    )


class FakeNews:
    """What each holding's News card would show, without asking Yahoo."""

    def __init__(self, by_ticker):
        self.by_ticker = by_ticker

    def get_news(self, db, asset):
        found = self.by_ticker[asset.ticker]
        if isinstance(found, Exception):
            raise found
        return NewsOut(window_days=7, items=found)


def test_the_news_file_has_each_holdings_recent_headlines_from_its_card_feeds(db_session, holdings):
    news = FakeNews({
        "ASML": [
            story("ASML cuts guidance", 5, summary="Second cut\nthis year. " + "x" * 400),
            story("ASML old story", 24 * 4),
        ],
        "4GLD": [story("Gold hits a record", 10, source=news_sources.label("ticker:GC=F"))],
    })

    text = briefr_context_service.news_markdown(db_session, NOW, news)

    assert "## ASML: ASML | Holding" in text
    assert "- 2026-10-19 07:00 UTC: ASML cuts guidance -- Second cut this year." in text
    assert "<https://example.com/asml>" in text
    assert "ASML old story" not in text  # older than the window
    assert "x" * 300 not in text and "…" in text  # long summaries are cut short
    assert f"Extra sources: {news_sources.label('ticker:GC=F')}" in text
    assert f"(via {news_sources.label('ticker:GC=F')}): Gold hits a record" in text
    assert "600" not in text and "Weight" not in text


def test_a_holding_without_recent_news_or_with_a_broken_feed_says_so(db_session, holdings):
    news = FakeNews({"ASML": [], "4GLD": RuntimeError("Yahoo is down")})

    text = briefr_context_service.news_markdown(db_session, NOW, news)

    assert "- No headlines in the last 3 days." in text
    assert "- Headlines unavailable tonight." in text


def _git(repo, *args):
    subprocess.run(["git", *export_briefr_context.IDENTITY, "-C", str(repo), *args], check=True, capture_output=True)


def test_the_export_script_writes_commits_and_pushes_only_a_change(db_session, holdings, tmp_path, monkeypatch, capsys):
    remote, repo = tmp_path / "remote.git", tmp_path / "checkout"
    subprocess.run(["git", "init", "--bare", "--quiet", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "clone", "--quiet", str(remote), str(repo)], check=True, capture_output=True)
    _git(repo, "commit", "--allow-empty", "--quiet", "-m", "start")
    _git(repo, "push", "--quiet", "-u", "origin", "main")
    monkeypatch.setattr(export_briefr_context, "SessionLocal", lambda: _Unclosed(db_session))
    monkeypatch.setattr(briefr_context_service, "fundamentals_service", FakeNews({"ASML": [], "4GLD": []}))

    assert export_briefr_context.main([str(repo), "--push"], now=NOW) == 0
    assert "pushed holdings, news and products as of 2026-10-19" in capsys.readouterr().out
    log = subprocess.run(["git", "-C", str(remote), "log", "--format=%s %an"], capture_output=True, text=True).stdout
    assert log.splitlines()[0] == "context: holdings, news and products as of 2026-10-19 homecloud"

    assert export_briefr_context.main([str(repo), "--push"], now=NOW) == 0
    assert "unchanged" in capsys.readouterr().out

    assert export_briefr_context.main([str(repo)], now=NOW) == 0
    assert (repo / "context/holdings.md").read_text().startswith("# Holdings")
    assert (repo / "context/news.md").read_text().startswith("# News")
    assert (repo / "context/listr-products.md").read_text().startswith("# listr products")
    assert export_briefr_context.main([str(tmp_path / "missing")]) == 2


class _Unclosed:
    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):
        pass
