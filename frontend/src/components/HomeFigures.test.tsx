import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Summary } from "../api/types";
import HomeFigures from "./HomeFigures";

const summary: Summary = {
  total_value_eur: "57226.45",
  cash_eur: "1060",
  cash_by_broker_eur: {},
  holdings_value_eur: "56166.45",
  ytd_return_eur: "10486.60",
  ytd_return_pct: "23.49",
  ytd_mwr_pct: "21.8",
  total_mwr_pct: "49.5",
  total_mwr_yearly_pct: "12.3",
  total_return_eur: "11200",
  total_return_pct: "24.41",
  unrealized_pnl_eur: "9600",
  unrealized_pnl_pct: "20",
  realized_pnl_eur: "1500",
  total_invested_eur: "46000",
  day_change_eur: "419.41",
  day_change_pct: "0.74",
  as_of: "2026-10-20",
};

function figure(label: string) {
  return screen.getByText(label).closest("div") as HTMLElement;
}

describe("HomeFigures", () => {
  it("leads with the money-weighted return for this year and since start", () => {
    render(<HomeFigures summary={summary} />);

    expect(figure("This year")).toHaveTextContent("+21,80%");
    expect(figure("This year")).not.toHaveTextContent("23,49");
    // since start is a yearly rate, next to the total euros
    expect(figure("Since start")).toHaveTextContent("+12,30%/yr");
    expect(figure("Since start")).not.toHaveTextContent("24,41");
  });

  it("keeps the time-weighted and the simple total in the hints", () => {
    render(<HomeFigures summary={summary} />);

    expect(figure("This year")).toHaveAttribute("title", expect.stringContaining("Time-weighted +23,49%"));
    expect(figure("Since start")).toHaveAttribute("title", expect.stringContaining("+24,41%"));
  });

  it("uses the range's own money-weighted return while there is less than a year of history", () => {
    render(<HomeFigures summary={{ ...summary, total_mwr_yearly_pct: null, total_mwr_pct: "6.4" }} />);

    expect(figure("Since start")).toHaveTextContent("+6,40%");
    expect(figure("Since start")).not.toHaveTextContent("/yr");
  });

  it("falls back to the time-weighted return, and says so, when no money-weighted rate exists", () => {
    render(<HomeFigures summary={{ ...summary, ytd_mwr_pct: null, total_mwr_pct: null, total_mwr_yearly_pct: null }} />);

    expect(figure("This year")).toHaveTextContent("+23,49%");
    expect(figure("This year")).toHaveAttribute("title", expect.stringContaining("Time-weighted: deposits and withdrawals"));
    expect(figure("Since start")).toHaveTextContent("+24,41%");
  });

  it("shows placeholders while the summary loads", () => {
    const { container } = render(<HomeFigures summary={undefined} />);

    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(4);
  });
});
