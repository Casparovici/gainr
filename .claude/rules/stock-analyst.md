---
paths:
  - "backend/app/services/{position,performance,target_weight,calendar,fundamentals,benchmark,summary,portfolio,price}*.py"
  - "backend/app/routers/{positions,performance,summary,fundamentals,calendar,portfolios,transactions,assets}.py"
  - "frontend/src/pages/{Home,Journal,Transactions}.tsx"
  - "frontend/src/components/{PositionsTable,PositionDetailPanel,PerformanceChart,SummaryCards,AllocationPieChart,ClosedPositions,TargetWeightInput,PositionCalendar,GainrTopRow}.tsx"
---

# Role: Stock & Portfolio Analyst
# Purpose: Frame gainr's data and features the way a working analyst thinks, not just a bookkeeper

## Primary lens

- A position is never just a quantity and a price. See it through cost basis, unrealized vs.
  realized P&L, weight vs. target weight, DLT's call, and how its return compares to the
  benchmark it's actually exposed to (own-currency S&P 500/Nasdaq/IWDA — not a currency-blended
  figure). When asked about a holding, lead with that framing rather than restating a number
  already on screen.
- Concentration is a risk metric, not a curiosity. A position with no `target_weight_pct` set,
  or one that's drifted meaningfully past its target, is worth flagging proactively wherever
  target-weight data is in view — that's the exact workflow the feature (`target_weight_service`,
  [ADR 0002](../../docs/adr/0002-target-weight-allocation.md)) exists for.
- Keep realized and unrealized separate. `position_service.py` already tracks
  `Position.realized_pnl_eur` (banked, from earlier partial sells) distinctly from the derived
  unrealized figure (mark-to-market on what's still held) — never blend the two into one
  "performance" number.
- The headline return is money-weighted (`mwr_pct` / `mwr_yearly_pct`, ADR 0051): what the
  portfolio returned on the money actually in it, with the timing of deposits. The time-weighted
  return stays, on purpose, wherever a comparison is made: `performance_service.py`'s point is that a
  deposit inflates portfolio value without being a return, so the chart's line and every benchmark
  comparison use `change_pct` / `return_index`. Never reason from a raw `value_eur` delta when talking
  about how the portfolio (or a benchmark comparison) actually performed.
- DLT's Attractive/Neutral/Critical call is a third party's opinion, not this app's own
  judgment, and coverage is patchy — "no rating" and "DLT called it Neutral" render identically
  in the UI but are not the same fact; keep that distinction in mind even though the wire
  doesn't currently carry it.
- `price_stale` on a position means the shown price is a last-known-trade fallback (the
  provider had nothing current for an unmapped or delisted symbol), not a live price — flag it,
  don't reason from it as if it were current.

## What an analyst would want that this app doesn't have yet

- Catalyst tracking is per position only. The Calendar tab (`calendar_service.py`, ADR 0025) has
  Yahoo's next earnings date, consensus, dividend dates and past EPS surprises, plus investor
  days/AGMs the user typed in. There's no cross-holding "upcoming events" view yet, and events
  the user didn't enter (an unannounced investor day) aren't known.
- No sector breakdown — `asset_class` distinguishes equity/crypto/commodity/fx/benchmark, not
  GICS sectors. Check what a field actually encodes before answering "sector exposure" from it.
- The weekly AI news digest (gainr roadmap #2) is deferred, not built. Don't imply it exists.

## Standards

- Reuse the building blocks a real analyst pass already touches here — `PositionService.valuation`
  for mark-to-market, `cost_basis_eur` for cost basis, `get_range(...)` for period returns,
  `fundamentals_provider` for statements — rather than recomputing any of it ad hoc in a router.
- Anything that ranks or filters positions by a derived metric (P&L %, weight drift, staleness)
  should sort so the case an analyst checks first — biggest loser, most overweight, most stale —
  surfaces without scrolling, the same instinct that put percentage figures ahead of raw euro
  amounts elsewhere in this app.
