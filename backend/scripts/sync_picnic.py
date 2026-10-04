"""Daily Picnic upkeep: processes new deliveries into gripr/Voorraad (when switched on, see
picnic_sync_service) and refreshes the price of every catalog item linked to a Picnic product.

Runs from the same daily timer as refresh_prices (deploy/gainr-refresh.service). Never fails the
unit over Picnic itself: without a connected session there's simply nothing to do until the
reader reconnects in the app, and a Picnic outage just means today's run is skipped -- the next
run (or opening Picnic-bestellingen) picks up whatever was missed.

Usage (from backend/):
    python -m scripts.sync_picnic
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.repositories import picnic_session_repo  # noqa: E402
from app.services import picnic_sync_service  # noqa: E402
from app.services.listr_picnic_service import PicnicNotConnected, listr_picnic_service  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        if picnic_session_repo.get(db) is None:
            print("Picnic: not connected, nothing to do.")
            return
        try:
            result = picnic_sync_service.sync(db)
            db.commit()
            print(
                f"Picnic deliveries: {result.deliveries} processed, {result.orders_booked} orders booked, "
                f"{result.orders_matched} already booked, {result.items_restocked} units restocked."
            )
            updated, not_found = listr_picnic_service.refresh_prices(db)
            db.commit()
            print(f"Picnic prices: {updated} updated" + (f", not found: {', '.join(not_found)}" if not_found else "."))
        except (PicnicNotConnected, picnic_sync_service.PicnicSyncNotConnected):
            db.commit()  # keeps the cleared session, so the app shows "connect" instead of failing
            print("Picnic: session expired -- reconnect in the app.")
        except Exception as exc:  # a Picnic outage or API change -- try again tomorrow
            db.rollback()
            print(f"Picnic: skipped ({type(exc).__name__}: {exc})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
