"""Daily broker sync: books Trading 212's new fills, dividends and last week's interest/cashback into
the gainr portfolio it's set to -- see broker_sync_service and docs/adr/0031-trading212-sync.md.

Runs from the same daily timer as refresh_prices and sync_banks (deploy/gainr-refresh.service).
Never fails the unit: switched off or not configured means nothing to do, and an outage or a
refused key is recorded on the connection (shown on the Transactions page) and retried tomorrow.

Usage (from backend/):
    python -m scripts.sync_brokers
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.services import broker_sync_service  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        try:
            result = broker_sync_service.sync(db)
            db.commit()
        except Exception as exc:  # an API change or a bug -- logged, retried tomorrow
            db.rollback()
            print(f"Trading 212: skipped ({type(exc).__name__}: {exc})")
            return
        print(
            f"Trading 212: {result.booked} booked, {result.matched} already in gainr, "
            f"{result.deposits} weekly interest/cashback deposits."
        )
        for item in result.unmapped:
            print(f"  waiting for an asset with ISIN {item['isin']} ({item['name']}): {item['records']} records")
        for problem in result.problems:
            print(f"  {problem}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
