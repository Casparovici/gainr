#!/bin/bash
# Pulls the freshest off-box backup (see docs/adr/0013-backup-strategy.md) from homecloud down
# into this checkout's backend/portfolio.db, so local dev/testing works against real data
# instead of whatever's been hand-seeded here. Restores from the daily backup snapshot, not the
# live db -- same reasoning backup_db.py already uses sqlite3's backup API for: never copy a
# file that's mid-write.
#
# Run from anywhere in the repo:
#   deploy/sync_from_homecloud.sh
#
# Default target is root@ipper -- the box's Tailscale hostname is still "ipper" (its pre-rename
# name, kept on purpose: the app's HTTPS URL ipper.tailf12cf8.ts.net and the household's device
# share hang off it, see README's Hosting section), and /opt/gainr's deploy/backup timers all
# run as root there. Override either half if your setup differs:
#   HOMECLOUD_HOST=myuser@myhost deploy/sync_from_homecloud.sh
set -euo pipefail

HOMECLOUD_HOST="${HOMECLOUD_HOST:-root@ipper}"
HOMECLOUD_REPO="${HOMECLOUD_REPO:-/opt/gainr}"
REMOTE_BACKUP_DIR="$HOMECLOUD_REPO/backend/backups"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_BACKEND_DIR="$(cd "$SCRIPT_DIR/../backend" && pwd)"
LOCAL_DB="$LOCAL_BACKEND_DIR/portfolio.db"
LOCAL_BACKUP_DIR="$LOCAL_BACKEND_DIR/backups"

echo "Looking for the latest backup on $HOMECLOUD_HOST:$REMOTE_BACKUP_DIR..."
LATEST_REMOTE=$(ssh "$HOMECLOUD_HOST" "ls -t $REMOTE_BACKUP_DIR/portfolio-*.db.gz 2>/dev/null | head -n1")
if [ -z "$LATEST_REMOTE" ]; then
  echo "No backups found on $HOMECLOUD_HOST -- has gainr-backup.timer run there yet?" >&2
  exit 1
fi
echo "Found: $LATEST_REMOTE"

TMP_GZ="$(mktemp /tmp/portfolio-sync-XXXXXX.db.gz)"
trap 'rm -f "$TMP_GZ"' EXIT
scp -q "$HOMECLOUD_HOST:$LATEST_REMOTE" "$TMP_GZ"

mkdir -p "$LOCAL_BACKUP_DIR"
if [ -f "$LOCAL_DB" ]; then
  ASIDE="$LOCAL_BACKUP_DIR/portfolio.pre-sync-$(date +%Y%m%d-%H%M%S).db"
  mv "$LOCAL_DB" "$ASIDE"
  # The database runs in WAL mode: its -wal file holds writes not yet copied into the main file.
  # It moves along (SQLite pairs it with the database by name), so the copy set aside is
  # complete and a stale log is never replayed into the restored snapshot.
  for suffix in -wal -shm; do
    if [ -f "$LOCAL_DB$suffix" ]; then mv "$LOCAL_DB$suffix" "$ASIDE$suffix"; fi
  done
  echo "Your previous local db is kept at $ASIDE (gitignored, same as backend/backups/ always is) -- delete it by hand once you're sure you don't need it back."
fi

gunzip -c "$TMP_GZ" > "$LOCAL_DB"
echo "Restored $(basename "$LATEST_REMOTE") -> $LOCAL_DB"

echo "Running migrations (the snapshot may predate schema changes you have locally but haven't deployed yet)..."
(
  cd "$LOCAL_BACKEND_DIR"
  if [ -f .venv/bin/activate ]; then
    # shellcheck source=/dev/null
    source .venv/bin/activate
  fi
  alembic upgrade head
)

echo "Done -- local portfolio.db now mirrors homecloud as of $(basename "$LATEST_REMOTE")."
