import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Performance } from "../api/types";
import PerformanceChart from "./PerformanceChart";

vi.mock("../hooks/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));
// recharts measures its container, which jsdom can't; the header is what's tested here.
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return { ...actual, ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div> };
});

const performance: Performance = {
  range: "YTD",
  points: [
    { date: "2026-01-02", value_eur: "46000", return_pct: "0" },
    { date: "2026-10-20", value_eur: "57226.45", return_pct: "23.49" },
  ],
  start_value_eur: "46000",
  end_value_eur: "57226.45",
  change_eur: "10486.60",
  change_pct: "23.49",
  mwr_pct: "21.8",
  mwr_yearly_pct: null,
  benchmarks: [],
};

function renderChart(p: Performance, range: Performance["range"] = p.range) {
  return render(
    <PerformanceChart
      performance={p}
      range={range}
      onRangeChange={() => {}}
      isLoading={false}
      benchmarks={[]}
      activeBenchmarks={[]}
      onToggleBenchmark={() => {}}
    />,
  );
}

describe("PerformanceChart header", () => {
  it("leads with the money-weighted return, the euros and the time-weighted return beside it", () => {
    renderChart(performance);

    const header = screen.getByRole("button", { name: "Portfolio value" }).parentElement as HTMLElement;
    expect(within(header).getByText("+21,80%")).toBeInTheDocument();
    expect(within(header).getByText("money-weighted")).toBeInTheDocument();
    expect(header).toHaveTextContent("over YTD");
    expect(header).toHaveTextContent("time-weighted +23,49%");
  });

  it("shows a yearly rate for a range of a year or longer", () => {
    renderChart({ ...performance, range: "Max", mwr_pct: "49.5", mwr_yearly_pct: "12.3" });

    expect(screen.getByText("+12,30%/yr")).toBeInTheDocument();
  });

  it("falls back to the time-weighted return for a day, and labels it that way", () => {
    renderChart({ ...performance, range: "1D", mwr_pct: null, mwr_yearly_pct: null, change_pct: "0.74", change_eur: "419.41" });

    const header = screen.getByRole("button", { name: "Portfolio value" }).parentElement as HTMLElement;
    expect(within(header).getByText("+0,74%")).toBeInTheDocument();
    expect(within(header).getByText("time-weighted")).toBeInTheDocument();
    expect(header).not.toHaveTextContent("money-weighted");
    // not repeated beside itself
    expect(header).not.toHaveTextContent("time-weighted +0,74%");
  });

  it("explains which number is which behind the info button", () => {
    renderChart(performance);

    expect(screen.getByText(/The big number is money-weighted/)).toBeInTheDocument();
  });
});
