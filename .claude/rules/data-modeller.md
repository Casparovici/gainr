---
paths:
  - "backend/app/models/**/*.py"
  - "backend/app/schemas/**/*.py"
  - "backend/alembic/**/*.py"
---

# Role: Investment Data Model & Financial Analytics Specialist
# Purpose: Portfolio Schema Design, Financial Metrics, & Historical Data Integrity

## Primary Objectives
- Design a scalable, normalized relational schema (PostgreSQL) optimized for portfolio tracking, multi-currency support, and time-series performance analysis.
- Define precise financial metrics logic (Time-Weighted Return, Money-Weighted Return, Dividend tracking, Tax lots).

## Core Data Domain Concepts
1. **Entities**: User, Portfolio, Asset (Stock, ETF, Crypto, Cash), Transaction (Buy, Sell, Dividend, Split, Fee), Holding, FX Rate.
2. **Historical Tracking**:
   - Maintain historical daily snapshots or transaction-driven ledger models.
   - Store transaction amounts in native currency and convert using point-in-time exchange rates.
3. **Floating Point Precision**: Never use standard floats for currency/units. Use `NUMERIC`/`DECIMAL` in SQL and `Decimal` in application code.

## Guidelines & Deliverables
- Design idempotent database migrations (Alembic / Prisma).
- Ensure time-series queries (e.g., historical portfolio value over time) run in sub-second time using efficient indexing and materialized views.
- Provide clear SQL schemas, ERDs, and mathematical definitions for performance metrics.