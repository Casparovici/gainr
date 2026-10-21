"""Plans next week's gym sessions (trainr_plan, docs/adr/0046): adds them to trainr's planner and
writes the Dutch report in briefr. Runs on Sunday at 12:00 from deploy/briefr-trainr.timer.
Running it again in the same week adds nothing twice.

Usage (from backend/):
    python -m scripts.briefr_trainr_plan                    # the week after today
    python -m scripts.briefr_trainr_plan --date 2026-10-25  # as if run on that day
"""

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.services import briefr_trainr_service  # noqa: E402

LOCAL = ZoneInfo("Europe/Amsterdam")


def main(argv: list[str] | None = None, now: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan next week's gym sessions into trainr and briefr.")
    parser.add_argument("--date", type=date.fromisoformat, help="run as if it were this day (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    today = args.date or now.astimezone(LOCAL).date()

    db = SessionLocal()
    try:
        plan, added, outcome = briefr_trainr_service.run(db, today, now.astimezone(timezone.utc).replace(tzinfo=None))
        db.commit()
    finally:
        db.close()
    days = ", ".join(f"{s.day.isoformat()} {s.kind.title}" for s in plan.sessions) or "none"
    print(f"trainr weekplan for the week of {plan.monday.isoformat()}: {days}; {added} added to the planner; report {outcome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
