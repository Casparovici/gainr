"""Backs up portfolio.db once: a consistent online copy, gzipped, pruned to N days, then
pushed off-box via rclone.

Meant to run on a schedule (see deploy/gainr-backup.timer) since this is the single SQLite
file behind gainr/gripr/listr/gardnr for one user with no other copy of the data anywhere.
Uses sqlite3's own backup API rather than `cp`, so a backup taken while the app is mid-write
is still a consistent snapshot instead of a torn file.

Usage (from backend/):
    python -m scripts.backup_db
"""

import gzip
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402

BACKUP_DIR = config.BACKEND_DIR / "backups"
KEEP_DAYS = 14


def _db_path() -> Path:
    prefix = "sqlite:///"
    if not config.DATABASE_URL.startswith(prefix):
        raise RuntimeError(f"backup_db only supports sqlite DATABASE_URL, got {config.DATABASE_URL!r}")
    return Path(config.DATABASE_URL[len(prefix) :])


def _take_snapshot(source: Path, dest: Path) -> None:
    src_conn = sqlite3.connect(str(source))
    dest_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()


def _prune_local(keep_days: int) -> list[Path]:
    cutoff = datetime.now(timezone.utc).timestamp() - keep_days * 86400
    removed = []
    for path in BACKUP_DIR.glob("portfolio-*.db.gz"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed.append(path)
    return removed


def _upload(path: Path) -> str:
    if shutil.which("rclone") is None:
        return "skipped upload: rclone not installed"
    if not config.BACKUP_RCLONE_REMOTE:
        return "skipped upload: GAINR_BACKUP_RCLONE_REMOTE not set"
    result = subprocess.run(
        ["rclone", "copy", str(path), config.BACKUP_RCLONE_REMOTE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"upload FAILED: {result.stderr.strip()}"
    return f"uploaded to {config.BACKUP_RCLONE_REMOTE}"


def main() -> None:
    BACKUP_DIR.mkdir(mode=0o700, exist_ok=True)
    source = _db_path()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    snapshot_path = BACKUP_DIR / f".portfolio-{stamp}.db.tmp"
    gz_path = BACKUP_DIR / f"portfolio-{stamp}.db.gz"

    _take_snapshot(source, snapshot_path)
    with open(snapshot_path, "rb") as raw, gzip.open(gz_path, "wb") as gz:
        shutil.copyfileobj(raw, gz)
    snapshot_path.unlink()

    upload_status = _upload(gz_path)
    removed = _prune_local(KEEP_DAYS)

    print(f"Backed up {source} -> {gz_path} ({gz_path.stat().st_size} bytes)")
    print(upload_status)
    if removed:
        print(f"Pruned {len(removed)} local backup(s) older than {KEEP_DAYS} days")


if __name__ == "__main__":
    main()
