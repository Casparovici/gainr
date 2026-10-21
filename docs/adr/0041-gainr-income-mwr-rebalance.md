# 41. gainr: dividend income, a money-weighted return and a rebalance helper, all derived

## Status

Accepted

## Context

A pass over the whole app found three things an investor would expect in gainr that it lacked
(gainr roadmap 6–8):

- **Dividend income.** Dividends were booked, but nothing showed what they add up to per month or
  year, or what the holdings can be expected to pay.
- **A money-weighted return.** Returns are time-weighted (ADR 0001), so they compare fairly with a
  benchmark, but that leaves out the timing of your own deposits.
- **A rebalance helper.** Target weights existed (ADR 0002), but turning "€500 to invest" into
  what to buy was left to mental arithmetic.

## Decisions

**All three are derived on every request, from the ledger and the positions.** There are no new
tables, nothing is stored, and there's no new data provider. Each one's arithmetic is a pure
module with no framework or database: `money_weighted_return.py`, `dividend_income.py` and
`rebalance.py`. A thin service joins it with the data (`performance_service`, `dividend_service`,
`rebalance_service`).

**Money-weighted return (XIRR) rides along with each chart range.** `GET /api/performance` gains
`mwr_pct` and `mwr_yearly_pct`.

- The cash flows are the range's start value (money in), every deposit and withdrawal after the
  start day (`_external_flows`, the same rows the change in euros already nets out), and the end
  value (money out). This is the same convention the time-weighted figure uses, so the two sit
  side by side for the same range.
- The rate is found by bisection in `Decimal`: about 0.15 s for a few hundred flows. A float
  solver would have been faster, but the rest of the money arithmetic stays `Decimal`, and this is
  fast enough.
- `mwr_pct` is the rate compounded over the range's length, so a YTD figure reads like the YTD
  time-weighted one. `mwr_yearly_pct` is only given for ranges of a year or more, because scaling a
  few weeks up to a year exaggerates it. 1D has neither.
- The chart header shows it next to the time-weighted change, and the ⓘ explains the difference.
  On the real ledger, Max came out at about 23% a year money-weighted against 34% time-weighted in
  total. The early losses fell when little money was in, the later gains when most of it was.
  That gap is exactly what the figure is for.

**Dividend income repeats the last 12 months.** `GET /api/income/dividends` feeds a new Income page.

- **Received:** dividends per month, year and holding, as booked (`total_eur`, after withholding
  tax, at the day's FX rate).
- **Expected:** each dividend in the last 365 days becomes an amount per share held on its
  payment day, times the shares held now, placed a year later. On a day with both a dividend and
  a trade, the dividend counts first, because it was earned on the shares held before. This needs
  no provider and works for every holding with a payment history. It doesn't know about a holding
  bought since its last payment, or about a raise or cut until the next payment, and the page's ⓘ
  says so.
  - Yahoo's forward dividend rate was the alternative: one more slow per-asset scrape, in native
    currency, with patchy coverage of ETFs and European listings. It could refine the estimate
    later; the ledger stays the baseline.
- **Yields:** the expected amount over market value (current yield) and over cost basis (yield on
  cost), per holding and over all open holdings.

**The rebalance helper only buys.** `GET /api/positions/rebalance?amount_eur=&from_cash=` plans
from the positions table's own values and targets.

- Each targeted holding (and cash, when cash has a target) is short of its target by
  `target % × total after the money − value now`. The amount is split over the holdings that are
  short, in proportion to how far each is short. Anything left once every shortfall is covered is
  spread by target.
- Amounts are whole cents; the rounding cents go to the largest purchase.
- Holdings over target get nothing and are named. Holdings without a target count towards the
  total, get nothing, and are named too.
- New money grows the total by the amount. With `from_cash`, the total stays the same, cash
  shrinks by the amount, and none of it goes back to cash. Asking for more than the cash there is
  is a 400.
- The quantity shown is `amount / (market value / quantity)`, which is approximate: prices move
  and brokers round.
- Alternatives:
  - "Fill the furthest behind first" (water-filling) would close the biggest gap faster, but it
    is harder to explain in one sentence.
  - Selling overweight holdings to rebalance fully means taxes, costs and a decision the user
    hasn't asked the app to make.

## Consequences

- No migration, no new provider, and no change to the caching approach.
- The Income page is a fourth gainr page: Home, Transactions, Income, Journal.
- `money_weighted_return`, `dividend_income` and `rebalance` are pure and tested on their own;
  the services are tested through the database like the rest of gainr.

## Addendum (2026-10-18): the rebalance helper buys only what DLT rates Attractive or Neutral

The user asked for the helper to stick to holdings DLT rates Attractive or Neutral, and to show
the rating with each purchase.

- **Who can receive money:** only a holding rated Attractive or Neutral, with a target. Cash has
  no rating and keeps its target, so a deposit can still top up a cash buffer that's below it.
- **Who is left out:** a holding rated Critical, or not rated at all, gets nothing, the same as one
  without a target. The rating decides first, so a Critical holding is listed as Critical whether
  or not it has a target. Left-out holdings still count towards the total, so every weight stays a
  share of the whole portfolio. Their targets aren't handed to the others: an eligible holding is
  only short of its own target.
- **Unrated is not Neutral here.** The positions table shows a holding with no rating as Neutral,
  meaning no reason to act (the analyst note on that distinction still stands). The helper would
  be buying on that call, so it treats unrated as left out and labels it "No rating".
- **API:** `RebalancePurchaseOut` carries `dlt_judgment`. `untargeted` became `left_out`, a list of
  `{name, dlt_judgment, reason}` with the reason `critical`, `unrated` or `no_target`. The dialog
  groups the left-out holdings by that reason.
