import { describe, expect, it } from "vitest";

import { daysUntil, formatCountdown } from "./calendar";

describe("daysUntil", () => {
  it("counts calendar days, across a daylight-saving change", () => {
    expect(daysUntil("2026-10-29", "2026-09-30")).toBe(29);
    expect(daysUntil("2026-10-26", "2026-10-24")).toBe(2); // Europe falls back on 25 Oct
    expect(daysUntil("2026-09-29", "2026-09-30")).toBe(-1);
  });
});

describe("formatCountdown", () => {
  it("gets coarser the further out a date is", () => {
    expect(formatCountdown(0)).toBe("today");
    expect(formatCountdown(1)).toBe("tomorrow");
    expect(formatCountdown(9)).toBe("in 9 days");
    expect(formatCountdown(29)).toBe("in 4 weeks");
    expect(formatCountdown(193)).toBe("in 6 months");
  });
});
