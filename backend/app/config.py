import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Local-dev convenience only: homecloud and any other real deployment set real environment
# variables directly (systemd, the shell), so there's no .env there and this is a no-op. Never
# overrides a variable already set in the environment (load_dotenv's default), so an explicit
# `export` still wins over a stale .env value.
load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.environ.get("GAINR_DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'portfolio.db'}")

# Base currency all EUR-converted values (value_eur, total_eur, portfolio value) are expressed in.
BASE_CURRENCY = "EUR"

CORS_ORIGINS = os.environ.get(
    "GAINR_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

# Gates the read-only listr weekplanner ICS feed (GET /api/listr/meal-plan.ics?token=...) --
# unset by default, so the endpoint stays disabled (404) until deliberately configured with a
# real secret. Never put the actual token in source; set it in the environment only.
LISTR_ICS_TOKEN = os.environ.get("GAINR_LISTR_ICS_TOKEN")

# The user's real Picnic (Dutch grocery delivery) account -- used only to (re-)authenticate
# against Picnic's private API (see app/services/picnic_provider.py); the resulting session key
# is what's actually persisted (in the picnic_session table), never these credentials. Unset by
# default, so the /api/listr/picnic/* endpoints report "not configured" rather than attempting
# a login with an empty password.
PICNIC_EMAIL = os.environ.get("GAINR_PICNIC_EMAIL")
PICNIC_PASSWORD = os.environ.get("GAINR_PICNIC_PASSWORD")

# The user's self-hosted Mealie recipe app (a Proxmox container on the LAN), for listr's
# "Ophalen uit Mealie" import -- see docs/adr/0022-listr-mealie-import.md. The URL comes from the
# environment too, never from a request, so the backend can only ever be pointed at this one
# host. The API key is a Mealie long-lived token; it's sent to Mealie as a bearer token and
# nowhere else (never logged, never returned). Both unset by default, which reports the import
# as "not configured" instead of calling out.
MEALIE_URL = os.environ.get("GAINR_MEALIE_URL")
MEALIE_API_KEY = os.environ.get("GAINR_MEALIE_API_KEY")

# Enable Banking (https://enablebanking.com), the licensed PSD2 aggregator gripr reads ING
# transactions through -- see docs/adr/0029-ing-transactions-into-gripr.md. The application id
# names the app registered in Enable Banking's control panel; the key path points at that app's
# RSA private key (a file outside the repo, readable by the service only), which signs the
# short-lived JWT every API call carries. The redirect URL is where ING sends the reader back
# after approving access -- it must be exactly the one registered with the app, and comes from
# here rather than from the request so a forged Host header can't redirect the consent anywhere
# else. All three unset by default, which reports the ING sync as "not configured".
ENABLEBANKING_APP_ID = os.environ.get("GAINR_ENABLEBANKING_APP_ID")
ENABLEBANKING_KEY_PATH = os.environ.get("GAINR_ENABLEBANKING_KEY_PATH")
ING_REDIRECT_URL = os.environ.get("GAINR_ING_REDIRECT_URL")

# Trading 212's public API (https://docs.trading212.com/api), for gripr's T212 Debit card spending
# and gainr's Trading 212 fills, dividends and interest -- see docs/adr/0031-trading212-sync.md.
# A key/secret pair generated in the Trading 212 app, sent as HTTP Basic auth to Trading 212 and
# nowhere else (never logged, never returned). Generate it read-only (no order execution) and
# restricted to the server's IP. Both unset by default, which reports the sync as "not configured".
T212_API_KEY = os.environ.get("GAINR_T212_API_KEY")
T212_API_SECRET = os.environ.get("GAINR_T212_API_SECRET")

# Where scripts/backup_db.py pushes the nightly database backup, e.g. "gdrive:gainr-backups"
# for an rclone remote named "gdrive". Unset by default, so a dev machine without rclone
# configured still takes local backups, it just doesn't push them off-box.
BACKUP_RCLONE_REMOTE = os.environ.get("GAINR_BACKUP_RCLONE_REMOTE")

# The checkout of the private agents repository (docs/adr/0044-briefr-agent-reports.md) that
# scripts/import_briefr_reports.py pulls and reads briefr's reports from, e.g.
# "/var/lib/gainr/agents" on the server. Unset by default, so a dev machine without the repository
# imports nothing unless given a path.
BRIEFR_REPO_DIR = os.environ.get("GAINR_BRIEFR_REPO_DIR")
