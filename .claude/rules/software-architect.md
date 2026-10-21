# Role: Software Architect
# Purpose: Module boundaries and structural decisions

## Shape of the system

- A modular monolith: one FastAPI process serves the API and the built SPA, over one SQLite
  database. gainr (portfolio), gripr (personal finance), listr (shopping/meals), gardnr
  (garden), trainr (workouts), taskr (agenda), briefr (agent reports) and notr (notes) are modules in the
  same codebase. Files of every module but gainr carry its prefix; gainr's are unprefixed.
- Layers: routers → services → repositories → models. No business logic in routers or the
  frontend; no framework imports in pure calculation code.
- External systems (Yahoo/yfinance, Trading 212, EnableBanking, Picnic, Mealie) sit behind a
  `*_provider.py` adapter, so a service never knows which vendor it talks to.
- Background work is a script in `backend/scripts/` run by a systemd timer from `deploy/`. There
  is no queue, worker or Redis, and none should be added without an ADR.

## Decisions

- A change to the schema, the caching approach or a data provider gets an ADR in `docs/adr/`
  (numbered, with a row added to its README). Prefer a small addendum to an existing ADR over a
  new one when the decision only changed.
- When one module needs another's data (gripr's portfolio link reads gainr), go through its
  services and repositories, never router to router. Reject a circular import between services.
- Do not add infrastructure (auth, queues, metrics stacks, a second database) the app doesn't
  need. It is a personal app on a home server; `/api/health` is enough observability.
