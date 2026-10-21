---
paths:
  - "backend/**/*.py"
---

# Role: Backend Engineer
# Purpose: API, services and calculation code

## Stack

- Python 3.11+, FastAPI, SQLAlchemy 2.0 (sync sessions), Pydantic v2 schemas in `app/schemas/`,
  SQLite. Endpoints are plain `def`: the work is blocking DB and `yfinance` calls, so don't
  introduce `async def` unless the code awaits something.
- Layers: `routers/` parse and validate and call a service; `services/` hold the logic;
  `repositories/` hold all queries; `models/` hold the tables. Never query from a router. A
  router may fetch the row its path names through a repository (and 404 when it's missing) or
  save a plain field update; anything with a rule in it (validation across rows, defaults,
  several writes) is a service function.
- Services don't raise `HTTPException`: they raise `NotFound`, `InvalidRequest` or `Conflict` from
  `app/services/errors.py`, and the router wraps the call in `with domain_errors():`
  (`app/routers/errors.py`) to answer 404/400/409.
- Money is `Decimal`, never `float`, and carries a currency. Convert with the FX rate of the
  transaction's own date.
- Avoid N+1 queries: use `selectinload`/`joinedload` where a list endpoint touches relations.
- Caching is a DB table (`price_history`, refreshed at most once per day per asset) or, for the
  performance series, an in-memory cache (ADR 0001). Don't add Redis or a TTL library.

## Quality

- New calculation code ships with `pytest` tests in `backend/tests/`; keep that module > 80%.
  Run `pytest` from `backend/` before committing.
- Providers can be down or rate-limited: degrade (serve the cached value and flag it, e.g.
  `price_stale`) rather than failing the whole dashboard request.
- Keep the module prefix on new files (`gripr_*`, `listr_*`, `gardnr`, `trainr_*`); gainr stays unprefixed.
