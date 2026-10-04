# 30. gainr: news from Yahoo's RSS headline feed after yfinance's endpoint was retired

## Status

Accepted. Changes how [ADR 0026](0026-news-sources-per-position.md)'s sources are fetched, not
what they are.

## Context

On 2 October 2026 every position's News card was empty. yfinance 1.7.0 (the latest release)
fetches `Ticker.news`, and the `Sector`/`Industry` feeds built on it, by posting to
`finance.yahoo.com/xhr/ncp`. Yahoo now answers that endpoint with a 404 under both of yfinance's
cookie strategies. yfinance turns that into an empty list, and the provider's fail-soft handling
passed it on as "no news this week".

Probing what Yahoo still serves:

- **The RSS headline feed** (`feeds.finance.yahoo.com/rss/2.0/headline?s=<symbol>`) returns
  10–20 current stories for any symbol, including European listings (`ASML.AS`, `RHM.DE`), crypto
  pairs, futures, indices, and sector indices (`^YH311`). Each story has a title, link,
  publication date and usually a description. It has no publisher field. It 404s without a
  User-Agent and returns 429 to a full browser one, but lets a plain identifying one through.
- **Industry indices** (`^YH31010010` and others) return an empty RSS feed.
- **Yahoo's news search** (`yf.Search(query).news`) still works and carries a publisher, but it
  matches text, not symbols. `ASML.AS` or `RHM.DE` return nothing, and `AAPL` returns a broadly
  related NVIDIA story first. For an industry's name ("Aerospace & Defense", "Solar"), though, it
  returns relevant current stories.

## Decision

- A position's own news and `ticker:` sources come from the RSS headline feed for the exact
  symbol.
- `sector:` sources use the same feed for the sector's index symbol, which yfinance's `Sector`
  still resolves.
- `industry:` sources use a news search for the industry's display name.
- The publisher shown for an RSS story is the story's own host (`247wallst.com`), and Yahoo's
  syndicated copies read as "Yahoo Finance". Search results keep the publisher Yahoo gives.
- The news cache records which feed filled it (`NEWS_FEED`). Rows cached empty from the retired
  endpoint are refetched on the next read instead of being served for their 3-hour TTL.

The `FundamentalsProvider` interface doesn't change, so the service and frontend are untouched.

## Consequences

- The feed is an unauthenticated, undocumented Yahoo surface like every other one yfinance uses.
  If it goes the same way, the symptom is the same: an empty card, not an error.
- Industry sources are now text-matched, so they can be broader than the old index feed was.
  The source tag on each story already makes that visible.
- RSS stories have no named publisher, only the site they link to.
- ETFs such as `IWDA.AS` still have no news of their own in either feed. That is what sources
  are for (ADR 0026).
