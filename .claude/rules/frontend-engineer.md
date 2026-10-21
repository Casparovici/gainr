---
paths:
  - "frontend/src/**/*.{ts,tsx}"
---

# Role: Frontend Engineer
# Purpose: React dashboard UI

## Stack

- TypeScript, React 18, Vite, Tailwind, Recharts, TanStack Query. Capacitor wraps it for
  Android, so nothing may assume a desktop browser.
- Server calls go through the per-module clients in `src/api/` (`client.ts`, `griprClient.ts`,
  `listrClient.ts`, `gardnrClient.ts`, `trainrClient.ts`) with their `*Types.ts`; don't call `fetch` from a
  component. Server state lives in TanStack Query, not in `useState` copies.
- Pages are per module under `src/pages/`, shared UI in `src/components/ui/`. Formatting of
  money, percentages and dates goes through `src/utils/format.ts`.

## Standards

- Strict TypeScript, no `any`. Types mirror the backend schemas.
- Every widget handles loading, empty and error states.
- Every user-visible string goes through `t()` / `tp()` from `src/i18n/` (module-level labels:
  `msg()`, then `t()` where shown), written in the module's own language, with its translation
  added to that module's file in `src/i18n/messages/`; `i18n.test.ts` fails otherwise. Data
  (names, notes, server text) is never wrapped. See ADR 0049.
- No business logic here: returns, P&L, allocation and balances come from the backend.
- Chart ranges are `1D`, `1M`, `YTD`, `1Y`, `Max`; a position's own price chart uses `1D`, `1W`, `1M`, `YTD`, `3Y` (ADR 0053).
- Pure helpers get Vitest tests next to them; components with logic get a Testing Library test.
  `npm run lint` fails on any warning and `npm run build` typechecks; run both before committing.
