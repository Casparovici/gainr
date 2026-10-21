import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Position } from "../api/types";
import TargetWeightInput from "./TargetWeightInput";

const updateCashTargetWeight = vi.fn(() => Promise.resolve({}));
vi.mock("../api/client", () => ({ api: { updateCashTargetWeight: (...args: unknown[]) => updateCashTargetWeight(...(args as [])) } }));
vi.mock("../hooks/usePortfolio", () => ({ usePortfolio: () => ({ portfolioId: 1 }) }));

const cash = {
  asset_id: 0, ticker: "CASH", name: "Cash", asset_class: "fx", quantity: "0", avg_cost_eur: "0", cost_basis_eur: "0",
  current_price_native: null, price_date: null, price_quoted_at: null, day_change_eur: null, day_change_pct: null, native_currency: "EUR", market_value_eur: "685.19",
  unrealized_pnl_eur: null, unrealized_pnl_pct: null, realized_pnl_eur: "0", weight_pct: "1.4", price_stale: false,
  dlt_judgment: null, target_weight_pct: "1.00", target_weight_diff_pct: "0.4", target_weight_diff_eur: "203.49",
} as Position;

function renderCell() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TargetWeightInput position={cash} asText />
    </QueryClientProvider>,
  );
}

describe("TargetWeightInput asText", () => {
  it("reads as plain text like every other row's target, not an input", () => {
    renderCell();
    expect(screen.getByRole("button", { name: "Edit target weight" })).toHaveTextContent("1,0%");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("opens a comma-decimal input on click and saves a changed value", async () => {
    renderCell();
    await userEvent.click(screen.getByRole("button", { name: "Edit target weight" }));
    const input = screen.getByRole("textbox");
    expect(input).toHaveValue("1,00");
    await userEvent.clear(input);
    await userEvent.type(input, "2,5{Enter}");
    expect(updateCashTargetWeight).toHaveBeenCalledWith(1, "2.5");
  });

  it("doesn't save when the value is unchanged", async () => {
    updateCashTargetWeight.mockClear();
    renderCell();
    await userEvent.click(screen.getByRole("button", { name: "Edit target weight" }));
    await userEvent.type(screen.getByRole("textbox"), "{Enter}");
    expect(updateCashTargetWeight).not.toHaveBeenCalled();
  });
});
