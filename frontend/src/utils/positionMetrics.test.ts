import { describe, expect, it } from "vitest";

import type { PositionMetric } from "../api/types";
import { formatHistory, formatMetricValue, hasValue } from "./positionMetrics";

function metric(extra: Partial<PositionMetric>): PositionMetric {
  return { key: "k", label: "L", unit: "pct", why: null, value: null, text: null, detail: null, history: [], source_hint: null, ...extra };
}

describe("formatMetricValue", () => {
  it("formats a figure by its unit", () => {
    expect(formatMetricValue(metric({ unit: "pct", value: "34.03" }), "USD")).toMatch(/^34[.,]0%$/);
    expect(formatMetricValue(metric({ unit: "pct", value: "0.35" }), null)).toMatch(/^0[.,]35%$/);
    expect(formatMetricValue(metric({ unit: "multiple", value: "24.79" }), "USD")).toMatch(/^24[.,]8x$/);
    expect(formatMetricValue(metric({ unit: "amount", value: "91447000000" }), "USD")).toMatch(/91[.,]4/);
  });

  it("keeps enough decimals on a small plain number to read it", () => {
    expect(formatMetricValue(metric({ unit: "number", value: "0.0316" }), null)).toMatch(/^0[.,]0316$/);
    expect(formatMetricValue(metric({ unit: "number", value: "1.12" }), null)).toMatch(/^1[.,]12$/);
  });

  it("shows a list-like metric as its text and a missing one as a dash", () => {
    expect(formatMetricValue(metric({ unit: "text", text: "NVDA 11.3%, MU 11.0%" }), null)).toBe("NVDA 11.3%, MU 11.0%");
    expect(formatMetricValue(metric({}), null)).toBe("—");
  });
});

describe("hasValue", () => {
  it("is true for a figure or a text, false for neither", () => {
    expect(hasValue(metric({ value: "0" }))).toBe(true);
    expect(hasValue(metric({ unit: "text", text: "x" }))).toBe(true);
    expect(hasValue(metric({}))).toBe(false);
  });
});

describe("formatHistory", () => {
  it("lays the trend out oldest to newest", () => {
    const m = metric({ history: [{ label: "FY2024", value: "12.7" }, { label: "FY2025", value: "11.1" }] });
    expect(formatHistory(m, null)).toMatch(/^FY24 12[.,]7% → FY25 11[.,]1%$/);
  });

  it("has no trend to show for a single period", () => {
    expect(formatHistory(metric({ history: [{ label: "FY2025", value: "11.1" }] }), null)).toBeNull();
  });
});
