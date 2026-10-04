import { describe, expect, it } from "vitest";
import { currentPeriodStart, periodBounds, periodLabel, periodNumber, periodTitle, shiftPeriod } from "./griprPeriod";

// These scenarios mirror backend/tests/test_gripr_period_service.py exactly, so a change that
// makes the two implementations disagree fails here too, not just silently in production.

describe("periodBounds", () => {
  it("at startDay 1, matches the plain calendar month", () => {
    expect(periodBounds("2026-01-01", 1)).toEqual({ start: "2026-01-01", end: "2026-01-31" });
    expect(periodBounds("2026-01-31", 1)).toEqual({ start: "2026-01-01", end: "2026-01-31" });
    expect(periodBounds("2026-02-15", 1)).toEqual({ start: "2026-02-01", end: "2026-02-28" });
    expect(periodBounds("2024-02-29", 1)).toEqual({ start: "2024-02-01", end: "2024-02-29" });
  });

  it("a reference date before startDay falls in the previous period", () => {
    // The 13th, with periods starting the 25th, is still inside the period that began Aug 25.
    expect(periodBounds("2026-09-13", 25)).toEqual({ start: "2026-08-25", end: "2026-09-24" });
  });

  it("a reference date on startDay begins a new period", () => {
    expect(periodBounds("2026-09-25", 25)).toEqual({ start: "2026-09-25", end: "2026-10-24" });
  });

  it("a reference date after startDay falls in the current period's start", () => {
    expect(periodBounds("2026-09-30", 25)).toEqual({ start: "2026-09-25", end: "2026-10-24" });
  });

  it("the end is always the day before the next period's start", () => {
    const { end } = periodBounds("2026-09-13", 25);
    const dayAfterEnd = shiftDayForward(end);
    const next = periodBounds(dayAfterEnd, 25);
    expect(next.start).toBe(dayAfterEnd);
  });

  it("works across a year boundary", () => {
    expect(periodBounds("2027-01-05", 25)).toEqual({ start: "2026-12-25", end: "2027-01-24" });
  });
});

describe("shiftPeriod", () => {
  it("moves forward one month", () => {
    expect(shiftPeriod("2026-09-25", 1)).toBe("2026-10-25");
  });

  it("moves backward one month", () => {
    expect(shiftPeriod("2026-09-25", -1)).toBe("2026-08-25");
  });

  it("rolls over a year boundary", () => {
    expect(shiftPeriod("2026-12-25", 1)).toBe("2027-01-25");
    expect(shiftPeriod("2027-01-25", -1)).toBe("2026-12-25");
  });
});

describe("currentPeriodStart", () => {
  it("agrees with periodBounds for today", () => {
    const today = new Date();
    const todayIso = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0"),
    ].join("-");
    expect(currentPeriodStart(15)).toBe(periodBounds(todayIso, 15).start);
  });
});

function shiftDayForward(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + 1);
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
}

describe("period numbers", () => {
  it("numbers a period by the month it ends in", () => {
    expect(periodNumber("2025-12-25", 25)).toEqual({ number: 1, year: 2026 });
    expect(periodNumber("2026-01-25", 25)).toEqual({ number: 2, year: 2026 });
    expect(periodNumber("2026-11-25", 25)).toEqual({ number: 12, year: 2026 });
    expect(periodNumber("2026-03-01", 1)).toEqual({ number: 3, year: 2026 });
  });

  it("labels and titles a period", () => {
    expect(periodLabel("2025-12-25", 25)).toBe("P1");
    expect(periodTitle("2025-12-25", 25)).toBe("Period 1, 2026 · 25 Dec – 24 Jan");
  });
});
