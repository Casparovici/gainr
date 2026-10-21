"""Imports briefr's agent reports from a checkout of the agents repository -- see
briefr_report_service and docs/adr/0044-briefr-agent-reports.md. Idempotent: an unchanged file is
skipped, a changed one replaces its report.

Runs every few minutes from deploy/briefr-import.timer, with --pull, so a report an agent pushed
during the night is in the app soon after. A file that can't be read is listed and skipped; only a
failed pull fails the unit, and even then what's already checked out is imported.

Usage (from backend/):
    python -m scripts.import_briefr_reports [--pull] [REPO_DIR]
REPO_DIR defaults to GAINR_BRIEFR_REPO_DIR.
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BRIEFR_REPO_DIR  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services import briefr_report_service  # noqa: E402


def pull(repo: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repo), "pull", "--ff-only", "--quiet"], capture_output=True, text=True, timeout=120,
    )
    if completed.returncode != 0:
        print(f"git pull failed in {repo}: {completed.stderr.strip()}", file=sys.stderr)
    return completed.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import briefr reports from the agents repository.")
    parser.add_argument("repo", nargs="?", default=BRIEFR_REPO_DIR, help="checkout of the agents repository")
    parser.add_argument("--pull", action="store_true", help="git pull the checkout first")
    args = parser.parse_args(argv)
    if not args.repo:
        print("No repository: pass its path or set GAINR_BRIEFR_REPO_DIR", file=sys.stderr)
        return 2
    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"{repo} is not a directory", file=sys.stderr)
        return 2

    pulled = pull(repo) if args.pull else True
    db = SessionLocal()
    try:
        result = briefr_report_service.import_reports(db, repo)
        db.commit()
    finally:
        db.close()
    if result.created or result.updated or result.failed:
        print(f"briefr: {result.created} new, {result.updated} updated, {result.unchanged} unchanged reports")
    for path, problem in result.failed:
        print(f"  skipped {path}: {problem}")
    return 0 if pulled else 1


if __name__ == "__main__":
    sys.exit(main())
