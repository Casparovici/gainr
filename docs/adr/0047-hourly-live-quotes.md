# 47. gainr: an hourly live quote on top of the daily closes

## Status

Accepted

## Context

gainr valued every holding at its latest daily close. `price_service` fetched each asset at most
once per calendar day (`gainr-refresh.timer`, 04:30 UTC), so during a trading day the Home page
showed yesterday's value, and the chart's 1D change compared yesterday's close with itself. The
provider already returns the latest traded price: `YFinanceProvider.get_last_settled_close` reads
it from Yahoo's chart metadata to repair gaps in the daily feed, but then discards it while the
session is still open.

The goal is a more current value without loading Yahoo heavily, without background workers
(see the software-architect rule), and without mixing intraday prices into the history that
time-weighted returns and benchmark comparisons are built from.

## Decision

**A live quote per asset, refreshed at most once an hour.**

- `PriceProvider.get_quote(symbol)` returns the last trade and its moment (`Quote`). Yahoo's
  version reads `regularMarketPrice`/`regularMarketTime` from the chart metadata, one small request
  per symbol. `get_last_settled_close` is now built on it. A provider without quotes returns
  None, and everything stays on closes.
- **Stored on the asset row, not in `price_history`.** Three nullable columns on `assets`:
  `quote_price` (NUMERIC, in the asset's own currency units, so pence-quoted listings are scaled
  like closes), `quoted_at` (when the trade happened, UTC) and `quote_checked_at` (when we last
  asked, UTC). An intraday price is not a close, so `price_history` stays closes only.
- **At most once an hour.** `price_service.refresh_quote` skips an asset whose
  `quote_checked_at` is less than an hour old, with one minute of slack so an hourly timer firing a
  few seconds early still runs. A failed fetch counts towards the hour and keeps the previous
  quote, so a provider that's down isn't asked again on every run.
- **Fetched by a timer, never by a request.** `scripts/refresh_quotes.py` runs hourly
  (`deploy/gainr-quotes.timer`). It quotes every asset held in any portfolio, each once, plus the
  FX pair of each currency they're priced in. A page load only reads the columns. There is no
  request-path fallback: a missing quote just leaves the close in place.
- **Used only for "now".** `price_service.get_current_price` prefers the live quote when it is
  *current*: refreshed within the last two hours (so one missed run doesn't send the dashboard back
  to yesterday's close) and at least as new as the asset's latest close. Otherwise it returns the
  close. Today's FX rate prefers its live quote in the same way. Position values, weights, P&L and
  the summary use the current price, and each position says when its quote was taken
  (`price_quoted_at`).
- **The chart's today point is re-priced, nothing else.** The cached daily series (ADR 0001) is
  still computed from closes only. `performance_service.get_live_series` takes the cached series
  and re-prices only its last point at the live quotes, chaining that one day's time-weighted
  return again from the day before. It also keeps what the series held on its last day (quantity,
  close, FX rate) so this needs no ledger replay. `get_range` (the chart, 1D, YTD on Home) uses the
  live series. `get_full_series` and the reports built on it (portfolio periods, briefr) stay on
  finished days' closes.
- **The page polls every 15 minutes** (summary, positions, chart), so a new quote shows up soon
  after it lands. That is a local request; it never reaches Yahoo.

## Alternatives considered

- **Fetch quotes in the request path with an in-memory TTL.** No schema change, but the first page
  load of each hour would wait for one Yahoo request per holding, the parallel Home requests
  would race to fetch the same quotes, and a restart would forget them. ADR 0001 moved the daily
  refresh out of the request path for the same reason.
- **Write intraday prices into `price_history` as today's row.** Fewer moving parts, but a
  half-day price would sit in the table that returns are built from, and could only be told apart
  from a real close by timing.
- **Yahoo's streaming websocket, Trading 212's positions endpoint, or a paid vendor.** Each is
  closer to real time. Streaming needs a long-lived connection in the app process, Trading 212
  only covers what is held there, and a vendor needs a key and a subscription. Hourly from the
  provider already in use is enough for a personal dashboard. `get_quote` is the seam if that
  changes.

## Consequences

- During a session the Home page is at most about an hour behind (plus Yahoo's own delay: US
  listings are near real time, most European ones about 15 minutes late), instead of a day.
- About one Yahoo request per held asset and FX pair per hour, around the clock (crypto trades at
  night). The timer runs hourly, so the quotes of closed markets just repeat the close.
- Total value, positions and the chart's today point agree. Earlier days, benchmarks and the
  briefr reports are unchanged.
- A quote is shown only while the hourly refresh is working. Two hours after the last refresh,
  values fall back to the daily close, as before this ADR.
- The quote's day is its UTC date. For an exchange far east of UTC (New Zealand, early in its
  session) that can be a day before the exchange's own date, and that quote then loses to a close
  already stored for that date. Accepted: no such holding today.
