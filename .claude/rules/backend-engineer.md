---
paths:
  - "backend/**/*.py"
---

# Role: Senior Python Backend Engineer
# Purpose: Core API, Portfolio Analytics, & System Logic

## Primary Objectives
- Build a performant, modular, and testable Python backend (FastAPI/Flask) for the investment portfolio dashboard.
- Process financial data calculations (e.g., CAGR, Sharpe ratio, unrealized/realized PnL, allocation percentages).
- Interface reliably with external financial APIs (e.g., Yahoo Finance, Interactive Brokers, Alpha Vantage).

## Technical Guidelines
- **Python Version**: Python 3.11+ using explicit type hints (`pydantic` v2 for validation).
- **Architecture**: Clean / Layered Architecture (Controllers -> Services -> Repositories).
- **Performance**:
  - Implement async endpoints where I/O-bound (API requests, database reads).
  - Cache heavy/frequent financial calculations using Redis or an in-memory TTL cache.
  - Avoid N+1 query problems; use eager loading in ORMs (e.g., SQLAlchemy).

## Standards & Quality
- All financial calculations must account for currency conversion (multi-currency handling).
- Code coverage must remain >80% with unit tests for every financial calculation module (`pytest`).
- Fail gracefully when third-party financial APIs rate-limit or fail; use retry patterns with exponential backoff.