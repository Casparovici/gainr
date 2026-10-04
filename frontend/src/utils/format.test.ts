import { describe, expect, it } from "vitest";
import {
  apiToDecimalInput,
  decimalInputToApi,
  formatCompactCurrency,
  formatCurrency,
  formatDate,
  formatEur,
  formatPct,
  formatQuantity,
  formatRatio,
  formatRelativeTime,
  formatWeight,
  numberToDecimalInput,
  parseDecimalInput,
  pnlColorClass,
  toNumber,
  todayIsoDate,
} from "./format";

describe("toNumber", () => {
  it("parses a numeric string", () => {
    expect(toNumber("42.5")).toBe(42.5);
  });

  it("returns null for null, undefined, and non-numeric input", () => {
    expect(toNumber(null)).toBeNull();
    expect(toNumber(undefined)).toBeNull();
    expect(toNumber("not a number")).toBeNull();
  });
});

describe("formatEur", () => {
  it("formats a positive number with the euro sign and comma decimal", () => {
    expect(formatEur(9000)).toBe("€ 9.000,00");
  });

  it("formats a negative number", () => {
    expect(formatEur(-42.5)).toBe("€ -42,50");
  });

  it("accepts a numeric string, matching what the API sends", () => {
    expect(formatEur("1234.5")).toBe("€ 1.234,50");
  });

  it("renders an em dash for null/undefined instead of '€ NaN'", () => {
    expect(formatEur(null)).toBe("—");
    expect(formatEur(undefined)).toBe("—");
  });

  it("uses compact notation when requested", () => {
    expect(formatEur(1_500_000, true)).toBe("€ 1,5 mln.");
  });
});

describe("formatCurrency", () => {
  it("formats using the given currency's own symbol, not always EUR", () => {
    expect(formatCurrency(100, "USD")).toBe("US$ 100,00");
  });

  it("falls back to EUR formatting for an invalid currency code", () => {
    expect(formatCurrency(100, "NOT_A_CODE")).toBe("€ 100,00");
  });

  it("defaults to EUR when no currency is given", () => {
    expect(formatCurrency(100, null)).toBe("€ 100,00");
  });

  it("renders an em dash for null/undefined", () => {
    expect(formatCurrency(null, "USD")).toBe("—");
  });
});

describe("formatPct", () => {
  it("adds a leading + for a positive value by default", () => {
    expect(formatPct(5.5)).toBe("+5,50%");
  });

  it("does not add a sign for a negative value (the minus is already there)", () => {
    expect(formatPct(-5.5)).toBe("-5,50%");
  });

  it("suppresses the leading + when signed is false", () => {
    expect(formatPct(5.5, 2, false)).toBe("5,50%");
  });

  it("respects a custom digit count", () => {
    expect(formatPct(5.5, 0, false)).toBe("6%");
  });

  it("renders an em dash for null/undefined", () => {
    expect(formatPct(null)).toBe("—");
  });
});

describe("formatWeight", () => {
  it("never adds a leading + even for a positive value", () => {
    expect(formatWeight(12.34)).toBe("12,3%");
  });
});

describe("formatRatio", () => {
  it("appends an x suffix instead of a percent sign", () => {
    expect(formatRatio(38.14)).toBe("38,1x");
  });

  it("renders an em dash for null/undefined", () => {
    expect(formatRatio(undefined)).toBe("—");
  });
});

describe("formatQuantity", () => {
  it("formats with up to 6 fraction digits, trimming trailing zeros", () => {
    expect(formatQuantity("10")).toBe("10");
    expect(formatQuantity("0.123456")).toBe("0,123456");
  });

  it("renders an em dash for null/undefined", () => {
    expect(formatQuantity(null)).toBe("—");
  });
});

describe("todayIsoDate", () => {
  it("matches the local calendar date, not a UTC-shifted one", () => {
    const now = new Date();
    const expected = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, "0"),
      String(now.getDate()).padStart(2, "0"),
    ].join("-");
    expect(todayIsoDate()).toBe(expected);
  });
});

describe("formatDate", () => {
  it("formats a YYYY-MM-DD string without shifting a day due to UTC parsing", () => {
    // A bare "2026-01-01" parsed as UTC midnight would render as Dec 31 in a negative-UTC-offset
    // timezone; appending T00:00:00 forces local-time parsing so this doesn't happen.
    expect(formatDate("2026-01-01")).toBe("1 Jan 2026");
  });

  it("accepts custom Intl.DateTimeFormat options", () => {
    expect(formatDate("2026-03-15", { month: "long" })).toBe("March");
  });
});

describe("parseDecimalInput", () => {
  it("parses plain dot-decimal input", () => {
    expect(parseDecimalInput("1234.56")).toBe(1234.56);
  });

  it("parses comma-decimal input with no thousands separator", () => {
    expect(parseDecimalInput("1234,56")).toBe(1234.56);
  });

  it("parses European notation with a dot thousands separator and comma decimal", () => {
    expect(parseDecimalInput("1.234,56")).toBe(1234.56);
  });

  it("returns null for blank input", () => {
    expect(parseDecimalInput("")).toBeNull();
    expect(parseDecimalInput("   ")).toBeNull();
  });

  it("returns null for garbage input", () => {
    expect(parseDecimalInput("abc")).toBeNull();
  });
});

describe("decimalInputToApi", () => {
  it("converts European-notation user input to a dot-decimal API string", () => {
    expect(decimalInputToApi("1.234,56")).toBe("1234.56");
  });

  it("returns null for unparseable input", () => {
    expect(decimalInputToApi("")).toBeNull();
  });
});

describe("numberToDecimalInput", () => {
  it("renders a computed number back with a comma decimal separator", () => {
    expect(numberToDecimalInput(1234.5)).toBe("1234,5");
  });

  it("rounds away floating-point noise past 8 decimal places", () => {
    expect(numberToDecimalInput(0.1 + 0.2)).toBe("0,3");
  });
});

describe("apiToDecimalInput", () => {
  it("converts a dot-decimal API value to comma-decimal for display", () => {
    expect(apiToDecimalInput("1234.56")).toBe("1234,56");
  });

  it("renders an empty string for null/undefined, not '—' (this feeds an editable input)", () => {
    expect(apiToDecimalInput(null)).toBe("");
    expect(apiToDecimalInput(undefined)).toBe("");
  });
});

describe("round-trip between decimalInputToApi and apiToDecimalInput", () => {
  it("returns to the original comma-decimal string a user typed", () => {
    const typed = "1.234,56";
    const api = decimalInputToApi(typed);
    expect(api).not.toBeNull();
    expect(apiToDecimalInput(api)).toBe("1234,56");
  });
});

describe("pnlColorClass", () => {
  it("is neutral slate for exactly zero", () => {
    expect(pnlColorClass(0)).toBe("text-slate-500");
  });

  it("is neutral slate for null/undefined, not a false 'loss' colour", () => {
    expect(pnlColorClass(null)).toBe("text-slate-500");
    expect(pnlColorClass(undefined)).toBe("text-slate-500");
  });

  it("is emerald for a gain", () => {
    expect(pnlColorClass(12.5)).toBe("text-emerald-600");
  });

  it("is red for a loss", () => {
    expect(pnlColorClass(-12.5)).toBe("text-red-600");
  });

  it("accepts a numeric string, matching what the API sends", () => {
    expect(pnlColorClass("-5")).toBe("text-red-600");
  });
});

describe("formatCompactCurrency", () => {
  it("formats a large figure compactly in the filer's own currency", () => {
    expect(formatCompactCurrency(402_800_000_000, "USD")).toBe("US$ 402,8 mld.");
  });

  it("falls back to a bare compact number for an unknown currency code", () => {
    expect(formatCompactCurrency(1_500_000, "NOT_A_CODE")).toBe("1,5 mln.");
  });

  it("falls back to a bare compact number when currency is null", () => {
    expect(formatCompactCurrency(1_500_000, null)).toBe("1,5 mln.");
  });

  it("renders an em dash for null/undefined", () => {
    expect(formatCompactCurrency(null, "USD")).toBe("—");
  });
});

describe("formatRelativeTime", () => {
  it("renders minutes for anything under an hour", () => {
    const iso = new Date(Date.now() - 5 * 60_000).toISOString();
    expect(formatRelativeTime(iso)).toBe("5 minutes ago");
  });

  it("renders hours for anything from 1 hour up to a day", () => {
    const iso = new Date(Date.now() - 3 * 3_600_000).toISOString();
    expect(formatRelativeTime(iso)).toBe("3 hours ago");
  });

  it("renders days beyond 24 hours", () => {
    const iso = new Date(Date.now() - 2 * 86_400_000).toISOString();
    expect(formatRelativeTime(iso)).toBe("2 days ago");
  });

  it("returns an empty string for an unparseable timestamp instead of 'NaN ago'", () => {
    expect(formatRelativeTime("not a date")).toBe("");
  });
});
