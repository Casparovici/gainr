#!/bin/bash
# Pulls main if it has moved and CI passed on it, reinstalls/rebuilds only what changed, restarts
# the service, and rolls back if the app doesn't come back up. Run on a timer (see
# gainr-deploy.timer); a no-op when there's nothing new. See docs/adr/0042.
#
# What's deployed is the commit recorded in $STATE_FILE, written only once every step has
# succeeded and the restarted app answers /api/health. Comparing against the checkout's HEAD
# instead would lose a failed deploy: the merge moves HEAD first, so after a failed install,
# migration or build the next run would see "nothing new" and never try again. A step that fails
# before the restart is retried on every run, against the full diff since the last good deploy.
#
# - CI gate: only a commit whose GitHub Actions runs all passed is deployed (scripts/deploy_github.py,
#   with the token from /etc/gainr/deploy.env). Without a token it deploys unchecked, as before,
#   and says so. GAINR_DEPLOY_SKIP_CI=1 deploys without asking, for a manual run.
# - Before migrating, a local backup (backend/backups/portfolio-<time>-pre-migrate-<sha>.db.gz).
# - If the restarted app doesn't answer, the code and the frontend go back to the last good deploy
#   and the commit is remembered as failed in $FAILED_FILE, so it isn't retried until main moves
#   on (or that file is removed). A migration that ran stays: they're additive by convention, so
#   the previous code still runs on the new schema; the pre-migrate backup is there if not.
set -euo pipefail
cd "${GAINR_DIR:-/opt/gainr}"

STATE_FILE="${GAINR_DEPLOY_STATE:-/var/lib/gainr/deployed-commit}"
STATE_DIR="$(dirname "$STATE_FILE")"
FAILED_FILE="$STATE_DIR/failed-commit"
NOTED_FILE="$STATE_DIR/deploy-noted"
HEALTH_URL="${GAINR_HEALTH_URL:-http://127.0.0.1/api/health}"
RESTART="${GAINR_RESTART_CMD:-systemctl restart gainr}"
HEALTH_TRIES="${GAINR_HEALTH_TRIES:-30}"  # a second apart

# First run after this script was introduced: whatever is checked out is what's running. Recorded
# before anything moves HEAD, so a failure later in this very run is still retried.
if [ ! -s "$STATE_FILE" ]; then
  mkdir -p "$STATE_DIR"
  git rev-parse HEAD >"$STATE_FILE"
fi
DEPLOYED=$(cat "$STATE_FILE")
git fetch --quiet origin main
TARGET=$(git rev-parse origin/main)
SHORT=${TARGET:0:7}

if [ "$DEPLOYED" = "$TARGET" ]; then
  exit 0
fi
# Rolled back from already: wait for the next commit rather than breaking the app every 2 minutes.
if [ -s "$FAILED_FILE" ] && [ "$(cat "$FAILED_FILE")" = "$TARGET" ]; then
  exit 0
fi

# The GitHub helper of whatever is checked out now; an older checkout without one counts as
# having no token.
github() {
  if [ -f backend/scripts/deploy_github.py ]; then
    (cd backend && venv/bin/python -m scripts.deploy_github "$@")
  else
    [ "$1" = ci ] && echo no-token
  fi
}

# Says something about a commit once, not on every 2-minute run. Succeeds when it was new.
note() {
  local key="$TARGET $1"
  if [ "$(cat "$NOTED_FILE" 2>/dev/null)" = "$key" ]; then
    return 1
  fi
  echo "$key" >"$NOTED_FILE"
  echo "$2"
}

healthy() {
  for _ in $(seq 1 "$HEALTH_TRIES"); do
    if backend/venv/bin/python -c "import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=2)" "$HEALTH_URL" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

if [ "${GAINR_DEPLOY_SKIP_CI:-0}" != 1 ]; then
  CI=$(github ci "$TARGET" 2>/dev/null || echo error)
  case "$CI" in
    success) ;;
    no-token) note no-token "No GAINR_DEPLOY_GITHUB_TOKEN: deploying $SHORT without checking CI" || true ;;
    failure)
      if note failure "CI failed on $SHORT: not deploying it, waiting for a newer commit"; then
        github status "$TARGET" failure "Not deployed: CI failed" || true
      fi
      exit 0
      ;;
    *)
      note "$CI" "Waiting for CI on $SHORT ($CI)" || true
      exit 0
      ;;
  esac
fi

github status "$TARGET" pending "Deploying to homecloud" || true
git merge --ff-only --quiet origin/main
CHANGED=$(git diff --name-only "$DEPLOYED" "$TARGET")

# Migrations run as whoever owns the database, so a journal or WAL file they create can still
# be opened by the app afterwards (the app need not run as root, see gainr.service).
DB_OWNER=$(stat -c %U backend/portfolio.db 2>/dev/null || echo root)
as_db_owner() {
  if [ "$DB_OWNER" = "$(id -un)" ]; then "$@"; else runuser -u "$DB_OWNER" -- "$@"; fi
}

REQUIREMENTS_CHANGED=0
if echo "$CHANGED" | grep -q '^backend/requirements\.txt$'; then
  backend/venv/bin/pip install -q -r backend/requirements.txt
  REQUIREMENTS_CHANGED=1
fi

if echo "$CHANGED" | grep -q '^backend/alembic/'; then
  (cd backend && as_db_owner venv/bin/python -m scripts.backup_db --tag "pre-migrate-$SHORT" --no-upload)
  (cd backend && as_db_owner venv/bin/alembic upgrade head)
fi

FRONTEND_SWAPPED=0
if echo "$CHANGED" | grep -q '^frontend/'; then
  # Built next to the live dist/ and swapped in only once the build succeeded, so a failed build
  # never leaves the app serving a half-emptied dist/. The previous build stays as dist.prev
  # until the restarted app answers, for the rollback.
  (
    cd frontend
    npm ci --silent
    rm -rf dist.next
    npx tsc -b
    npx vite build --outDir dist.next --emptyOutDir --logLevel warn
  )
  rm -rf frontend/dist.prev
  if [ -d frontend/dist ]; then mv frontend/dist frontend/dist.prev; fi
  mv frontend/dist.next frontend/dist
  FRONTEND_SWAPPED=1
fi

$RESTART

if healthy; then
  echo "$TARGET" >"$STATE_FILE"
  rm -f "$FAILED_FILE"
  rm -rf frontend/dist.prev frontend/dist.failed
  github status "$TARGET" success "Deployed to homecloud" || true
  echo "Deployed $DEPLOYED -> $TARGET"
  exit 0
fi

echo "Deployed $DEPLOYED -> $TARGET, but $HEALTH_URL didn't answer; rolling back to ${DEPLOYED:0:7}" >&2
git reset --hard --quiet "$DEPLOYED"
if [ "$REQUIREMENTS_CHANGED" = 1 ]; then
  backend/venv/bin/pip install -q -r backend/requirements.txt
fi
if [ "$FRONTEND_SWAPPED" = 1 ] && [ -d frontend/dist.prev ]; then
  rm -rf frontend/dist.failed
  mv frontend/dist frontend/dist.failed
  mv frontend/dist.prev frontend/dist
fi
echo "$TARGET" >"$FAILED_FILE"
$RESTART
github status "$TARGET" failure "Health check failed; rolled back to ${DEPLOYED:0:7}" || true

if healthy; then
  echo "Rolled back to ${DEPLOYED:0:7}; $SHORT stays undeployed until main moves on (or $FAILED_FILE is removed)" >&2
else
  echo "Rolled back to ${DEPLOYED:0:7}, but $HEALTH_URL still doesn't answer" >&2
fi
exit 1
