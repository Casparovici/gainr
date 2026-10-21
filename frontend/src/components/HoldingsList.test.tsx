import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Position } from "../api/types";
import HoldingsList from "./HoldingsList";

vi.mock("./AssetLogo", () => ({ default: () => null }));

function position(extra: Partial<Position>): Position {
  return {
    asset_id: 1, ticker: "ACME", name: "Acme", asset_class: "equity", quantity: "10", avg_cost_eur: "10",
    cost_basis_eur: "100", current_price_native: "12", price_date: "2026-10-20", price_quoted_at: null,
    day_change_eur: "2", day_change_pct: "1.5", native_currency: "EUR", market_value_eur: "120",
    unrealized_pnl_eur: "20", unrealized_pnl_pct: "20", realized_pnl_eur: "0", weight_pct: "40", price_stale: false,
    dlt_judgment: null, target_weight_pct: null, target_weight_diff_pct: null, target_weight_diff_eur: null,
    ...extra,
  };
}

const rows = [
  position({ asset_id: 2, ticker: "SMALL", name: "Small Co", market_value_eur: "50", day_change_pct: "-3.2", weight_pct: "20" }),
  position({ asset_id: 0, ticker: "CASH", name: "Cash", market_value_eur: "999", day_change_pct: null, weight_pct: "30" }),
  position({ asset_id: 1, ticker: "BIG", name: "Big Co", market_value_eur: "500", target_weight_pct: "35" }),
];

function names() {
  return screen.getAllByRole("listitem").map((li) => within(li).getByRole("button").textContent ?? "");
}

describe("HoldingsList", () => {
  it("lists holdings by value with cash last, each with today's move and its weight", () => {
    render(<HoldingsList positions={rows} isLoading={false} onSelect={() => {}} />);
    const items = names();
    expect(items[0]).toContain("Big Co");
    expect(items[1]).toContain("Small Co");
    expect(items[2]).toContain("Cash");
    expect(items[1]).toMatch(/−?-?3[,.]20% today/);
    expect(items[0]).toMatch(/target 35[,.]0%/);
    expect(screen.getByRole("heading", { name: /Holdings\s*2/ })).toBeInTheDocument();
  });

  it("sorts the worst day first on request and opens a holding on tap", async () => {
    const onSelect = vi.fn();
    render(<HoldingsList positions={rows} isLoading={false} onSelect={onSelect} />);
    await userEvent.selectOptions(screen.getByLabelText("Sort holdings"), "today");
    expect(names()[0]).toContain("Small Co");
    await userEvent.click(screen.getAllByRole("button", { name: /Big Co/ })[0]);
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ ticker: "BIG" }));
  });

  it("says what to do when nothing is held, and offers a retry on an error", async () => {
    const { rerender } = render(<HoldingsList positions={[rows[1]]} isLoading={false} onSelect={() => {}} />);
    expect(screen.getByText(/No holdings yet/)).toBeInTheDocument();
    const onRetry = vi.fn();
    rerender(<HoldingsList positions={undefined} isLoading={false} isError onRetry={onRetry} onSelect={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /retry|try again/i }));
    expect(onRetry).toHaveBeenCalled();
  });
});
