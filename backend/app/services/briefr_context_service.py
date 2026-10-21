"""briefr: the context agents work from, written by the server into the agents repository before
they run (docs/adr/0044-briefr-agent-reports.md). Agents run in the cloud and can't reach the app,
so what they need to know about the portfolio is committed for them -- and only that: tickers,
names and weights, never an amount, a quantity or a cash balance. Next to that, the headlines the
app's News card shows per holding (its own Yahoo feed plus the extra sources set on it, ADR 0026
and 0030): the server can read Yahoo's feed, a cloud agent can't. And for the home chef, listr's
product catalog, so the ingredients it writes land on products (ADR 0054)."""

from datetime import date as date_, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.repositories import asset_repo, listr_item_repo, portfolio_repo
from app.services import news_sources
from app.services.fundamentals_service import FundamentalsService, fundamentals_service
from app.services.position_service import CASH_ASSET_ID, position_service

HOLDINGS_PATH = "context/holdings.md"
NEWS_PATH = "context/news.md"
PRODUCTS_PATH = "context/listr-products.md"
# Long enough to cover a weekend for a Monday-morning run, short enough to stay a night's reading.
NEWS_WINDOW = timedelta(days=3)
MAX_HEADLINES = 12
MAX_SUMMARY_CHARS = 300


def _pct(value: Decimal | None) -> str:
    return "" if value is None else str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ").strip()


def holdings_markdown(db: Session, as_of: date_) -> str:
    """Every open holding of every portfolio that isn't archived, largest first, as a Markdown
    table per portfolio: ticker, Yahoo symbol, name, class, weight and target weight (in % of the
    portfolio, cash included). Cash is one line with its weight only."""
    lines = [
        "# Holdings",
        "",
        f"As of {as_of.isoformat()}, exported by homecloud. Weights are % of each portfolio's value,",
        "cash included; a target is the weight the owner aims for (blank when none is set).",
        "Use the Ticker column as `symbol` in a report's findings.",
    ]
    for portfolio in portfolio_repo.list_portfolios(db):
        rows = position_service.list_position_rows(db, portfolio.id)
        holdings = [r for r in rows if r.asset_id != CASH_ASSET_ID]
        assets = asset_repo.get_assets_by_ids(db, [r.asset_id for r in holdings])
        lines += [
            "",
            f"## {_cell(portfolio.name)}",
            "",
            "| Ticker | Yahoo | Name | Class | Weight % | Target % |",
            "|---|---|---|---|---:|---:|",
        ]
        for row in holdings:
            yahoo = assets[row.asset_id].yahoo_symbol if row.asset_id in assets else None
            lines.append(
                f"| {_cell(row.ticker)} | {_cell(yahoo or '')} | {_cell(row.name)} | {_cell(row.asset_class)} "
                f"| {_pct(row.weight_pct)} | {_pct(row.target_weight_pct)} |"
            )
        if not holdings:
            lines.append("| | | No open holdings | | | |")
        cash = next((r for r in rows if r.asset_id == CASH_ASSET_ID), None)
        if cash is not None and cash.weight_pct is not None:
            lines += ["", f"Cash: {_pct(cash.weight_pct)}% of the portfolio."]
    return "\n".join(lines) + "\n"


def _line(text: str, limit: int | None = None) -> str:
    text = " ".join(text.split())
    return text if limit is None or len(text) <= limit else text[: limit - 1].rstrip() + "…"


def news_markdown(db: Session, now: datetime, news: FundamentalsService | None = None) -> str:
    """Per open holding (once, whichever portfolios hold it), the headlines of the last few days
    from the same feeds as its News card in the app: its own, then the extra sources set on it,
    newest first. A holding whose feeds can't be read tonight says so rather than failing the
    export, so the holdings file still goes out."""
    news = news or fundamentals_service
    cutoff = now - NEWS_WINDOW
    asset_ids: list[int] = []
    for portfolio in portfolio_repo.list_portfolios(db):
        active, _closed = position_service.get_positions(db, portfolio.id)
        asset_ids += [p.asset_id for p in active if p.asset_id not in asset_ids]
    assets = asset_repo.get_assets_by_ids(db, asset_ids)

    lines = [
        "# News",
        "",
        f"Exported by homecloud at {now.strftime('%Y-%m-%d %H:%M')} UTC: per holding, the headlines of",
        f"the last {NEWS_WINDOW.days} days from the Yahoo feeds the app's News card reads -- the holding's own,",
        "plus the extra sources set on it (marked \"via\"). A starting point, not the whole story: search",
        "beyond it, and prefer primary sources.",
    ]
    for asset_id in asset_ids:
        asset = assets.get(asset_id)
        if asset is None:
            continue
        lines += ["", f"## {_line(asset.ticker)}: {_line(asset.name)}", ""]
        sources = news_sources.parse_stored(asset.news_sources)
        if sources:
            lines += [f"Extra sources: {', '.join(news_sources.label(s) for s in sources)}", ""]
        try:
            items = news.get_news(db, asset).items
        except Exception:  # a feed problem tonight shouldn't cost the agents their holdings file
            lines.append("- Headlines unavailable tonight.")
            continue
        recent = [i for i in items if i.published_at.astimezone(timezone.utc) >= cutoff][:MAX_HEADLINES]
        if not recent:
            lines.append(f"- No headlines in the last {NEWS_WINDOW.days} days.")
        for item in recent:
            when = item.published_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
            via = f" (via {_line(item.source)})" if item.source else ""
            summary = f" -- {_line(item.summary, MAX_SUMMARY_CHARS)}" if item.summary.strip() else ""
            lines.append(f"- {when} UTC{via}: {_line(item.title)}{summary} <{item.url}>")
    return "\n".join(lines) + "\n"


def products_markdown(db: Session) -> str:
    """listr's product catalog (what isn't archived), per category in the shop's order: a name and
    its default unit, which is what a recipe's ingredient needs to land on a product. Grocery
    names only, nothing about what's in stock or bought."""
    by_category: dict[tuple[int, str], list[tuple[str, str]]] = {}
    for item in listr_item_repo.list_items(db):
        key = (item.category.sort_order, item.category.name)
        by_category.setdefault(key, []).append((item.name, item.default_unit))
    lines = [
        "# listr products",
        "",
        "Exported by homecloud: the product catalog of the household's shopping lists. Name a recipe's",
        "ingredient exactly as a product here when one fits (\"Tomaten\", not \"rijpe tomaten\"), with the",
        "unit next to it when the recipe's amount is in that unit. An ingredient that matches no product",
        "is kept in the recipe's notes, to add by hand.",
    ]
    for (_, category), items in sorted(by_category.items()):
        lines += ["", f"## {_line(category)}", ""]
        lines += [f"- {_line(name)} ({_line(unit)})" for name, unit in items]
    return "\n".join(lines) + "\n"
