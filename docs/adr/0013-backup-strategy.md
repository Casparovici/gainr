# 13. Daily off-box backup of portfolio.db

## Status

Accepted

## Context

A whole-codebase audit (2026-09) flagged `backend/portfolio.db` as the highest-severity
operational risk in the app: it's the single copy of every module's data (gainr, gripr, listr,
gardnr), gitignored by design (CLAUDE.md: never commit real financial data), and lives on one
Proxmox LXC. A disk failure or an accidental `rm` loses years of transaction history with no
recovery path. CSV export exists on gainr/gripr, but it's manual, partial, and not triggered on
any schedule — not a real backup story.

## Decision

`backend/scripts/backup_db.py`, run daily by `gainr-backup.timer` (03:30, before the price
refresh at 06:00), does three things:

1. Takes a consistent snapshot via `sqlite3.Connection.backup()` — the same API SQLite itself
   recommends for backing up a live database — rather than `cp`, which can copy a file mid-write
   on a database that's actively serving requests.
2. Gzips it into `backend/backups/portfolio-<timestamp>.db.gz` and prunes anything older than 14
   days, so local disk use stays bounded without a separate cron entry.
3. Pushes the fresh backup off-box with `rclone copy` to whatever remote
   `GAINR_BACKUP_RCLONE_REMOTE` names (an env var, e.g. `gdrive:gainr-backups`), read from
   `/etc/gainr-backup.env` on the box — never committed to git, same convention as the Picnic
   credentials in `config.py`.

If `rclone` isn't installed or the remote isn't configured, the script still takes and prunes
local backups and just skips the upload — a dev machine gets backups-of-convenience for free
without needing cloud credentials, and a misconfigured remote degrades to "local backups only"
rather than crashing the whole job.

## Alternatives considered

- **Litestream (continuous SQLite replication)**: would give near-zero RPO instead of up to 24h,
  but is another daemon to run and monitor for a single-user app where losing at most a day of
  transactions (re-enterable from bank statements) is an acceptable trade against operational
  simplicity.
- **`cp`/`sqlite3 .backup` CLI instead of the Python API**: the `sqlite3` CLI isn't installed on
  the box (Debian's minimal image) and shelling out to it would be one more thing to apt-install
  and keep present; Python's stdlib `sqlite3` module is already there because the app needs it.
- **Backup target = another Tailscale node / this dev machine**: considered, but neither is
  guaranteed always-on; genuine cloud storage (rclone to Google Drive) was chosen for real
  off-box durability independent of any of the user's own machines being up.

## Consequences

- Up to 24h of data loss (RPO) in the worst case — the gap between the last nightly backup and
  a failure. Acceptable for this app's stakes; revisit if that ever isn't true.
- `rclone`'s Google Drive remote is authenticated once, interactively (OAuth), directly on the
  box — the resulting token lives only in that box's `rclone.conf`, never in this repo or in any
  chat transcript.
- Restoring is a manual, undocumented-in-code step today (download the `.gz`, gunzip, drop it in
  as `portfolio.db`, restart `gainr.service`) — fine for a rare single-user recovery, but if this
  is ever exercised for real it's worth writing the two-command restore path down somewhere
  durable.

## Addendum: restoring onto a dev machine, not just recovering the box

The same backups also solve a second, more routine problem: local dev drifting out of sync with
what's actually in production, making local testing unrepresentative. `deploy/sync_from_homecloud.sh`
scripts the restore path above, retargeted at a laptop instead of the box itself — SSH in, find
the newest `portfolio-*.db.gz`, pull it, set the current local `portfolio.db` aside (into the
already-gitignored `backend/backups/`, never deleted automatically) rather than overwrite it in
place, and run `alembic upgrade head` afterward since local code is often ahead of whatever
schema the snapshot was taken under. This doesn't touch the recovery scenario ADR 0013 itself was
written for — `gainr.service` restoring onto the box after real data loss is still the manual
step described above — it's a distinct, lower-stakes use of the same nightly artifact.
