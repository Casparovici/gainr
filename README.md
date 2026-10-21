# gainr

A self-hosted all-in-one app with eight modules in one codebase, opening on **Vandaag**: one
screen of what needs you today across all of them (late garden care and tasks, payments to
categorise, unread reports, the portfolio's move, what's safe to move out, today's agenda and
tonight's meal), each linking to its module (ADR 0048).

| Module | What it's for | Written in |
| --- | --- | --- |
| **gainr** | Investment portfolios: performance, allocation, per-position research | English |
| **gripr** | Personal finance: accounts, budgets, recurring payments, bank sync | English |
| **listr** | Groceries and recipes, with Picnic and Mealie integration | Dutch |
| **gardnr** | Garden map, plants and care schedules | Dutch |
| **trainr** | Workouts: home gym, running, cycling, football and padel, planned and logged | Dutch |
| **taskr** | One agenda of what's due in gardnr and trainr, plus your own tasks; shown on Vandaag, with the full agenda at `/taskr` | Dutch |
| **briefr** | An inbox for the reports AI agents write overnight (holdings scan, app builder, …) | English |
| **notr** | Notes in Markdown, with pictures, labels and links to positions, plants and recipes | English |

The whole app can be shown in English or Dutch: Settings > Language (ADR 0049). The table says
which language each module's code is written in. Text the server writes stays in that language:
agenda titles, notifications, reports and the product catalogue.

It runs for one household on a home server, used over Tailscale (it also answers on the home LAN;
see Deployment). An Android app wraps
the same site.

## Features

### gainr

- Several portfolios (e.g. Main and Kids), each with its own ledger, positions and performance.
- Home leads with the portfolio's value and today's move (time-weighted, at the hourly live prices),
  then the year's and all-time return, the chart, and the holdings: each with today's move and its
  weight against its target. On a wide screen the figures and the allocation sit beside the chart.
- The headline performance figure is the **money-weighted return** (XIRR, ADR 0051): what the
  portfolio returned on the money actually in it, with the timing of your own deposits. It's the big
  number in the chart's header for each range (1M, YTD, 1Y, Max; per year from a year up) and the
  figure in the "This year" and "Since start" tiles. For one day, or when no rate exists, the
  time-weighted return stands in and is labelled so.
- Time-weighted performance (1D, 1M, YTD, 1Y, Max) against the S&P 500, Nasdaq and MSCI World: the
  chart's line, and the figure beside the headline, stay time-weighted because that is the one that
  compares fairly with a benchmark.
- Income: dividends received per month, year and holding, what the holdings are expected to pay
  over the next 12 months, and the yield on market value and on cost.
- Rebalance helper: enter an amount (new money or cash already there) and see what to buy to move
  towards the target weights, buying only and only holdings DLT rates Attractive or Neutral.
- Per position: a price chart (1D, 1W, 1M, YTD, 3Y, ADR 0053; 1D is the last session's intraday
  prices, fetched from Yahoo when opened and not stored), cost basis, realised and unrealised P&L, target weight, news, financials, an
  earnings and dividend calendar, and notes. The Journal collects the notes written about positions
  (they are notr's notes, ADR 0050).
- A Metrics tab for the holdings with an analyst checklist (`fundamentals_metrics.py`): the figures
  that decide how each is judged, from Yahoo where it has them; the rest stay listed as not on Yahoo,
  with where to look.
- Cash per broker, with transfers between brokers, and a read-only list of every cash movement behind the balance.
- Files (invoices, contract notes) can be attached to a transaction: PDF, PNG, JPEG or WebP, kept in
  the database so the daily backup covers them (gripr transactions can carry files too).
- Trading 212 sync: fills, dividends and the weekly interest booked automatically; the cashback is a
  deposit in the portfolio and income in a gripr account of your choice.
- A notifications bell: what the Trading 212 sync booked, instruments waiting for an asset.
- Prices and FX are daily closes from Yahoo Finance, converted to EUR at the rate of the day. On
  top of that, a live quote per holding (and FX rate) is fetched at most once an hour: current
  values, weights, P&L and the chart's today point use it while it's under two hours old; history
  and returns stay on closes. Most European listings are about 15 minutes delayed at Yahoo.

### gripr

- Accounts with derived or manual balances, virtual pots, and net worth by account type.
- Transactions (expense, income, refund, transfer), future-dated entries kept out of totals until
  their date. Files (invoices, receipts) can be attached to a transaction.
- Recurring rules, budgets per category with suggested amounts, savings goals (the Savings tab opens
  with the room to save: budgeted income minus budgeted expenses for the period, and how much of it
  the goals plan), loan-linked
  categories.
- Bank sync for ING and Trade Republic (via Enable Banking) and Trading 212: entries are matched
  to what you entered, filed under the recurring rule they fulfil, or booked for you to categorise.
  Trade Republic sends only amounts, so its payments show up uncategorised on the morning run; entering
  the payment afterwards takes over that row rather than adding a second one.
- Depreciation: a monthly transfer into a fund can be what a car loses, so its value follows the plan
  while the fund follows the market.
- Money you front for others: mark what you expect back on an expense; spending counts your share, and
  repayments close it.
- Accounts can track a gainr portfolio: transfers mirror into its cash, the balance follows its value.
- Periods can start on any day of the month (e.g. payday).
- Transactions: search (notes, category, account, amount) and a select mode to file, move or delete
  several at once; after categorising a bank payment, the others from that counterparty are offered.
- Each category compared with its usual (the 3 periods before) on Overview and in its dialog.
- Subcategories show up where the money goes: a category's dialog and Overview split its spending by
  subcategory, and bank payments learn the (sub)category you gave the same counterparty before.
- Overview's balance chart: the current period's checking balance day by day, actual up to today
  then a forecast for the rest of the period from recurring rules and remaining budget, spread over
  the weekdays you tend to spend on, with what is safe to move out today.
- Overview's savings rate and runway, and a "Needs attention" list of budgets missed the same way
  three periods running.
- A notifications bell: what the syncs booked, money that came back, banks needing attention.

### listr

- Shopping lists, recipes linked to a product catalog, a meal planner with a calendar feed. A planned meal can be moved to another day from its day dialog.
- Supermarkets (ADR 0052): add the shops you use and arrange their categories in the order you walk
  through them. A shopping list set to a store shows its groups in that order, and a list without one
  follows the standard category order. Arranging is done with arrows, in the stores sheet ("Winkels
  beheren…" in a list's store picker).
- On a shopping list and on the Producten page each category folds away by tapping its header
  ("Alles inklappen" does all at once), remembered on this device (per list for a list), and a line is
  ticked by tapping its name, not only the box.
- Pantry stock with minimums and a one-tap restock list.
- Leftovers: keep cooked meals ("2 meals for 4 in the freezer") with a use-by date, and eat them from the meal planner.
- Picnic: push a list to the cart, order, browse offers, import recipes, and book deliveries into
  gripr and the pantry.
- A photo per recipe, shown in the recipe list and on the recipe.
- Recipe import from a self-hosted Mealie, pictures included.

### gardnr

- A map of each garden with zones and plants, drawn in the app.
- Care schedules per plant, a "today" view of what's due, and a care log with photos.

### trainr

- A week/month planner for workouts (home gym, running, cycling, football, padel); tick one off to log it.
- Runs and rides: distance, time and top speed, with average speed and pace worked out.
- Football and padel: time, total calories, and average and maximum heart rate per match.
- Home gym: exercises with sets, reps and weight in kg, a "last time" hint per exercise, and a
  catalogue of suggested dumbbell/barbell/bodyweight exercises you can extend. Each exercise can
  link a how-to demo (start and end photo, plus the steps) from the public-domain
  free-exercise-db catalogue; the suggestions come linked.
- Guided workouts: start a planned gym session from the planner and trainr steps through it set by
  set, with target reps and weight, a countdown for timed holds, a rest timer between sets and
  skip/tick-off per set or exercise; finishing saves it as done with what you actually lifted and
  how long each exercise took (rests not counted). An exercise's demo plays while you do its sets,
  and the next one's during the rest.
- History per week (Monday to Sunday), month or year with totals per activity.
- An overview per activity (picked from a dropdown): km this week/month/year/ever, monthly and
  yearly charts, records; for football and padel, calories and heart rate per period; for home gym, weight progress per exercise and sets per muscle group.
- Import rides and runs from a Strava account export (`scripts/import_strava.py`).

### taskr

- An agenda of everything due across the modules: gardnr's care actions and trainr's
  planned workouts.
- A day, a week (7 days) or a month (30 days), each starting today, with previous/next to page
  through; whatever is still open from before the range is listed first ("Achterstallig").
- A module's line links to the module that owns it, where you tick it off, and it drops off the
  agenda by itself.
- Your own tasks, for to-dos that don't belong to a module: add one with a title and a day, tick it
  off on the agenda (with an undo), and tap it to change its title, day or notes, or delete it. An
  open task stays overdue until it's done.

### briefr

- An inbox of the reports your agents write: newest first, each marked **Act**, **Watch** or
  **Info** by its most urgent finding, with an unread dot until you open it.
- A report opens in place: its findings, each with the agent's verdict, a link to the position when
  it's about a holding and links to its sources, then the write-up.
- Filter by agent and by level; mark a report unread, or archive it (the Archive tab keeps them, and
  can move one back).
- Agents never write to the app. They commit Markdown files to a private agents repository; the
  server pulls it every 10 minutes and imports what's new (`scripts/import_briefr_reports.py`), and
  nightly writes the context they work from: tickers, names and weights per portfolio, no amounts,
  each holding's headlines of the last 3 days from the same feeds as its News card, extra
  sources included, and listr's product names (`scripts/export_briefr_context.py`). The file format is in ADR 0044.
- Performance reports on the gainr portfolios, computed on the server every morning (ADR 0045):
  daily (Tuesday to Saturday, for the last weekday), weekly (Saturday) and monthly (on the 1st),
  each as a separate report per portfolio. In each: the time-weighted return, the change in euros, the benchmarks over the same
  days, and per holding its price change and what it contributed, in euros and in points of the
  start value, for the positions still held at the period's end (one sold out during it counts
  in the portfolio's figures only). Big moves, stale prices and (weekly and monthly) drift from a
  target weight are flagged. `python -m scripts.briefr_performance --date 2026-10-17 --period
  weekly` writes one by hand.
- A weekly gym plan, every Sunday at 12:00 (ADR 0046): from the last three weeks of home-gym
  sessions, the server plans next week's three sessions of about 45 minutes for muscle growth (8–12
  reps, more weight once you reach 12), around the padel, football, runs and rides in the planner,
  and puts them in trainr's planner. The Dutch report in briefr explains the week. Your workout
  history never leaves the server.
- A home chef, every Friday morning (ADR 0054): an agent suggests five recipes for the coming week,
  preferably from Dutch sites, each written out with its ingredients and steps. **Plan in listr**
  on a recipe picks a day of the next two weeks (asking before replacing what's planned there),
  adds the recipe to listr's recipes the first time (ingredients that match a product become
  recipe lines, the rest go into its notes) and plans it in the weekplanner.

### notr

- Notes in **Markdown**: headings, bold and italic, lists, **checklists you tick off in place**,
  quotes, code, tables and links. The editor has a toolbar, a Write / Preview switch, and Enter
  continues a list.
- **Pictures** in a note: paste a screenshot, drop a file, or pick one (a phone offers its camera).
  They are stored in the database, scaled to 1600 px, so the daily backup covers them (ADR 0050).
  Only PNG, JPEG and WebP are accepted.
- Labels, a pin (pinned notes lead the list and show on Vandaag), archiving, and search over titles
  and text.
- A note can be about positions, plants and recipes, or about nothing. The same note then shows in
  notr, in the Notes section of each position, plant and recipe it is about, and, for positions,
  in gainr's Journal: one table, several views. A note about a position can start from a thesis
  template (why I own it, what would make me sell, risks).
- Vandaag has a "+ Notitie" button and lists the pinned notes. In briefr, "Save as note" turns a
  report into a note, linked to the positions it is about.

## Tech stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, SQLite.
- **Frontend**: React, TypeScript, Vite, Tailwind, TanStack Query, Recharts.
- **Android**: Capacitor, loading the deployed site.

Money is `Decimal`/`NUMERIC`, never float. Positions and balances are derived from the ledger on
every request, never stored. The backend is layered routers → services → repositories → models;
external data sources sit behind provider classes.

## Getting started

Requirements: Python 3.11+, Node 20+ (running the frontend tests needs Node 22.22.2 or 24.15 or newer).

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
python -m scripts.import_strava ~/Downloads/export_123.zip                 # trainr, rides and runs from a Strava export
```

Imports are idempotent. Locally there's no hourly timer, so values stay on daily closes until you
run `python -m scripts.refresh_quotes` (a holding quoted within the last hour is skipped).
To work against production data instead, `deploy/sync_from_homecloud.sh`
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
| `GAINR_BRIEFR_REPO_DIR` | Checkout of the agents repository briefr imports reports from and exports context to (the units set `/var/lib/gainr/agents`) |

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
deploy/           systemd units and the deploy script
docs/adr/         architecture decision records
```

gripr, listr, gardnr, trainr, taskr, briefr and notr files carry a module prefix (`gripr_account.py`, `pages/listr/`); gainr's
are unprefixed.

## Development

```bash
cd backend && pytest                 # backend tests
cd backend && ruff check .           # backend lint (pip install -r requirements-dev.txt)
cd frontend && npm test              # frontend tests (Vitest)
cd frontend && npm run build         # production build, includes the typecheck
cd frontend && npm run lint          # ESLint
```

CI (GitHub Actions, `.github/workflows/ci.yml`) runs on every push and pull request, on the
server's Python (3.13):

- **backend**: Ruff, the tests with coverage, and a floor of 80% per service module (the
  `*_provider.py` adapters exempt)
- **frontend**: lint, tests and the build
- **smoke**: migrates an empty database, starts the whole app and checks the API and the built
  page answer (`.github/scripts/smoke.sh`, which runs locally too)
- **audit**: known vulnerabilities in the Python dependencies, and in the production npm ones at
  high severity and up

Dependabot opens weekly update PRs, minor and patch bumps grouped per ecosystem. The home server
deploys a commit only once CI passed on it (ADR 0042).

A change that touches the schema, a data source or caching gets an ADR in `docs/adr/`. Every
user-visible change gets a `CHANGELOG.md` entry. Coding standards per area live in
`.claude/rules/`.

UI conventions shared by all modules:

- Each module has its own brand colour; the design kit is in `frontend/design/`.
- Dark mode is a CSS override layer in `index.css`, not `dark:` variants on components.
- The language (English or Dutch) is a per-browser preference, like the font: every UI string
  goes through `t()` from `src/i18n/`, keyed by the text as written, with its translation in
  `src/i18n/messages/` (one file per module and direction). `i18n.test.ts` fails when a string
  has no translation.
- The font is a per-browser preference (Settings in gainr or gripr): `data-font` on `<html>` swaps the `--font-display` and `--font-text` variables. A new package is a block in `index.css`, an entry in `utils/fontPackages.ts` and its family in the Google Fonts link in `index.html`.
- Dropdowns are native `<select>`s restyled globally in `index.css` (chevron, padding, hover); the opened list is the system picker.
- Below 640px, pages use a bottom navigation bar, and tables scroll within themselves.
- Explanatory text sits behind an ⓘ next to its title; only short status lines stay on screen.
- Settings sections start folded; sync actions are an icon (`SyncButton`), not a word.

## Deployment

The app runs on a home Proxmox container as one process, as its own unprivileged `gainr` user:
`uvicorn` serves the API and the built frontend on port 80. It's meant to be used over Tailscale
at `https://ipper.tailf12cf8.ts.net`; other household members get access through a Tailscale
device share, not an in-app login. It listens on all of the container's interfaces, so it also
answers on the home LAN (and on `http://finance.tijssen-hq.nl`, which points at the Tailscale
address); there is no login, so anyone on the LAN can use it.

systemd units, in `deploy/`:

| Unit | What it does |
| --- | --- |
| `gainr.service` | The app |
| `gainr-deploy.timer` | Every 2 minutes: if `main` moved past the last good deploy and CI passed on it, pull, install what changed, back up and migrate, build, restart, and check `/api/health`. A failed step is retried on the next run; a failed health check rolls back to the last good deploy. The outcome shows on the commit in GitHub as `homecloud/deploy` (ADR 0042) |
| `gainr-refresh.timer` | Daily 04:30 UTC, after Trading 212 posts the night's card payments: prices, Picnic, bank and Trading 212 syncs |
| `gainr-quotes.timer` | Hourly: the live quote of every held asset and its FX rate, at most once an hour each (ADR 0047) |
| `gainr-backup.timer` | Daily: consistent SQLite snapshot, kept 14 days, pushed off-site with rclone |
| `briefr-import.timer` | Every 10 minutes: pull the agents repository and import new or changed reports into briefr |
| `briefr-performance.timer` | Daily 07:00 Amsterdam time, after the price refresh: the performance reports that are due (daily, weekly on Saturday, monthly on the 1st), straight into briefr |
| `briefr-trainr.timer` | Sunday 12:00 Amsterdam time: plan next week's three gym sessions into trainr's planner, with a report in briefr |
| `briefr-context.timer` | Daily 01:30 Amsterdam time, before the agents run: write `context/holdings.md` (tickers and weights), `context/news.md` (each holding's recent headlines) and `context/listr-products.md` (listr's product names, for the home chef) to the agents repository and push them if they changed |

Secrets live in `/etc/gainr/env`, read by the app and the daily jobs. The deploy script doesn't
install units: after changing one, copy it to `/etc/systemd/system/` and run
`systemctl daemon-reload`. A new timer also needs enabling once, e.g.
`systemctl enable --now gainr-quotes.timer`.

#### The deploy's CI gate (one-time)

Without a token the deploy still runs, just without checking CI first. To switch the gate on,
create a fine-grained token on GitHub (Settings → Developer settings → Fine-grained tokens) with
access to this repository only and the permissions **Actions: Read** and **Commit statuses:
Read and write**, then on the server:

```bash
install -m 0600 /dev/null /etc/gainr/deploy.env
echo 'GAINR_DEPLOY_GITHUB_TOKEN=github_pat_…' > /etc/gainr/deploy.env
cp deploy/gainr-deploy.service /etc/systemd/system/ && systemctl daemon-reload
```

A commit that failed CI is not deployed. One that failed its health check after deploying is
rolled back, and isn't tried again until `main` moves on: remove `/var/lib/gainr/failed-commit`
to retry it, or run `GAINR_DEPLOY_SKIP_CI=1 /opt/gainr/deploy/deploy.sh` to deploy without the
check.

#### briefr's agents repository (one-time)

briefr reads the private agents repository through a deploy key that works for that repository only
(ADR 0044). On the server:

```bash
ssh-keygen -t ed25519 -N '' -C homecloud-briefr -f /etc/gainr/agents-deploy-key
chown gainr:gainr /etc/gainr/agents-deploy-key*
cat /etc/gainr/agents-deploy-key.pub   # GitHub: the agents repo → Settings → Deploy keys → Add, tick "Allow write access"
runuser -u gainr -- env GIT_SSH_COMMAND='ssh -i /etc/gainr/agents-deploy-key -o IdentitiesOnly=yes -o UserKnownHostsFile=/var/lib/gainr/known_hosts -o StrictHostKeyChecking=accept-new' \
  git clone git@github.com:casparovici/agents.git /var/lib/gainr/agents
cp deploy/briefr-*.service deploy/briefr-*.timer /etc/systemd/system/ && systemctl daemon-reload
systemctl enable --now briefr-import.timer briefr-context.timer briefr-performance.timer briefr-trainr.timer
```

Write access is for the context export; the import only reads. `journalctl -u briefr-import` lists
any report file it skipped and why.

#### Run as gainr (one-time, when installing the units from 2026-10-14)

The units used to run as root. Before installing the current ones, give the `gainr` user what
it reads and writes:

```bash
useradd --system --home-dir /var/lib/gainr --shell /usr/sbin/nologin gainr
systemctl stop gainr gainr-refresh.timer gainr-backup.timer
chgrp gainr /opt/gainr/backend && chmod g+w /opt/gainr/backend   # the database's -wal/-shm files
chown gainr:gainr /opt/gainr/backend/portfolio.db* && chown -R gainr:gainr /opt/gainr/backend/backups
chgrp gainr /etc/gainr && chmod 0750 /etc/gainr                  # so gainr can reach what's inside
chown root:gainr /etc/gainr/env /etc/gainr/enablebanking.key && chmod 0640 /etc/gainr/env /etc/gainr/enablebanking.key
install -d -o gainr -g gainr /var/lib/gainr
install -o gainr -g gainr -m 0600 /root/.config/rclone/rclone.conf /var/lib/gainr/rclone.conf
cp deploy/*.service deploy/*.timer /etc/systemd/system/ && systemctl daemon-reload
systemctl start gainr gainr-refresh.timer gainr-backup.timer
```

`gainr.service` reads `GAINR_LISTR_ICS_TOKEN` (the public meal-plan feed's token) from `/etc/gainr/env`
like the other secrets; the unit used to carry it inline, so move it across when replacing the unit.

The deploy unit stays root (it runs git, npm and systemctl) and runs migrations as the
database's owner.

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
household, so a few parts (Dutch banks, a home-server deployment) are
specific to that setup; step 7 lists them.

### 1. Install the prerequisites

- **Git**
- **Python 3.11 or newer** (`python3 --version`)
- **Node.js 20 or newer** (`node --version`); to run the frontend tests, 22.22.2, 24.15 or newer

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
- **Language.** The app speaks English and Dutch (Settings > Language); text the server writes
  (agenda titles, notifications, reports, the listr product catalogue) stays in the language it was
  written in. Another language is a dictionary per module in `frontend/src/i18n/messages/`.
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
