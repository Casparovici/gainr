#!/usr/bin/env bash
# Start the backend (uvicorn --reload on :8000) and the frontend (vite on :5173) together for
# local testing, with their output interleaved and prefixed. Ctrl+C stops both.
#
#   ./dev.sh                 # migrate the local database, then start both
#   ./dev.sh --no-migrate    # skip `alembic upgrade head`
#
# Uses backend/portfolio.db (or GAINR_DATABASE_URL if you export one) and backend/.env, exactly
# like running the two commands from the README by hand.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173
MIGRATE=1

for arg in "$@"; do
  case "$arg" in
    --no-migrate) MIGRATE=0 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

red() { printf '\033[31m%s\033[0m\n' "$*" >&2; }

# -- preflight ----------------------------------------------------------------------------------

if [[ ! -x "$ROOT/backend/.venv/bin/uvicorn" ]]; then
  red "No backend virtualenv with uvicorn in backend/.venv. Create it once with:"
  echo "  cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

# A second copy would fail to bind anyway; say who's holding the port instead of killing it.
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if holder=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1" (pid "$2")"}') && [[ -n "$holder" ]]; then
    red "Port $port is already in use by $holder -- stop that first (an earlier ./dev.sh?)."
    exit 1
  fi
done

if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Installing frontend dependencies (first run)..."
  (cd "$ROOT/frontend" && npm install)
fi

if [[ "$MIGRATE" == 1 ]]; then
  echo "Applying database migrations..."
  (cd "$ROOT/backend" && .venv/bin/alembic upgrade head)
fi

# -- run ----------------------------------------------------------------------------------------

# Every child joins this script's process group, so one `kill 0` takes down uvicorn's reloader
# and vite's own children too, whether we got Ctrl+C or one side exited on its own.
cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Stopping backend and frontend..."
  kill 0 2>/dev/null || true
}
trap cleanup INT TERM EXIT

prefix() { sed -u "s/^/$1 /"; }

(cd "$ROOT/backend" && exec .venv/bin/uvicorn app.main:app --port "$BACKEND_PORT" --reload 2>&1) \
  | prefix $'\033[36m[backend]\033[0m' &
(cd "$ROOT/frontend" && exec npm run dev -- --port "$FRONTEND_PORT" --strictPort 2>&1) \
  | prefix $'\033[35m[frontend]\033[0m' &

echo
echo "  App:  http://localhost:$FRONTEND_PORT   (API on :$BACKEND_PORT, proxied under /api)"
echo "  Ctrl+C stops both."
echo

# If either side dies (a syntax error, a port grabbed in the meantime), stop the other too
# rather than leaving half the app running.
wait -n
red "One of the two processes exited -- stopping the other."
