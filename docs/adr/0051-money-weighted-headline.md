# 51. gainr: the money-weighted return is the headline performance figure

## Status

Accepted. Changes which figure leads in [ADR 0041](0041-gainr-income-mwr-rebalance.md); the
time-weighted series of [ADR 0001](0001-performance-series-cache.md) is unchanged.

## Context

Home showed the time-weighted return as the performance figure, with the money-weighted return
(XIRR, ADR 0041) in small muted text beside it. They answer different questions. The time-weighted
return measures the investments and ignores when you paid money in, which is why it compares fairly
with a benchmark. The money-weighted return is what the portfolio actually returned on the money that
was in it, timing of the reader's own deposits included. On the real ledger the two were far apart
over the whole history (about 23% a year money-weighted against 34% in total time-weighted), because
the early losses came when little money was in and the later gains when most of it was. The reader
wants the figure that says how their own money did to be the one that leads.

## Decision

**The money-weighted return leads wherever the portfolio's own performance is the point.**

- **The chart's header:** the big number is the money-weighted return for the range, per year once
  the range is a year or longer (`mwr_yearly_pct`; shorter than that, scaling up to a year exaggerates
  it, ADR 0041) and the range's own otherwise (`mwr_pct`). Under it: the change in euros, and the
  time-weighted return, labelled as such.
- **The two tiles under the hero:** "This year" is the money-weighted return for the year so far;
  "Since start" is the money-weighted return per year since the first transaction (the range's own
  while there is less than a year of history), next to the total euros. The simple "total value
  against everything paid in" figure moved into the tile's hint.
- **No rate, no pretence.** For one day, or when no rate exists (money never moved, one day of
  history, no solution in the search bracket), the time-weighted return takes the big number's place
  and is labelled "time-weighted", so a headline is never missing and never mislabelled.
- **The summary carries them:** `GET /api/summary` gains `ytd_mwr_pct`, `total_mwr_pct` and
  `total_mwr_yearly_pct`, taken from the same `performance_service.get_range` the chart uses (YTD and
  Max), so a tile and the chart's header cannot disagree. One more range per summary request: the
  bisection is about 0.15 s for a few hundred flows, and the summary is polled every 15 minutes.
  `headline()` in `utils/performanceHeadline.ts` is the one place that chooses.

**The time-weighted return stays where a comparison is made.** The chart's line is the time-weighted
series, so it stays comparable with the S&P 500, Nasdaq and MSCI World lines and its end point is the
time-weighted figure, not the big number; the header's ⓘ says so. The day's move under the hero
("today") is time-weighted too: a day has no money-weighted rate. The briefr performance reports
(ADR 0045) are periods of a day, a week or a month, against benchmarks, so they stay time-weighted.
The old "returns are time-weighted" rule in `.claude/CLAUDE.md` and the stock-analyst rule now say
which figure is which.

## Alternatives considered

- **Switch the chart's line to money-weighted.** A running money-weighted return is not a series that
  benchmarks can be laid over, and it changes whenever an earlier deposit is edited.
- **Show both at the same size.** That is the status quo with more ink: the reader asked for one
  number to lead.
- **Money-weighted in the briefr reports too.** Over a day or a week the two are nearly the same, and
  a rate per year would mislead; deferred until a longer report asks for it.

## Consequences

- A deposit just before a rise lifts the headline and one just before a fall lowers it, which is the
  point, but the headline is no longer the right figure to put next to a benchmark; the time-weighted
  figure beside it is.
- The headline can end somewhere other than the chart's line. Both are labelled.
