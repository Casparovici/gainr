# 45. briefr: performance reports are computed on the server, not written by a model

## Status

Accepted. Builds on [ADR 0044](0044-briefr-agent-reports.md).

## Context

The owner wants a daily, weekly and monthly report on how the gainr portfolios did: each
holding's price change, what it contributed to the portfolio, and whatever else matters over the
period, delivered in briefr next to the other agents' reports.

The other agents (the holdings scan, the app builder) are language models running in the cloud.
They read the web and write prose, and they work from `context/holdings.md`, which deliberately
holds weights only: no amounts leave the server (ADR 0044). A performance report is the opposite
kind of work. It's arithmetic on the ledger, it's mostly euro amounts, and it has to be exactly
right.

## Decisions

**The performance "agent" is a job on the server, not a model.** `scripts/briefr_performance.py`
runs every morning at 07:00 Amsterdam time from `briefr-performance.timer`, after the 04:30 UTC
price refresh. It computes the figures from gainr's own ledger and price cache and writes the
report straight into briefr's tables, as agent `portfolio-performance`. That gives four things a
model wouldn't:

- **Exact figures:** `Decimal` throughout, the same valuation rules as the performance chart, and
  tested to the cent.
- **Private amounts:** they never leave the server, so the line drawn in ADR 0044 holds.
- **Reliability:** it costs nothing and needs no network beyond the price refresh, so it runs
  every day.
- **A clear split:** the holdings scan already explains why things moved. This report says how
  much they moved and what that did to the portfolio. Together they answer both questions,
  without one guessing at the other's job.

**Writing into briefr directly doesn't reopen what ADR 0044 closed.** That ADR kept reports
coming in through files, so nothing from outside could put text in the app. This report is
written by the app's own code, on the server, about the app's own data. It uses a key of its own,
`server/portfolio-performance/<period>/<end date>`, in place of a file path.
`briefr_report_service.save_generated_report` hashes the content without the run time, so
re-running a period changes nothing and leaves a report you've already read marked read.

**Periods run from close to close**, in the owner's calendar (Europe/Amsterdam):

| Report | Runs on | Covers |
|---|---|---|
| Daily | Tuesday to Saturday | the last weekday, from the close of the weekday before (Monday's report includes the weekend, which matters for crypto) |
| Weekly | Saturday | Friday's close against the previous Friday's |
| Monthly | the 1st | the last day of the month against the last day of the month before |

**What a report says, per portfolio** (each portfolio that isn't archived and had money in it, the
largest first):

- **Return:** time-weighted, from the same series as the Home chart (`performance_service`), so
  deposits don't count as performance. Next to it, the change in euros and the value at both
  ends with the net deposits.
- **Benchmarks:** S&P 500, Nasdaq and MSCI World over the same days, in their own currency, as on
  the chart.
- **Per holding:** the price change in its own currency (the number the market quotes), and its
  **contribution**: value at the end, minus value at the start, minus what was spent buying it,
  plus what selling it brought in, plus its dividends. The contribution is given in euros and in
  percentage points of the start value. Contributions plus interest minus fees add up exactly to
  the portfolio's change; a test holds them to that.
  Only positions still held at the period's end are listed (addendum 2026-10-19): one sold out
  during the period, or a closed one paying a late dividend, is left out of the tables, findings
  and summary, though the portfolio's return, change, dividends and sells still count it. So in
  a period with a sell-out, the listed contributions no longer add up to the change.
- **Also:** dividends, interest, fees, and the number of buys and sells. For the weekly and
  monthly reports, the best and worst day, and the holdings without a target weight.
- **Layout:** the daily report lists the three biggest contributors and detractors. The weekly
  and monthly reports list every holding, detractors first with the worst at the top, as the
  stock-analyst rule asks.

**Findings, which make a report "watch"**, link to the position:

- a price move of at least 5% (daily), 10% (weekly) or 15% (monthly);
- a holding valued at its last transaction price because it has no close (stale);
- in the weekly and monthly reports only, a weight 5 percentage points or more from its target.

**The calculation is gainr's, and pure.** `portfolio_period.py` replays the ledger against price
and FX lookups it's handed, with no database. `portfolio_period_service.py` feeds it from the
price cache and adds the time-weighted return and the benchmarks. briefr's
`briefr_performance_service.py` only chooses the periods and words the report. Anything else that
wants period figures later asks gainr's service, not briefr's.

## Alternatives considered

- **A cloud agent with a brief, like the others:** it would need the amounts, which would mean
  committing them to GitHub. And arithmetic done by a model is checked by nobody.
- **A model writing a narrative over figures the server computes:** possible later, as a separate
  step (e.g. the holdings scan reading the week's figures in percentages only). It isn't needed
  for the numbers themselves, which are the ask.
- **One report per portfolio:** three reports every morning (Main, Kids, Auto) is noise. One
  report per period, with a section per portfolio, reads in one go.
- **A modified-Dietz or time-weighted return per holding:** more exact when a holding is bought
  or sold mid-period, but harder to read, and the contributions would no longer add up to the
  portfolio's change. Euro contribution, and its share of the start value, is what the owner
  asked for.

## Consequences

- Two to four reports a week land in briefr: daily from Tuesday to Saturday, weekly on Saturday,
  monthly on the 1st. They're filterable under the agent "Portfolio performance".
- A period's report reflects the ledger at the moment it runs. A transaction entered later for a
  past day changes the figures only when the period is re-run by hand
  (`python -m scripts.briefr_performance --date … --period …`).
- The weekly and monthly "watch" for drift repeats as long as a holding stays off target. That's
  intended: it's a standing reminder, on the cadence where acting on it makes sense.

## Addendum (2026-10-19): one report per portfolio

The owner asked for the portfolios to be reported on separately rather than as sections of one
report. Each period now writes **one report per portfolio** that isn't archived and had money in
it, keyed `server/portfolio-performance/<period>/<end date>/portfolio-<id>`. The key uses the id,
not the name, so renaming a portfolio updates its reports instead of starting new ones. Each
report's title names its portfolio ("Week 42 (12 Oct – 16 Oct) · Main: +3.50%"), and its
findings no longer add "in <portfolio>". The benchmarks are repeated in every report, so each one
reads on its own.

That reverses the "one report per period" choice above. What it gains: each portfolio can be read,
marked and archived on its own, and a quiet portfolio shows up as an Info report of its own
instead of hiding under the busy one's Watch. What it costs: two to four reports a week per
portfolio instead of in total.

Reports written before this change keep their old key. A period re-run by hand writes the new
per-portfolio reports next to the old combined one, which can be archived.

