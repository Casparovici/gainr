"""Writes briefr's performance reports on the gainr portfolios -- daily, weekly and monthly, as
they fall due -- straight into briefr (briefr_performance_service, docs/adr/0045).

Runs every morning from deploy/briefr-performance.timer, after the price refresh: one report per
portfolio per period. Re-running is safe: a report is only replaced when its content changed.

Usage (from backend/):
    python -m scripts.briefr_performance                     # whatever is due today
    python -m scripts.briefr_performance --period weekly     # that period as of today
    python -m scripts.briefr_performance --date 2026-10-17   # as if run on that day
"""

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.services import briefr_performance_service as perf  # noqa: E402

# The periods follow the owner's calendar, whatever time zone the server runs in.
LOCAL = ZoneInfo("Europe/Amsterdam")
BUILDERS = {perf.DAILY: perf.daily_period, perf.WEEKLY: perf.weekly_period, perf.MONTHLY: perf.monthly_period}


def main(argv: list[str] | None = None, now: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write briefr's portfolio performance reports.")
    parser.add_argument("--date", type=date.fromisoformat, help="run as if it were this day (YYYY-MM-DD)")
    parser.add_argument("--period", choices=sorted(BUILDERS), help="this period only, even if it isn't due")
    args = parser.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    today = args.date or now.astimezone(LOCAL).date()
    periods = [BUILDERS[args.period](today)] if args.period else None

    db = SessionLocal()
    try:
        outcomes = perf.run(db, today, now.astimezone(timezone.utc).replace(tzinfo=None), periods)
        db.commit()
    finally:
        db.close()
    if not outcomes:
        print(f"briefr performance: nothing due on {today.isoformat()}")
    for period, portfolio, outcome in outcomes:
        which = f" {portfolio}" if portfolio else ""
        print(f"briefr performance: {period.kind} {period.start.isoformat()} → {period.end.isoformat()}{which}: {outcome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
