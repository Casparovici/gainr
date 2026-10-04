# 26. gainr: extra news sources per position (sector, industry or any Yahoo symbol)

## Status

Accepted

## Context

A position's News card showed only its own ticker's Yahoo news. For several holdings that's
little or nothing:

- the gold tracker (4GLD.DE) and the two thematic ETFs (JEDI.PA, GRID.MI) returned no stories at
  all;
- Bitcoin and Ethereum's EUR pairs returned a handful of price-forecast pieces.

The user asked to use yfinance's sector/industry and market classes for these: commodities news
for gold, the cryptocurrencies market for BTC/ETH, aerospace & defense for JEDI, and renewable
utilities plus solar for GRID.

Probing yfinance 1.7.0:

- **`Sector(key)` / `Industry(key)`** each carry a `.ticker` (Yahoo's sector index, e.g.
  `^YH31010010` for Aerospace & Defense) whose `.news` is a live, relevant feed. It returned 10
  current stories for each of the requested industries.
- **There is no "commodities" sector.** `Sector("commodities")` is a 404.
- **`Market("COMMODITIES")` / `Market("CRYPTOCURRENCIES")` have no news.** They return a status
  summary with one arbitrary highlight symbol per exchange: Brent crude and copper for
  commodities, Solana for crypto. Following those would put oil or Solana news on the gold or
  Bitcoin position.
- **The main contract or USD pair is the market-wide feed in practice.** Gold futures (`GC=F`)
  carries gold-price and gold-miner stories, and `BTC-USD`/`ETH-USD` carry Yahoo's broader
  crypto-market coverage.
- **yfinance's bundled catalogue (`SECTOR_INDUSTY_MAPPING_LC`) has a few unusable keys.** Some
  are spelled with an em-dash (`utilities—renewable`), which Yahoo's API rejects in favour of a
  plain hyphen (`utilities-renewable`).

## Decision

**Sources are data on the asset, not code.** `assets.news_sources` holds a JSON list of source
keys:

- `sector:<key>`, e.g. `sector:utilities`
- `industry:<key>`, e.g. `industry:aerospace-defense`
- `ticker:<symbol>`, e.g. `ticker:GC=F`

It's per asset, like the calendar and journal (a source describes the company or instrument,
not a portfolio), and edited from the News card itself: removable chips, plus an add control
listing suggested markets, the 11 sectors and 145 industries, or any Yahoo symbol. The
requested mapping was then set through the API, so changing it later needs no code:

| Position | Sources |
|---|---|
| 4GLD | `ticker:GC=F` |
| BTCEUR | `ticker:BTC-USD` |
| ETHEUR | `ticker:ETH-USD` |
| JEDI | `industry:aerospace-defense` |
| GRID | `industry:utilities-renewable`, `industry:solar` |

**The catalogue is offline.** Keys are derived from yfinance's display names ("Aerospace &
Defense" → `aerospace-defense`), not its lowercase table. All 145 match and were spot-checked
against Yahoo. The market suggestions (gold, silver and crude futures, BTC/ETH USD) are a short
hand-picked list, and any other symbol can be typed in. Validation rejects unknown sector and
industry keys, malformed symbols, and more than six sources.

**Merging.** `FundamentalsProvider.get_source_news(source)` is optional, with a default of none,
so another provider can skip it. `FundamentalsService.get_news` combines the position's own feed
with each source's, newest first, capped at 30:

- A story that also appears in an earlier feed (same URL or title) is kept once, attributed to
  the position itself when it's there.
- The position's own feed is taken as-is, exactly as before.
- Each story carries its source's label, which the card shows as a small tag.

The 3-hour news cache now stores the source list with the items. A cache built from different
sources (or from before this change) is refetched immediately rather than waiting out the TTL.

## Alternatives considered

- **Hard-coding the five mappings by symbol**: faster to write, but every future ETF would need a
  code change, and the user couldn't adjust them.
- **Following `Market(...)` summaries**: it gives the wrong instruments' news (see above).
- **A composite "crypto market" source** (BTC-USD and ETH-USD together): possible later, but the
  single USD pair already carries the broad crypto coverage, and two sources can be added if
  wanted.

## Consequences

- Each extra source is one more Yahoo request per position per 3-hour cache window, and only when
  the position's news is opened. There's no background fetching.
- Sector and industry feeds are broad. JEDI's aerospace-and-defense feed includes stories like
  SpaceX pricing, so the tag makes it visible that a story is about the industry, not the fund.
