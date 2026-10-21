"""Refreshes daily prices for every held asset plus the three benchmarks, once.

Meant to run on a schedule (see deploy/gainr-refresh.timer) well before anyone's likely to
open the app, so a page load never has to make a synchronous Yahoo Finance call itself —
`price_service`/`benchmark_service` gate their own fetch to once per calendar day per asset,
so this just makes sure that one fetch already happened by the time a request comes in. The
request path keeps its on-miss fallback, so a missed or late run still self-heals, just with
the first request of the day paying the cost this script is meant to avoid.

Usage (from backend/):
    python -m scripts.refresh_prices
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.services import gripr_portfolio_link_service  # noqa: E402
from app.services.benchmark_service import BENCHMARKS, benchmark_service  # noqa: E402
from app.services.position_service import held_assets  # noqa: E402
from app.services.price_service import price_service  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        # Every portfolio's held assets, unioned -- prices/the price cache are shared across
        # portfolios (see docs/adr/0019), so this refreshes once per asset regardless of how
        # many portfolios hold it, not once per portfolio.
        refreshed = []
        for asset in held_assets(db):
            price_service.get_daily_price(db, asset)
            refreshed.append(asset.ticker)

        window_start = date.today() - timedelta(days=7)
        for key in BENCHMARKS:
            benchmark_service.get_series(db, key, window_start, date.today())
            refreshed.append(f"benchmark:{key}")

        # Right after the prices it depends on, so every linked gripr account's mirrored balance
        # is written from today's valuation rather than yesterday's. A no-op when nothing's linked.
        balances = gripr_portfolio_link_service.sync_balance(db)

        db.commit()
        print(f"Refreshed {len(refreshed)} price series: {', '.join(refreshed)}")
        for account_id, balance in balances.items():
            print(f"Synced gripr account {account_id} balance to portfolio value: {balance}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
