import { describe, expect, it } from "vitest";

import { cappedRange, clampTo } from "./chartScale";

// Overview's money put aside: twelve months of investments, savings and reservations, with the
// month €35k of home equity went into savings and the month part of it went out again.
const MONTHS = [
  685, 551, 2055, 891, 994, 1661, 1261, 691, 961, 1691, 1091, 671,
  -1490, -559, 1644, -793, 344, 2255, 1487, 982, -3025, 35331, -13251, -2429,
  19, 386, -119, 115, 178, -498, 315, -2146, -675, 71, 315, 315,
];

describe("cappedRange", () => {
  it("leaves the one-off months out of the scale, keeping every ordinary month in it", () => {
    const range = cappedRange(MONTHS)!;

    expect(range.max).toBeLessThan(35331);
    expect(range.min).toBeGreaterThan(-13251);
    expect(range.max).toBeGreaterThan(2255);
    expect(range.min).toBeLessThan(-3025);
  });

  it("keeps the chart's own scale when nothing is that far out", () => {
    expect(cappedRange([100, 200, 150, 300, 250, -50])).toBeNull();
    expect(cappedRange([5, 6])).toBeNull();
  });

  it("clamps a value to the range, and leaves it alone without one", () => {
    expect(clampTo(35331, { min: -3500, max: 2500 })).toBe(2500);
    expect(clampTo(-13251, { min: -3500, max: 2500 })).toBe(-3500);
    expect(clampTo(400, null)).toBe(400);
  });
});
