import { describe, expect, it } from "vitest";

import { agentLabel, countsLabel, ingredientLabel, planDayLabel, runLabel, sourceLabel } from "./briefr";

// Local times, so the labels don't depend on the machine's time zone.
const NOW = new Date(2026, 9, 19, 8, 0); // Monday 19 Oct 2026, 08:00
const at = (...parts: [number, number, number, number, number]) => new Date(...parts).toISOString();

describe("briefr labels", () => {
  it("names an agent from its slug", () => {
    expect(agentLabel("holdings-scan")).toBe("Holdings scan");
    expect(agentLabel("app-builder")).toBe("App builder");
  });

  it("says when a report ran relative to now", () => {
    expect(runLabel(at(2026, 9, 19, 2, 14), NOW)).toBe("Today 02:14");
    expect(runLabel(at(2026, 9, 18, 3, 5), NOW)).toBe("Yesterday 03:05");
    expect(runLabel(at(2026, 9, 14, 2, 0), NOW)).toBe("Wed 14 Oct");
    expect(runLabel(at(2026, 8, 30, 2, 0), NOW)).toBe("30 Sep");
    expect(runLabel(at(2025, 11, 31, 2, 0), NOW)).toBe("31 Dec 2025");
  });

  it("labels a source by its site", () => {
    expect(sourceLabel("https://www.reuters.com/markets/asml")).toBe("reuters.com");
    expect(sourceLabel("not a url")).toBe("not a url");
  });

  it("sums up the findings, leaving out what's zero", () => {
    expect(countsLabel({ act: 1, watch: 2, ignore: 0 })).toBe("1 act · 2 watch");
    expect(countsLabel({ act: 0, watch: 0, ignore: 0 })).toBe("No findings");
  });
});

describe("planDayLabel", () => {
  it("says today and tomorrow, then the weekday and date", () => {
    expect(planDayLabel("2026-10-23", "2026-10-23")).toBe("Today");
    expect(planDayLabel("2026-10-24", "2026-10-23")).toBe("Tomorrow");
    expect(planDayLabel("2026-10-26", "2026-10-23")).toBe("Mon 26 Oct");
  });
});

describe("ingredientLabel", () => {
  it("writes the amount with a decimal comma, then the unit, the name and the note", () => {
    expect(ingredientLabel({ name: "Sojasaus", quantity: "1.500", unit: "el", note: "licht" })).toBe("1,5 el Sojasaus (licht)");
    expect(ingredientLabel({ name: "Tomaten", quantity: "2", unit: null, note: null })).toBe("2 Tomaten");
    expect(ingredientLabel({ name: "Zout en peper", quantity: null, unit: null, note: null })).toBe("Zout en peper");
  });
});
