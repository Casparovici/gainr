# gainr

A self-hosted all-in-one app with four modules in one codebase:

| Module | What it's for | Language |
| --- | --- | --- |
| **gainr** | Investment portfolios: performance, allocation, per-position research | English |
| **gripr** | Personal finance: accounts, budgets, recurring payments, bank sync | English |
| **listr** | Groceries and recipes, with Picnic and Mealie integration | Dutch |
| **gardnr** | Garden map, plants and care schedules | Dutch |

It runs for one household on a home server, reachable only over Tailscale. An Android app wraps
the same site.

## Features

### gainr

- Several portfolios (e.g. Main and Kids), each with its own ledger, positions and performance.
- Time-weighted performance (1D, 1M, YTD, 1Y, Max) against the S&P 500, Nasdaq and MSCI World.
- Per position: cost basis, realised and unrealised P&L, target weight, news, financials, an
  earnings and dividend calendar, and notes. A journal collects notes across positions.
- Cash per broker, with transfers between brokers.
- Trading 212 sync: fills, dividends, and a weekly interest/cashback deposit, booked automatically.
- A notifications bell: what the Trading 212 sync booked, instruments waiting for an asset.
- Prices and FX are daily closes from Yahoo Finance, converted to EUR at the rate of the day.

### gripr

- Accounts with derived or manual balances, virtual pots, and net worth by account type.
- Transactions (expense, income, refund, transfer), future-dated entries kept out of totals until
  their date.
- Recurring rules, budgets per category with suggested amounts, savings goals, loan-linked
  categories.
- Bank sync for ING and Trade Republic (via Enable Banking) and Trading 212: entries are matched
  to what you entered, filed under the recurring rule they fulfil, or booked for you to categorise.
- Money you front for others: mark what you expect back on an expense; spending counts your share, and
  repayments close it.
- Accounts can track a gainr portfolio: transfers mirror into its cash, the balance follows its value.
- Periods can start on any day of the month (e.g. payday).
- A notifications bell: what the syncs booked, money that came back, banks needing attention.
- An MCP server lets a chat assistant add a transaction from a description.

### listr

- Shopping lists, recipes linked to a product catalog, a meal planner with a calendar feed.
- Pantry stock with minimums and a one-tap restock list.
- Picnic: push a list to the cart, order, browse offers, import recipes, and book deliveries into
  gripr and the pantry.
- Recipe import from a self-hosted Mealie.

### gardnr

- A map of each garden with zones and plants, drawn in the app.
- Care schedules per plant, a "today" view of what's due, and a care log with photos.

## Tech stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, SQLite.
- **Frontend**: React, TypeScript, Vite, Tailwind, TanStack Query, Recharts.
- **Android**: Capacitor, loading the deployed site.

Money is `Decimal`/`NUMERIC`, never float. Positions and balances are derived from the ledger on
every request, never stored. The backend is layered routers → services → repositories → models;
external data sources sit behind provider classes.

## Getting started

Requirements: Python 3.11+, Node 20+.

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# Frontend
cd ../frontend && npm install

# Run both (applies migrations, then starts the API on :8000 and the UI on :5173)
cd .. && ./dev.sh
```

Open <http://localhost:5173>. To run them separately:

```bash
cd backend && uvicorn app.main:app --port 8000 --reload
cd frontend && npm run dev
```

### Seeding data

The database starts empty. Real data stays out of git (`*.xlsx`, `personal_trx.csv` and
`backend/portfolio.db` are ignored).

```bash
cd backend
python -m scripts.import_transactions ../portfolio.xlsx                  # gainr, "Main" portfolio
python -m scripts.import_transactions ../portfolio_kids.xlsx --portfolio Kids
python -m scripts.import_gripr ../personal_trx.csv                         # gripr
python -m scripts.seed_listr                                               # listr product catalog
```

Imports are idempotent. To work against production data instead, `deploy/sync_from_homecloud.sh`
pulls the latest server backup into `backend/portfolio.db`.

## Configuration

Everything is optional; a feature whose settings are missing hides itself. Set them in the
environment, or in `backend/.env` for local development (gitignored).

| Variable | Used for |
| --- | --- |
| `GAINR_DATABASE_URL` | Database location (default `sqlite:///backend/portfolio.db`) |
| `GAINR_CORS_ORIGINS` | Allowed origins for the dev server (default `localhost:5173`) |
| `GAINR_T212_API_KEY`, `GAINR_T212_API_SECRET` | Trading 212 sync. Generate a read-only key, restricted to the server's IP |
| `GAINR_ENABLEBANKING_APP_ID`, `GAINR_ENABLEBANKING_KEY_PATH`, `GAINR_ING_REDIRECT_URL` | Bank sync for ING and Trade Republic via Enable Banking |
| `GAINR_PICNIC_EMAIL`, `GAINR_PICNIC_PASSWORD` | Picnic integration |
| `GAINR_MEALIE_URL`, `GAINR_MEALIE_API_KEY` | Mealie recipe import |
| `GAINR_LISTR_ICS_TOKEN` | Enables the meal-plan calendar feed |
| `GAINR_BACKUP_RCLONE_REMOTE` | Off-site destination for the daily backup |

## Project structure

```text
backend/
  app/            routers, services, repositories, models, schemas (one flat set for all modules)
  alembic/        migrations
  scripts/        imports, daily sync jobs, backups
  tests/
frontend/
  src/            pages and components per module, shared UI in components/ui
  android/        Capacitor wrapper
mcp-server/       MCP server for adding gripr transactions from chat
deploy/           systemd units and the deploy script
docs/adr/         architecture decision records
```

gripr, listr and gardnr files carry a module prefix (`gripr_account.py`, `pages/listr/`); gainr's
are unprefixed.

## Development

```bash
cd backend && pytest                 # backend tests
cd frontend && npm test              # frontend tests (Vitest)
cd frontend && npm run build         # production build, includes the typecheck
cd frontend && npm run lint          # ESLint
cd mcp-server && pytest              # MCP server tests
```

CI (GitHub Actions) runs the backend tests, and the frontend lint, tests and build, on every push.

A change that touches the schema, a data source or caching gets an ADR in `docs/adr/`. Every
user-visible change gets a `CHANGELOG.md` entry. Coding standards per area live in
`.claude/rules/`.

UI conventions shared by all modules:

- Each module has its own brand colour; the design kit is in `frontend/design/`.
- Dark mode is a CSS override layer in `index.css`, not `dark:` variants on components.
- Below 640px, pages use a bottom navigation bar, and tables scroll within themselves.
- Explanatory text sits behind an ⓘ next to its title; only short status lines stay on screen.

## Deployment

The app runs on a home Proxmox container as one process: `uvicorn` serves the API and the built
frontend on port 80. It's reachable over Tailscale at `https://ipper.tailf12cf8.ts.net`. Other
household members get access through a Tailscale device share, not an in-app login.

systemd units, in `deploy/`:

| Unit | What it does |
| --- | --- |
| `gainr.service` | The app |
| `gainr-deploy.timer` | Every 2 minutes: if `main` moved, pull, install what changed, migrate, build, restart |
| `gainr-refresh.timer` | Daily 04:30 UTC, after Trading 212 posts the night's card payments: prices, Picnic, bank and Trading 212 syncs |
| `gainr-backup.timer` | Daily: consistent SQLite snapshot, kept 14 days, pushed off-site with rclone |

Secrets live in `/etc/gainr/env`, read by the app and the daily jobs. The deploy script doesn't
install units: after changing one, copy it to `/etc/systemd/system/` and run
`systemctl daemon-reload`.

The only public endpoint is the meal-plan calendar feed, served on its own Tailscale Funnel port
and protected by a token.

### Android

```bash
cd frontend && npm run build && npx cap sync android
cd android && ./gradlew assembleDebug
```

The app loads the deployed site, so web deploys update it too. Builds are sideloaded, not
published.

## Documentation

- [`docs/adr/`](docs/adr/README.md): why things are built the way they are
- [`CHANGELOG.md`](CHANGELOG.md): what changed, newest first
- [`ROADMAP.md`](ROADMAP.md): what's planned

## License

[MIT](LICENSE): use, change and share it freely; it comes without any warranty.

## Run your own copy

A step-by-step guide to running this app for yourself on a laptop. It was built for one
household, so a few parts (Dutch module texts, specific banks, a home-server deployment) are
specific to that setup; step 7 lists them.

### 1. Install the prerequisites

- **Git**
- **Python 3.11 or newer** (`python3 --version`)
- **Node.js 20 or newer** (`node --version`)

macOS and Linux work as described. On Windows, use WSL: `dev.sh` is a bash script.

### 2. Get the code

Fork the repository on GitHub if you want to keep your own changes, then clone it:

```bash
git clone https://github.com/<you>/<your-fork>.git gainr
cd gainr
```

### 3. Set up the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows (WSL): the same
pip install -r requirements.txt
alembic upgrade head               # creates backend/portfolio.db
cd ..
```

The database is a single SQLite file, `backend/portfolio.db`. It's gitignored, so your data never
ends up in a commit.

### 4. Set up the frontend

```bash
cd frontend
npm install
cd ..
```

### 5. Start the app

```bash
./dev.sh
```

This applies any pending migrations, then starts the API on port 8000 and the web app on port
5173. Open <http://localhost:5173>. Ctrl+C stops both.

### 6. Add your data

The app starts empty, with one gainr portfolio called "Main".

- **gainr:** add transactions with "Add transaction" on the Transactions page. Prices come from
  Yahoo Finance on their own, no account needed. To import a history from a spreadsheet, put it in
  an `.xlsx` file with a sheet named "Transaction" and these columns from row 2: date, type,
  ticker, stock, amount, price, local value, fx, value, costs, total, broker. Then run
  `python -m scripts.import_transactions ../your-file.xlsx` from `backend/` (with `.venv` active).
  It's safe to run again.
- **gripr:** create your accounts on the Accounts page, then add transactions by hand.
- **listr:** load the starter product catalog (about 220 Dutch grocery products) with
  `python -m scripts.seed_listr` from `backend/`.
- **gardnr:** add a garden on Tuinen and draw it.

### 7. Adjust what's specific to the original setup

- **Integrations are optional.** Picnic, Mealie, the bank sync (ING and Trade Republic through
  Enable Banking), Trading 212 and the off-site backup each switch on only when their variables are
  set (see [Configuration](#configuration)). Without them, their buttons don't appear. Put
  variables in `backend/.env`; that file is gitignored.
- **Language.** listr and gardnr are in Dutch, written directly in the pages; there's no
  translation layer.
- **Banks and logos.** The bank sync and the bank logo list are set up for Dutch banks. Another
  bank needs to be available through Enable Banking and added as a row in `bank_connections` (see
  ADR 0029).
- **Hosting.** Everything in `deploy/` (systemd units, the auto-deploy, the Tailscale address) and
  the Android app's address in `frontend/capacitor.config.ts` point at the original home server.
  For laptop use you can ignore them.

### 8. Keep it running

- **Updating:** after pulling new code, run `pip install -r requirements.txt` in `backend/` and
  `npm install` in `frontend/`, then `./dev.sh`; it migrates the database for you.
- **Backing up:** copy `backend/portfolio.db` somewhere safe, or run
  `python -m scripts.backup_db` from `backend/` for a consistent, compressed copy in
  `backend/backups/`.
- **One process instead of two:** run `npm run build` in `frontend/`, then
  `uvicorn app.main:app --port 8000` in `backend/`, and open <http://localhost:8000>.
