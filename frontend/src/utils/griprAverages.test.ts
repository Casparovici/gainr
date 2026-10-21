import { describe, expect, it } from "vitest";

import { completedPeriodAverage, splitInProgress } from "./griprAverages";

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

describe("splitInProgress", () => {
  it("dashes only the last point, anchored on the one before it", () => {
    expect(splitInProgress([1, 2, 3], true)).toEqual({ solid: [1, 2, null], partial: [null, 2, 3] });
  });

  it("leaves a finished series solid", () => {
    expect(splitInProgress([1, 2, 3], false)).toEqual({ solid: [1, 2, 3], partial: [null, null, null] });
  });

  it("has nothing to anchor a lone point on", () => {
    expect(splitInProgress([5], true)).toEqual({ solid: [5], partial: [null] });
  });
});
