import { describe, expect, it } from "vitest";

import { actionLabel, addDaysISO, dueBucket, dueText, gardnrDate, todayLocalISO } from "./gardnr";

describe("todayLocalISO", () => {
  it("uses the local calendar date, not UTC", () => {
    // 23:30 local on 28 Sep stays the 28th even where UTC has already rolled over.
    expect(todayLocalISO(new Date(2026, 8, 28, 23, 30))).toBe("2026-09-28");
    expect(todayLocalISO(new Date(2026, 0, 5, 0, 5))).toBe("2026-01-05");
  });
});

describe("dueText", () => {
  const today = "2026-09-29";

  it("says 'vandaag' for something due today, not 'te laat'", () => {
    expect(dueText("2026-09-29", today)).toEqual({ text: "vandaag", isDue: true });
  });

  it("calls a date before today late", () => {
    const result = dueText("2026-09-20", today);
    expect(result.isDue).toBe(true);
    expect(result.text).toMatch(/^te laat sinds /);
  });

  it("gives a future date without emphasis", () => {
    const result = dueText("2026-10-03", today);
    expect(result.isDue).toBe(false);
    expect(result.text).toMatch(/^op /);
  });
});

describe("actionLabel", () => {
  it("uses the custom label for 'other'", () => {
    expect(actionLabel("other", "Mulchen")).toBe("Mulchen");
  });

  it("falls back to the fixed label", () => {
    expect(actionLabel("water", null)).toBe("Water geven");
    expect(actionLabel("other", null)).toBe("Overig");
  });
});

describe("addDaysISO", () => {
  it("crosses month and year ends", () => {
    expect(addDaysISO("2026-09-29", 7)).toBe("2026-10-06");
    expect(addDaysISO("2026-12-30", 3)).toBe("2027-01-02");
  });

  it("isn't thrown off by the end of daylight saving time", () => {
    expect(addDaysISO("2026-10-24", 1)).toBe("2026-10-25");
    expect(addDaysISO("2026-10-25", 1)).toBe("2026-10-26");
  });
});

describe("dueBucket", () => {
  const today = "2026-09-29";

  it("sorts a due date into Te laat, Vandaag or Binnenkort", () => {
    expect(dueBucket("2026-09-28", today)).toBe("late");
    expect(dueBucket("2026-09-29", today)).toBe("today");
    expect(dueBucket("2026-10-06", today)).toBe("soon");
  });

  it("leaves anything more than a week out off the list", () => {
    expect(dueBucket("2026-10-07", today)).toBeNull();
  });
});



describe("gardnrDate", () => {
  const today = "2026-10-01"; // a Thursday

  it("names a day in the past week by its Dutch weekday", () => {
    expect(gardnrDate("2026-09-28", today)).toBe("ma");
    expect(gardnrDate("2026-09-30", today)).toBe("wo");
  });

  it("gives day and Dutch month otherwise, with the year only when it's another year", () => {
    expect(gardnrDate("2026-09-12", today)).toBe("12 sep");
    expect(gardnrDate("2026-10-01", today)).toBe("1 okt");
    expect(gardnrDate("2027-03-29", today)).toBe("29 mrt 2027");
  });

  it("feeds the due texts", () => {
    expect(dueText("2026-09-28", today).text).toBe("te laat sinds ma");
    expect(dueText("2026-10-12", today).text).toBe("op 12 okt");
  });
});
