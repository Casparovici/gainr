# gainr — investment portfolio dashboard

Personal portfolio dashboard, local and single-user. Transactions are seeded from an Excel
export (`portfolio.xlsx`, gitignored); the app derives performance, allocation and
per-position metrics from that ledger.

## Architecture at a glance

- `backend/` — Python 3.11+, FastAPI + SQLAlchemy 2.0, layered routers → services →
  repositories → models. Owns every financial calculation and the price-feed integration
  (`yfinance`, no API key).
- `backend/alembic/` — migrations. There is no separate `db/` directory.
- `frontend/` — TypeScript, React + **Vite** (not Next.js), Tailwind, Recharts,
  TanStack Query. Owns the dashboard UI and charts.
- **SQLite**, not Postgres: this runs locally for one person. `DATABASE_URL` comes from
  `GAINR_DATABASE_URL` or defaults to `backend/portfolio.db`, so swapping to Postgres later
  is a connection-string change rather than a rewrite.
- ADRs live in `docs/adr/` (numbered, e.g. `0001-performance-series-cache.md`).

Detailed standards per layer live in `.claude/rules/` and load automatically when Claude
touches matching files — this file holds only what should be true in every session.

## Rules in this repo

| Rule | Loads when |
|---|---|
| `software-architect` | always — structural decisions aren't tied to a path |
| `backend-engineer` | `backend/**/*.py` |
| `data-modeller` | models, schemas, migrations |
| `frontend-engineer` | `frontend/src/**/*.{ts,tsx}` |
| `ux-designer` | `frontend/src/**/*.{ts,tsx}` |
| `security-engineer` | routers, price/logo providers, `config.py` |
| `stock-analyst` | gainr positions/performance/fundamentals — backend or frontend |
| `personal-finance-specialist` | anything under gripr — backend or frontend |

They load on their own — there's no need to invoke them by name, and more than one applies
to plenty of changes (a new endpoint is both `backend-engineer` and `security-engineer`).

## Non-negotiables

- Currency and unit values: `Decimal` in Python, `NUMERIC` in SQL. Never `float`.
- Every money-bearing value carries a currency. Base currency is EUR throughout; conversions
  use point-in-time FX rates, never one "current rate" applied to history.
- Positions and cash are **derived from the transaction ledger on every request**, never
  stored, so the Home page can't drift out of sync with the ledger. Every gainr transaction
  belongs to exactly one portfolio; nothing sums across portfolios implicitly (see ADR 0019).
- New financial-calculation code ships with `pytest` tests; keep that module above 80%.
- Frontend: no `any`. Every widget handles loading, empty and error states.
- Never commit `portfolio.xlsx` or `backend/portfolio.db` — they hold a real transaction
  history and are gitignored.

## Commands

```bash
# backend (from backend/, with .venv activated)
source .venv/bin/activate
pytest                                        # tests
alembic upgrade head                          # migrations
uvicorn app.main:app --port 8000 --reload     # dev server; --reload matters, routes are
                                              # added often and a stale process 404s them
python -m scripts.import_transactions ../portfolio.xlsx   # re-seed from the sheet (idempotent)
                                              # into the "Main" portfolio; --portfolio NAME
                                              # imports into (or creates) a different one

# frontend (from frontend/)
npm run dev        # dev server on :5173, proxies /api to :8000
npm run build      # production build (also typechecks)
npm run lint       # ESLint (TypeScript + React hooks rules); CI fails on any warning
npm test           # Vitest — pure utils + React Testing Library component tests
npm run test:watch
```

## What the app actually offers

- Multiple portfolios (e.g. "Main", "Kids"), switched via a header pill — every gainr endpoint
  that reads/writes ledger data takes a `portfolio_id`. Assets (ticker, price/logo cache) are
  shared across portfolios; target weights and cash settings are per-portfolio. See ADR 0019.
- Chart ranges: `1D`, `1M`, `YTD`, `1Y`, `Max`. Returns are time-weighted.
- Benchmark overlays: S&P 500 (`^GSPC`), Nasdaq Composite (`^IXIC`), iShares MSCI World
  (`IWDA.AS`) — in their own currency, so they exclude EUR exchange-rate effects.
- Per-position: allocation %, average cost (GAK), unrealized and realized P&L, and a detail
  card with company news, quarterly/annual financials, and a calendar (upcoming earnings and
  dividend dates from Yahoo, past EPS beat/miss, plus user-entered events).
- Prices are daily closes from Yahoo Finance, cached in `price_history` and refreshed at most
  once per calendar day per asset.

## Conventions

- Respect the layer boundaries above: no business logic in the frontend, no framework code in
  the domain layer.
- Anything that changes the schema, the caching approach or the data provider deserves an ADR.
- No secrets in source. There are none today — yfinance needs no key — so if that changes,
  read from the environment and keep it out of git.
- Every change ships with its documentation, in the same commit as the code:
  - `CHANGELOG.md` — one line for anything a user of the app would notice, under today's date
    (`## YYYY-MM-DD`, created if missing; there's no "Unreleased": every push to `main` is
    deployed). New capability under **Added**, existing behaviour working differently under
    **Changed**, something that was wrong under **Fixed**. Start with the module (`gripr: …`)
    and say what changed for the user, not which files moved; detail belongs in an ADR. An
    internal refactor with no visible effect needs none.
  - `README.md` — update it when the change alters how the app behaves, what it shows, or how
    it's run, so the two never disagree.
