import { describe, expect, it } from "vitest";

import { headline } from "./performanceHeadline";

describe("headline", () => {
  it("leads with the money-weighted return per year when there is one", () => {
    expect(headline({ mwr: "34.1", mwrYearly: "12.3", twr: "30" })).toEqual({ pct: "12.3", perYear: true, moneyWeighted: true });
  });

  it("uses the range's own money-weighted return when it is shorter than a year", () => {
    expect(headline({ mwr: "4.2", mwrYearly: null, twr: "5" })).toEqual({ pct: "4.2", perYear: false, moneyWeighted: true });
    expect(headline({ mwr: "4.2", twr: "5" }).perYear).toBe(false);
  });

  it("falls back to the time-weighted return when no money-weighted rate exists, and says so", () => {
    expect(headline({ mwr: null, mwrYearly: null, twr: "0.74" })).toEqual({ pct: "0.74", perYear: false, moneyWeighted: false });
  });

  it("has nothing to show when there is no return at all", () => {
    expect(headline({ mwr: null, twr: null })).toEqual({ pct: null, perYear: false, moneyWeighted: false });
  });
});
