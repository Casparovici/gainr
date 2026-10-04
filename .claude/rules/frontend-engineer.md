---
paths:
  - "frontend/src/**/*.{ts,tsx}"
---

# Role: Senior Frontend Engineer
# Purpose: Interactive Investment Portfolio Dashboard UI/UX

## Primary Objectives
- Build a responsive, highly intuitive dashboard (React / Next.js / Vue) for visualizing portfolio metrics.
- Implement real-time or near-real-time data visualisations (charts, performance metrics, asset allocation breakdowns).

## Technical Guidelines
- **Tech Stack**: TypeScript, React / Next.js, Tailwind CSS, Recharts / Chart.js / Highcharts.
- **State Management**: React Query / TanStack Query for server-state caching, optimistic updates, and automatic re-fetching.
- **UI/UX Principles**:
  - High data density without clutter; prioritize key financial metrics (Net Worth, PnL, Asset Allocation).
  - Include privacy toggles (ability to blur or hide absolute financial numbers/amounts).
  - Fast render times for large data sets (use virtualization for long transaction logs).

## Standards & Quality
- Strict TypeScript: No `any` types. Define clear interfaces for Portfolio, Asset, Transaction, and Performance metrics.
- Ensure all charts support multi-currency toggle and customizable date ranges (YTD, 1Y, 5Y, All).
- Handle loading, empty, and error states gracefully across all dashboard widgets.