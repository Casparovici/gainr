# 42. Deploy: only what passed CI, a backup before migrating, and a rollback

## Status

Accepted

## Context

`main` deploys itself: `gainr-deploy.timer` runs `deploy/deploy.sh` every 2 minutes on the home
server. It pulls, installs and builds what changed, restarts, checks `/api/health` and retries a
failed step. That's continuous deployment by pull, and it stays. A push from GitHub Actions would
need a way into the tailnet and an SSH key stored in GitHub, which is more exposure for no gain.

A review found four gaps in it:

- **CI didn't gate anything.** Branch protection isn't available on a free private repository, so
  CI was advisory. The server deployed whatever landed on `main`, usually before CI on that commit
  had finished, and a red commit deployed like a green one.
- **Migrations ran without a fresh backup.** The newest copy was the 03:30 nightly.
- **A failed health check left the app down.** The new code stayed in place, and the deploy was
  retried every 2 minutes against the same broken commit.
- **A failed deploy was only visible in the server's journal.**

## Decisions

**The CI gate runs on the server.** Before merging, `deploy.sh` asks GitHub about the target
commit (`backend/scripts/deploy_github.py`, standard library only).

- It uses the Actions API (`/actions/runs?head_sha=`) and takes each workflow's latest run, so a
  re-run of a flaky job counts. Only runs started by a push count: Dependabot's own update jobs
  ("dynamic"), schedules and manual dispatches run on `main`'s commit too, and a failing one says
  nothing about whether the commit is safe.
- **Every run passed:** deploy. **One failed:** don't, and wait for a newer commit. **Still
  running, or none started yet:** wait for the next run of the timer. **GitHub didn't answer:**
  treated as waiting, never as a pass.
- Each situation is logged once per commit, not every 2 minutes.
- The token is `GAINR_DEPLOY_GITHUB_TOKEN` in `/etc/gainr/deploy.env`, which only the deploy unit
  reads. It's a fine-grained token for this repository only, with Actions: read and Commit
  statuses: read and write.
- **Without a token**, deploys go ahead unchecked, as before, and the log says so once per commit.
  This lets the change ship before the token exists.
- `GAINR_DEPLOY_SKIP_CI=1` skips the gate for a manual run.

**A local backup before every migration.** When `backend/alembic/` changed, `scripts.backup_db
--tag pre-migrate-<sha> --no-upload` runs first, as the database's owner. The file is
`backend/backups/portfolio-<time>-pre-migrate-<sha>.db.gz`, pruned with the nightlies after 14
days. A failed backup stops the deploy before the migration, and the deploy is retried.

**Roll back when the restarted app doesn't answer.**

- The previous frontend build (`dist.prev`) is kept until the health check passes.
- On failure, the checkout is reset to the last good commit, its requirements are reinstalled if
  they changed, its frontend is put back, and the app is restarted.
- The commit is written to `/var/lib/gainr/failed-commit` and isn't tried again until `main`
  moves on, or that file is removed.
- A migration that already ran is not undone. Migrations here are additive by rule (the
  data-modeller rule: nullable columns, new tables), so the previous code still runs on the new
  schema. If one ever isn't, the pre-migrate backup is the way back, by hand.
- A step that fails before the restart (install, migration, build) is still simply retried, as
  before: the running app was never touched.

**The deploy's outcome is reported on the commit.** The same helper sets a `homecloud/deploy`
commit status: pending while deploying, then success, or failure with the reason (CI failed, or
the health check failed and it rolled back). It shows on the commit and on its PR. Reporting
never fails a deploy.

## Alternatives considered

- **Deploy from GitHub Actions over Tailscale (a push).** It needs a Tailscale auth key and an SSH
  key in GitHub secrets, and the box would accept deploys from outside. Rejected.
- **Branch protection on `main`.** It isn't available on the free plan for a private repository,
  and it would gate merges, not what the server pulls.
- **Undoing migrations on rollback** (`alembic downgrade`). Downgrades are rarely exercised, and one
  that drops a column loses data written since. Restoring the backup by hand is safer, for the
  rare case where it's needed at all.

## Consequences

- The token has to be created on GitHub and put in `/etc/gainr/deploy.env`, and the changed
  `gainr-deploy.service` installed (README, Deployment). Until then, deploys behave as before, plus
  the pre-migrate backup and the rollback.
- A commit whose CI never runs (an Actions outage) waits until it does, or until a manual
  `GAINR_DEPLOY_SKIP_CI=1` run.
- `deploy.sh` was tested end to end against a scratch git server: CI pending, green with a
  migration, red, a failed health check with rollback, and no token. `deploy_github.py` and the
  tagged backup are tested in the backend suite.
