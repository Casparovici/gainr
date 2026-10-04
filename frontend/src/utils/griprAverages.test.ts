import { describe, expect, it } from "vitest";

import { completedPeriodAverage } from "./griprAverages";

describe("completedPeriodAverage", () => {
  it("leaves out the period still in progress", () => {
    expect(completedPeriodAverage([100, 200, 300, 10], true)).toEqual({ average: 200, count: 3 });
  });

  it("uses every period when the last one is complete", () => {
    expect(completedPeriodAverage([100, 200, 300, 400], false)).toEqual({ average: 250, count: 4 });
  });

  it("has nothing to average with no complete period", () => {
    expect(completedPeriodAverage([50], true)).toBeNull();
    expect(completedPeriodAverage([], false)).toBeNull();
  });
});
