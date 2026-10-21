"""Import rides and runs from a Strava account export into trainr.

Usage (from backend/):
    python -m scripts.import_strava ~/Downloads/export_12345678.zip
    python -m scripts.import_strava path/to/activities.csv --dry-run

Takes the archive Strava emails after "Download or delete your account" -> "Request your
archive" (the .zip, or activities.csv taken out of it). Rides become Fietsen, runs Hardlopen, each
a done workout with distance, moving time, top speed and the activity's name as its note; other
activity types are skipped and listed. Idempotent: each workout remembers its Strava activity id,
so re-running with a newer export only adds what's new. See docs/adr/0037 (addendum).
"""

import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models.trainr_workout import TrainrActivityType  # noqa: E402
from app.services.trainr_strava_import import (  # noqa: E402
    StravaExportError,
    import_activities,
    parse_activities_csv,
)

LABELS = {TrainrActivityType.CYCLING: ("ride", "rides"), TrainrActivityType.RUNNING: ("run", "runs"), TrainrActivityType.HOME_GYM: ("gym session", "gym sessions")}


def read_csv(path: Path) -> str:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.rsplit("/", 1)[-1] == "activities.csv"]
            if not names:
                raise StravaExportError(f"No activities.csv in {path.name}")
            return archive.read(names[0]).decode("utf-8-sig")
    return path.read_text(encoding="utf-8-sig")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("path", type=Path, help="Strava export .zip or its activities.csv")
    parser.add_argument("--dry-run", action="store_true", help="parse and report, write nothing")
    args = parser.parse_args()

    try:
        activities = parse_activities_csv(read_csv(args.path.expanduser()))
    except (StravaExportError, OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        result = import_activities(db, activities)
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()

    booked = ", ".join(f"{n} {LABELS[t][n != 1]}" for t, n in result.by_activity.items()) or "nothing new"
    verb = "would import" if args.dry_run else "imported"
    print(f"{len(activities)} activities in the export: {verb} {booked}; {result.already_imported} already imported.")
    if result.skipped_types:
        skipped = ", ".join(f"{t or '(no type)'} x{n}" for t, n in sorted(result.skipped_types.items()))
        print(f"Skipped (not a ride or run): {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
