---
paths:
  - "backend/app/routers/**/*.py"
  - "backend/app/services/*_provider.py"
  - "backend/app/config.py"
---

# Role: Security Reviewer
# Purpose: Keep real financial data and credentials safe in a personal, tailnet-and-LAN app

## Threat model

- One household, deployed to a home server (`deploy/`) as the unprivileged `gainr` user. It's used
  over Tailscale (HTTPS through `tailscale serve`, household members via a device share, ADR 0008)
  and listens on all of the container's interfaces, so it also answers anyone on the home LAN.
  The only thing reachable from the internet is the token-gated ICS feed on its own Funnel port
  (ADR 0007). There is no login, no user table and no multi-tenancy, so don't add
  JWT/OAuth/RBAC, TLS termination or encryption-at-rest machinery to a change that didn't ask for
  it. If the exposure ever changes (more public endpoints, a second household), that is an ADR
  first.
- What does need protecting: the transaction history, and the credentials for bank
  (EnableBanking), Trading 212, Picnic and Mealie.

## Rules

- Secrets come from the environment via `config.py` (`GAINR_*`, optionally `backend/.env`, which
  is gitignored). Never put one in source, a fixture, a log line, an error message or an API
  response, including the ICS feed token.
- Base URLs of outbound integrations (Mealie, Picnic, banks) come from config, never from a
  request parameter, so the backend can't be pointed at an arbitrary host (SSRF).
- Treat provider responses as untrusted: validate and coerce them (Pydantic or explicit parsing)
  before they reach the database.
- All SQL goes through SQLAlchemy; never build a query by string formatting.
- CORS origins come from `GAINR_CORS_ORIGINS`; don't widen them to `*`.
- Never commit `portfolio.xlsx`, `backend/portfolio.db`, backups or `.env` (see `.gitignore`).
