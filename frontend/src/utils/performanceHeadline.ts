// Which return is the headline of a performance figure. The portfolio's headline is money-weighted
// (XIRR, docs/adr/0051): what it returned on the money actually in it, with the timing of your own
// deposits in it. The time-weighted return stays next to it and as the chart's line, because it is
// the one that compares fairly with a benchmark.

export interface Headline {
  /** The percentage to show large; null when no return can be given at all. */
  pct: string | null;
  /** Whether it is a yearly rate (a range of a year or longer) rather than the range's own return. */
  perYear: boolean;
  /** False when it fell back to the time-weighted return, because no money-weighted rate exists
   * (a day, no money moved). The label then says so. */
  moneyWeighted: boolean;
}

/** The money-weighted return -- per year when there is one, else the range's own -- or, when there
 * is no such rate, the time-weighted return in its place. */
export function headline(figures: { mwr: string | null; mwrYearly?: string | null; twr: string | null }): Headline {
  const yearly = figures.mwrYearly ?? null;
  if (yearly !== null) return { pct: yearly, perYear: true, moneyWeighted: true };
  if (figures.mwr !== null) return { pct: figures.mwr, perYear: false, moneyWeighted: true };
  return { pct: figures.twr, perYear: false, moneyWeighted: false };
}
