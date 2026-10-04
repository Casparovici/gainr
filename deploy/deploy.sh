#!/bin/bash
# Pulls main if it has moved, reinstalls/rebuilds only what changed, restarts the service.
# Run on a timer (see gainr-deploy.timer) — a no-op when there's nothing new.
set -euo pipefail
cd /opt/gainr

BEFORE=$(git rev-parse HEAD)
git fetch --quiet origin main
AFTER=$(git rev-parse origin/main)

if [ "$BEFORE" = "$AFTER" ]; then
  exit 0
fi

git merge --ff-only origin/main
CHANGED=$(git diff --name-only "$BEFORE" "$AFTER")

if echo "$CHANGED" | grep -q '^backend/requirements\.txt$'; then
  backend/venv/bin/pip install -q -r backend/requirements.txt
fi

if echo "$CHANGED" | grep -q '^backend/alembic/'; then
  (cd backend && venv/bin/alembic upgrade head)
fi

if echo "$CHANGED" | grep -q '^frontend/'; then
  (cd frontend && npm ci --silent && npm run build --silent)
fi

systemctl restart gainr
echo "Deployed $BEFORE -> $AFTER"
