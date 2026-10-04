"""Updates each asset's De Lange Termijn (DLT) rating from a hand-maintained mapping below.

DLT has no API or export — this is refreshed by pasting a screenshot of the dashboard's
Favorieten page into chat, reading the "Oordeel" column off it, and updating RATINGS here.
Only lists tickers DLT actually covers; anything else keeps showing as "Neutral" in the app
(the positions endpoint treats "no rating" and "explicitly neutral" the same on the wire).

Usage (from backend/):
    python -m scripts.update_dlt_ratings
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models.asset import DltJudgment  # noqa: E402
from app.repositories import asset_repo  # noqa: E402

# ticker -> DLT's "Oordeel" as of the screenshot date below.
# Source: dashboard.delangetermijn.nl/favorieten, 2026-09-12.
RATINGS: dict[str, DltJudgment] = {
    "MELI": DltJudgment.ATTRACTIVE,
    "NOW": DltJudgment.ATTRACTIVE,
    "NASDAQ:GOOGL": DltJudgment.NEUTRAL,
    "AMZN": DltJudgment.NEUTRAL,
    "NU": DltJudgment.NEUTRAL,
    "AMS:TDIV": DltJudgment.NEUTRAL,
    "EPA:JEDI": DltJudgment.NEUTRAL,
    "GRIDINAV": DltJudgment.NEUTRAL,
    "SMH": DltJudgment.CRITICAL,
}


def main() -> None:
    db = SessionLocal()
    try:
        updated, missing = [], []
        for ticker, judgment in RATINGS.items():
            asset = asset_repo.get_by_ticker(db, ticker)
            if asset is None:
                missing.append(ticker)
                continue
            asset.dlt_judgment = judgment
            updated.append(f"{ticker} -> {judgment.value}")
        db.commit()

        print(f"Updated {len(updated)} asset(s):")
        for line in updated:
            print(f"  {line}")
        if missing:
            print(f"\nNo matching asset for {len(missing)} ticker(s) (typo, or not held): {missing}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
