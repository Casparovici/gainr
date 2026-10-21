#!/bin/bash
# CI's smoke test: the whole app as it's deployed -- app/main.py importing every router, the
# migrations building an empty database, uvicorn serving the API and the built frontend. The unit
# tests mount routers one at a time on purpose (importing app.main would touch the real database),
# so without this a broken main.py or a failing startup would pass CI. Needs frontend/dist built.
#
#   .github/scripts/smoke.sh            # from the repository root, backend dependencies installed
set -euo pipefail
cd "$(dirname "$0")/../.."

PORT="${SMOKE_PORT:-8765}"
BASE="http://127.0.0.1:$PORT"
WORK="$(mktemp -d)"
export GAINR_DATABASE_URL="sqlite:///$WORK/smoke.db"
PYTHON="${SMOKE_PYTHON:-python}"

(cd backend && "$PYTHON" -m alembic upgrade head)
(cd backend && exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >"$WORK/server.log" 2>&1) &
SERVER=$!
trap 'kill "$SERVER" 2>/dev/null || true; rm -rf "$WORK"' EXIT

for _ in $(seq 1 30); do
  curl -fsS "$BASE/api/health" >/dev/null 2>&1 && break
  if ! kill -0 "$SERVER" 2>/dev/null; then
    cat "$WORK/server.log"
    echo "The app didn't start" >&2
    exit 1
  fi
  sleep 1
done

check() {
  local path="$1" expect="$2" body
  if ! body=$(curl -fsS "$BASE$path"); then
    cat "$WORK/server.log"
    echo "GET $path failed" >&2
    exit 1
  fi
  if ! grep -qF -- "$expect" <<<"$body"; then
    echo "GET $path didn't contain $expect" >&2
    exit 1
  fi
  echo "ok  GET $path"
}

# The API and the built page, plus a read per module that needs nothing from outside.
check /api/health '"ok"'
check / 'id="root"'
check /trainr 'id="root"'
check /api/portfolios '"name"'
check "/api/trainr/exercises" '"Plank"'
check "/api/taskr/agenda?date_from=2026-01-01&date_to=2026-01-07" '"overdue"'
check /api/gripr/accounts '['
check /api/gardnr/areas '['
check /api/listr/lists '['
check /api/listr/stores '['
check /api/briefr/reports '['
check /briefr 'id="root"'
check /api/notr/notes '['
check /api/notr/labels '['
check /notr 'id="root"'
