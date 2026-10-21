import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PositionMetric, PositionMetrics } from "../api/types";
import PositionMetricsSection from "./PositionMetrics";

function metric(extra: Partial<PositionMetric>): PositionMetric {
  return { key: "k", label: "L", unit: "pct", why: null, value: null, text: null, detail: null, history: [], source_hint: null, ...extra };
}

const data: PositionMetrics = {
  lens: "Growth company",
  currency: "USD",
  metrics: [
    metric({ key: "m", label: "Operating margin", value: "6.72", why: "The current debate", history: [{ label: "FY2024", value: "12.7" }, { label: "FY2025", value: "11.1" }] }),
    metric({ key: "g", label: "GMV growth", source_hint: "The company's quarterly results" }),
  ],
};

describe("PositionMetricsSection", () => {
  it("shows what Yahoo had, with its trend and why it matters", () => {
    render(<PositionMetricsSection data={data} />);

    expect(screen.getByText("Operating margin")).toBeInTheDocument();
    expect(screen.getByText(/^6[.,]72%$/)).toBeInTheDocument();
    expect(screen.getByText("The current debate")).toBeInTheDocument();
    expect(screen.getByText(/^FY24 12[.,]7% → FY25 11[.,]1%$/)).toBeInTheDocument();
    expect(screen.getByText(/1 of 2 from Yahoo/)).toBeInTheDocument();
  });

  it("keeps a missing metric on the list and says where to look", () => {
    render(<PositionMetricsSection data={data} />);

    expect(screen.getByText("GMV growth")).toBeInTheDocument();
    expect(screen.getByText("Not on Yahoo")).toBeInTheDocument();
    expect(screen.getByText(/Look in: The company's quarterly results/)).toBeInTheDocument();
  });
});
