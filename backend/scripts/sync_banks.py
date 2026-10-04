"""Daily bank sync: books new transactions from every switched-on bank (ING, Trade Republic) into
gripr -- see bank_sync_service.

Runs from the same daily timer as refresh_prices (deploy/gainr-refresh.service). Never fails the
unit over a bank: one without a live consent is reported and skipped until the reader reconnects
in the app, and an outage just means today's run misses it -- the next run (or "Sync now") re-reads
the days it missed. The other banks sync regardless.

Usage (from backend/):
    python -m scripts.sync_banks
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.services import bank_sync_service  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        try:
            result = bank_sync_service.sync(db, scheduled=True)
            db.commit()
        except Exception as exc:  # an API change or a bug -- logged, retried tomorrow
            db.rollback()
            print(f"Banks: skipped ({type(exc).__name__}: {exc})")
            return
        print(
            f"Banks: {result.booked} booked, {result.fulfilled} filed under a recurring rule, "
            f"{result.matched} already in gripr, {result.counterparts} transfer halves skipped."
        )
        for bank, problem in result.problems.items():
            print(f"  {bank}: {problem}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
