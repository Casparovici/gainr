"""Refreshes the live quote of every held asset, and of the FX rates they're valued at, at most
once an hour (docs/adr/0047-hourly-live-quotes.md).

Runs hourly from deploy/gainr-quotes.timer. A page load only reads the quotes this stores and
never fetches one itself, so the request path makes no extra Yahoo calls. Running it more often
changes nothing: `price_service.refresh_quote` skips any asset whose quote is under an hour old.
A failing provider never fails the run; that asset simply keeps its previous quote, and once it
is two hours old the app values the holding at its daily close again.

Usage (from backend/):
    python -m scripts.refresh_quotes
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.services.position_service import held_assets  # noqa: E402
from app.services.price_service import price_service  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        assets = held_assets(db)
        refreshed = [asset.ticker for asset in assets if price_service.refresh_quote(db, asset)]
        for currency in sorted({asset.native_currency for asset in assets}):
            if price_service.refresh_fx_quote(db, currency):
                refreshed.append(f"FX:{currency}")
        db.commit()
        print(f"Refreshed {len(refreshed)} live quotes: {', '.join(refreshed) or 'none due'}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
