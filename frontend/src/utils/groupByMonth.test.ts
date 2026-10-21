import { describe, expect, it } from "vitest";

import { countSummary, groupByMonth } from "./groupByMonth";

describe("groupByMonth", () => {
  it("keeps the list's order and starts a group at each new month", () => {
    const groups = groupByMonth(["2026-09-19", "2026-09-02", "2026-08-30", "2026-09-01"], (d) => d);
    expect(groups.map((g) => [g.key, g.items.length])).toEqual([["2026-09", 2], ["2026-08", 1], ["2026-09", 1]]);
    expect(groups[0].label).toBe("September 2026");
  });

  it("is empty for an empty list", () => {
    expect(groupByMonth([], (d: string) => d)).toEqual([]);
  });
});

describe("countSummary", () => {
  it("counts each kind, most common first, with the caller's plural", () => {
    const phrase = (k: string, n: number) => `${n} ${n === 1 ? k : `${k}s`}`;
    expect(countSummary(["buy", "deposit", "buy"], (k) => k, phrase)).toBe("2 buys · 1 deposit");
  });
});
