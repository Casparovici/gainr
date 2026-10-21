# 53. gainr: a price chart per position, with intraday prices fetched on demand

## Status

Accepted. Builds on [ADR 0001](0001-performance-series-cache.md) (in-memory cache) and
[ADR 0047](0047-hourly-live-quote.md) (live quote on top of closes).

## Context

A position's detail showed its numbers but not how its price got there (issue #87). The reader wants
the price over 1 day, 1 week, 1 month, year to date and 3 years. Daily closes are already stored
(`price_history`), but the one-day view needs prices within the day, which nothing stores: ADR 0047
keeps one live quote per asset and deliberately keeps intraday prices out of `price_history`.

## Decision

**One read endpoint, `GET /api/assets/{id}/prices?range=1D|1W|1M|YTD|3Y`,** served by
`price_chart_service`. It returns the points, the currency, whether they are `intraday` or `daily`,
and the change over the range (start and end price, absolute and percentage).

- **1W, 1M, YTD and 3Y are daily closes** from `price_history`, in the asset's own currency and
  scaled like every other price (pence-quoted listings). Missing history is backfilled through
  `ensure_history`, as the performance series already does in the request path. When the live quote
  of ADR 0047 is current and newer than the last close, it is added as today's point, so the chart
  ends on the same price as the rest of the page.
- **1D is intraday:** `PriceProvider.get_intraday(symbol)` returns the 15-minute bars of the last
  trading session (Yahoo, `period=5d`, only the bars of the last bar's exchange-local date), and the
  change is measured against the close before that session. A provider without intraday returns
  nothing.
- **Intraday is never stored.** It is fetched when the chart is opened and held in a process-local
  cache for 10 minutes per symbol, failures and empty answers included, so a flaky provider is asked
  once per ten minutes, not once per click. This follows ADR 0001's precedent of an in-memory cache
  and keeps `price_history` closes-only.
- **No intraday, no empty chart:** if the bars are unavailable (provider down, market closed for a
  long time, no symbol), 1D falls back to the last seven days of closes and says so
  (`is_fallback`), and the page labels it "over 1W".

## Alternatives considered

- **Store the bars** in a table. More data and a retention question for a view used occasionally;
  the cache makes the provider call rare enough.
- **Have the hourly quotes timer collect them** (ADR 0047). It would give hourly resolution at best
  and grow the timer's work for every held asset; the chart only needs the one asset being viewed.
- **A charting widget from the provider** (TradingView). A second price source that could disagree
  with the rest of the page, and an external script.

## Consequences

- This is the one place a page load calls the provider for prices: opening 1D can make one Yahoo
  request per asset per ten minutes. ADR 0047's "no request-path provider call" concerned the
  Home page's quotes and still holds there; a failed call here only costs the intraday view.
- The cache is per process and is lost on restart, which is fine for ten minutes of data.
- Intraday points are in the asset's own currency; nothing here is converted or summed.
