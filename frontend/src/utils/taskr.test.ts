import { describe, expect, it } from "vitest";

import { agendaRange, dayLabel, overdueTitle, rangeLabel, shiftStart, shortDate, shortDayDate } from "./taskr";

// A fixed "today" (a Wednesday) -- nothing here reads the clock.
const TODAY = "2026-10-14";

describe("agendaRange", () => {
  it("covers one day, seven days or thirty days from the start", () => {
    expect(agendaRange("day", TODAY)).toEqual({ from: TODAY, to: TODAY });
    expect(agendaRange("week", TODAY)).toEqual({ from: TODAY, to: "2026-10-20" });
    expect(agendaRange("month", TODAY)).toEqual({ from: TODAY, to: "2026-11-12" });
  });

  it("crosses a year end", () => {
    expect(agendaRange("week", "2026-12-29")).toEqual({ from: "2026-12-29", to: "2027-01-04" });
  });
});

describe("shiftStart", () => {
  it("moves a whole window back or forward", () => {
    expect(shiftStart("day", TODAY, 1)).toBe("2026-10-15");
    expect(shiftStart("day", TODAY, -1)).toBe("2026-10-13");
    expect(shiftStart("week", TODAY, 1)).toBe("2026-10-21");
    expect(shiftStart("week", TODAY, -1)).toBe("2026-10-07");
    expect(shiftStart("month", TODAY, 1)).toBe("2026-11-13");
  });

  it("lands next to the previous window, with no gap and no overlap", () => {
    const next = shiftStart("month", TODAY, 1);
    expect(next).toBe(shiftStart("day", agendaRange("month", TODAY).to, 1));
  });
});

describe("shortDate / shortDayDate", () => {
  it("leaves out this year and spells out another", () => {
    expect(shortDate("2026-10-03", TODAY)).toBe("3 okt");
    expect(shortDate("2027-01-03", TODAY)).toBe("3 jan 2027");
  });

  it("prefixes the short weekday", () => {
    expect(shortDayDate("2026-10-12", TODAY)).toBe("ma 12 okt");
  });
});

describe("dayLabel", () => {
  it("names yesterday, today and tomorrow", () => {
    expect(dayLabel("2026-10-13", TODAY)).toBe("Gisteren");
    expect(dayLabel(TODAY, TODAY)).toBe("Vandaag");
    expect(dayLabel("2026-10-15", TODAY)).toBe("Morgen");
  });

  it("gives any other day its weekday and date", () => {
    expect(dayLabel("2026-10-16", TODAY)).toBe("vrijdag 16 okt");
    expect(dayLabel("2026-10-12", TODAY)).toBe("maandag 12 okt");
    expect(dayLabel("2027-01-01", TODAY)).toBe("vrijdag 1 jan 2027");
  });
});

describe("rangeLabel", () => {
  it("names the day of a one-day view", () => {
    expect(rangeLabel("day", TODAY, TODAY)).toBe("Vandaag · woensdag 14 okt");
    expect(rangeLabel("day", "2026-10-15", TODAY)).toBe("Morgen · donderdag 15 okt");
    expect(rangeLabel("day", "2026-10-20", TODAY)).toBe("dinsdag 20 okt");
  });

  it("spans a week or a month", () => {
    expect(rangeLabel("week", TODAY, TODAY)).toBe("14 okt – 20 okt");
    expect(rangeLabel("month", "2026-12-20", TODAY)).toBe("20 dec – 18 jan 2027");
  });
});

describe("overdueTitle", () => {
  it("calls it overdue when the range starts today or earlier", () => {
    expect(overdueTitle(TODAY, TODAY)).toBe("Achterstallig");
    expect(overdueTitle("2026-10-07", TODAY)).toBe("Achterstallig");
  });

  it("calls it 'before this period' for a range further ahead", () => {
    expect(overdueTitle("2026-10-21", TODAY)).toBe("Vóór deze periode");
  });
});
