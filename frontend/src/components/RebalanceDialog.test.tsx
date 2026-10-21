import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { RebalancePlan } from "../api/types";
import { formatEur } from "../utils/format";
import RebalanceDialog, { parseAmount } from "./RebalanceDialog";

vi.mock("../api/client", () => ({ api: { getRebalancePlan: vi.fn() } }));

const plan: RebalancePlan = {
  amount_eur: "500.00",
  from_cash: false,
  cash_eur: "95.16",
  purchases: [
    { asset_id: 3, ticker: "SMH", name: "VanEck Semiconductor", dlt_judgment: "attractive", amount_eur: "300.00", quantity: "3.3333", weight_before_pct: "13.8", weight_after_pct: "14.5", target_pct: "15" },
    { asset_id: 0, ticker: "CASH", name: "Cash", dlt_judgment: null, amount_eur: "200.00", quantity: null, weight_before_pct: "0.2", weight_after_pct: "1.0", target_pct: "1" },
    { asset_id: 4, ticker: "ABN", name: "ABN AMRO", dlt_judgment: "neutral", amount_eur: "0.00", quantity: "0", weight_before_pct: "12", weight_after_pct: "11.9", target_pct: "5" },
  ],
  left_out: [
    { name: "Bitcoin", dlt_judgment: "neutral", reason: "no_target" },
    { name: "Nu Holdings", dlt_judgment: "critical", reason: "critical" },
    { name: "Tonies", dlt_judgment: null, reason: "unrated" },
  ],
};

function renderDialog() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <RebalanceDialog portfolioId={1} cashEur="95.16" onClose={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("parseAmount", () => {
  it("reads plain, Dutch and English amounts", () => {
    expect(parseAmount("500")).toBe("500.00");
    expect(parseAmount("€ 1.250,50")).toBe("1250.50");
    expect(parseAmount("1,250.5")).toBe("1250.50");
    expect(parseAmount("12,5")).toBe("12.50");
  });
  it("refuses nothing, zero and nonsense", () => {
    expect(parseAmount("")).toBeNull();
    expect(parseAmount("0")).toBeNull();
    expect(parseAmount("abc")).toBeNull();
    expect(parseAmount("1.2.3")).toBeNull();
  });
});

describe("RebalanceDialog", () => {
  beforeEach(() => vi.clearAllMocks());

  it("plans an amount of new money: what to buy, what's skipped and what has no target", async () => {
    vi.mocked(api.getRebalancePlan).mockResolvedValue(plan);
    renderDialog();
    expect(screen.getByText("Enter an amount to see what to buy.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `From cash (${formatEur("95.16")})` })).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Amount to invest"), "500");

    expect(await screen.findByText("VanEck Semiconductor")).toBeInTheDocument();
    expect(api.getRebalancePlan).toHaveBeenCalledWith(1, "500.00", false);
    expect(screen.getByText("≈ 3,333 SMH")).toBeInTheDocument();
    expect(screen.getByText("Keep as cash")).toBeInTheDocument();
    expect(screen.getByText("At or over target, so nothing: ABN AMRO.")).toBeInTheDocument();
    expect(screen.getByText("No target set, so left out: Bitcoin.")).toBeInTheDocument();
    expect(screen.getByText("Rated Critical by DLT, so left out: Nu Holdings.")).toBeInTheDocument();
    expect(screen.getByText("Not rated by DLT, so left out: Tonies.")).toBeInTheDocument();
    // Each holding bought shows its rating; cash has none.
    expect(screen.getByText("Attractive")).toBeInTheDocument();
    expect(screen.queryByText("No rating")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /From cash/ }));
    expect(api.getRebalancePlan).toHaveBeenLastCalledWith(1, "500.00", true);
  });

  it("says so when there's less cash than the amount", async () => {
    vi.mocked(api.getRebalancePlan).mockRejectedValue(new Error("400 Bad Request: only cash"));
    renderDialog();
    await userEvent.click(screen.getByRole("button", { name: /From cash/ }));
    await userEvent.type(screen.getByLabelText("Amount to invest"), "500");
    expect(await screen.findByRole("alert")).toHaveTextContent(/That's more than the € 95,16 in cash/);
  });
});
