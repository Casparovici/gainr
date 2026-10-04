# 25. gainr: a Calendar tab per position — Yahoo's earnings and dividend dates, plus your own

## Status

Accepted

## Context

A holding's important dates (the next quarterly results, dividend dates, an investor day or
capital markets day) weren't anywhere in the app. The user wanted them in the position detail
panel, as their own tab next to Notes.

The question was where the dates come from. Probing yfinance (already the app's data source,
no key) against the user's real holdings showed:

- **US and Dutch stocks** (AMZN, GOOGL, MELI, NOW, NU, ABN): the next earnings date with a
  confirmed/estimated flag, the analyst consensus for EPS and revenue, about five years of
  estimated vs reported EPS, and upcoming ex-dividend and payment dates.
- **A European small cap** (tonies): the calendar still named a date that had already passed as
  "next". A future row in the earnings history had the real one.
- **ETFs, crypto and gold**: nothing.
- **Time of day** (before or after the market): reliable for US listings, where the release
  timestamp is in New York time. For a European listing it's meaningless: ABN AMRO's 07:00 CET
  release comes back as 10:00 or 22:00 New York.
- **Investor days, capital markets days and AGMs**: not in yfinance, and not in the free tiers
  of the usual alternatives (Finnhub, for example, only covers earnings).

## Decision

**Yahoo's dates come from the existing provider, cached like Financials.**
`FundamentalsProvider.get_company_events()` sits next to `get_news`/`get_financials`, so a paid
data vendor later swaps in the same way. Parsing is a pure function, `build_company_events`,
unit-tested with plain values. `calendar_service` caches the result per asset for a day in
`asset_snapshots` (kind `calendar`). It stores the data raw and filters it against today on the
way out, since a cached "upcoming" date becomes a past one without anything being re-fetched.
Rules applied on read:

- **Next earnings** is the first calendar date on or after today. When the calendar only has a
  past date, the first future row from the earnings history is used instead, always marked
  "estimated" and without the consensus figures, since those belonged to the stale entry.
- **Two calendar dates** mean a window, not a day, so the event is marked estimated and shows
  both ends.
- **Time of day** is only given for listings whose exchange time zone is America/New_York
  (16:00 or later = after close, before 09:30 = before open).
- **Dividend dates** are shown only when they're still ahead. MELI's calendar still carries a
  2017 dividend.
- **Past results**: the last eight reported quarters. Each shows expected vs actual EPS and the
  surprise, (actual − estimate) / |estimate|, which the UI labels beat, miss, or in line (within
  0.5%). They're in the company's reporting currency, never converted, same as Financials.

**Everything else is entered by hand, in a `position_events` table**: asset, date, kind
(investor day, capital markets day, AGM, product event, other), title and notes. It's per asset,
not per portfolio, like journal notes, because a date belongs to the company wherever it's held.
Your own events are the only editable ones, and the only way to put anything on an ETF's
calendar. Past own events stay visible for a year.

**API**: `GET /api/assets/{id}/calendar` returns `{currency, upcoming, past, results}`, with each
event marked `source: yahoo | manual`. `POST/PUT/DELETE /api/assets/{id}/events[/{event_id}]`
handle your own events, scoped to that asset (404 otherwise).

**UI**: a Calendar tab after Notes, hidden on the Cash row. Upcoming events come first, each with
a date block, timing, consensus and a countdown ("in 4 weeks"). Past results follow, with beats
and misses in the app's gain/loss colours, then your past events. The Overview tab gains one
"Next: Earnings · 29 Oct — in 4 weeks" line, which is empty when nothing is coming up.

## Alternatives considered

- **A paid calendar API** (with investor days or confirmed release times): a key and a cost for a
  single-user app, when the gap it fills (a handful of investor days a year) is easy to type in.
  The provider interface leaves that door open.
- **Scraping companies' investor relations pages**: a different page layout per company, broken
  by every redesign.
- **Fetching events for every holding in the daily price-refresh job**: it would make a future
  "upcoming across all holdings" view instant. But it's a Yahoo call per asset per day even when
  nobody looks, and the per-position tab doesn't need it. It can be added when that view is.

## Consequences

- Opening a position's Overview now also asks for its calendar, for the "Next:" line. That's one
  Yahoo lookup per asset per day at most, then cached, the same cost as opening Financials.
- Not built yet: an upcoming-events list across all holdings, and an ICS feed so events appear in
  a phone calendar (listr's meal-plan feed, ADR 0007, is the pattern to follow).
