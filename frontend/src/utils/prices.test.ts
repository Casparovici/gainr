import { describe, expect, it } from "vitest";

import { formatDate, formatTime } from "./format";
import { pricesAsOfLabel } from "./prices";

const TODAY = "2026-10-19";

describe("pricesAsOfLabel", () => {
  it("is null when nothing is priced", () => {
    expect(pricesAsOfLabel([], TODAY)).toBeNull();
    expect(pricesAsOfLabel([{ price_date: null, price_quoted_at: null }], TODAY)).toBeNull();
  });

  it("calls a settled day's prices its close", () => {
    const label = pricesAsOfLabel([{ price_date: "2026-10-16", price_quoted_at: null }], TODAY);
    expect(label).toBe(`prices as of ${formatDate("2026-10-16")} close`);
  });

  it("shows the newest live quote's time", () => {
    const label = pricesAsOfLabel(
      [
        { price_date: TODAY, price_quoted_at: "2026-10-19T13:45:00Z" },
        { price_date: TODAY, price_quoted_at: "2026-10-19T12:10:00Z" },
      ],
      TODAY,
    );
    expect(label).toBe(`prices as of ${formatTime("2026-10-19T13:45:00Z")}`);
  });

  it("names the oldest price when holdings are priced on different days", () => {
    const label = pricesAsOfLabel(
      [
        { price_date: TODAY, price_quoted_at: "2026-10-19T13:45:00Z" },
        { price_date: "2026-10-15", price_quoted_at: null },
      ],
      TODAY,
    );
    expect(label).toBe(`prices as of ${formatTime("2026-10-19T13:45:00Z")}, oldest ${formatDate("2026-10-15")}`);
  });
});
