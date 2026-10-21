import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { DividendIncome } from "../api/types";
import Income from "./Income";

vi.mock("../api/client", () => ({ api: { getDividendIncome: vi.fn() } }));
vi.mock("../components/GainrTopRow", () => ({ default: () => null }));
vi.mock("../hooks/usePortfolio", () => ({
  usePortfolio: () => ({ portfolioId: 1, portfolios: [{ id: 1, name: "Main" }], setPortfolioId: vi.fn(), isLoading: false }),
}));

const income = (over: Partial<DividendIncome> = {}): DividendIncome => ({
  as_of: "2026-10-18",
  received_this_year_eur: "78.70",
  received_last_year_eur: "58.27",
  received_12m_eur: "85.10",
  expected_12m_eur: "75.07",
  paying_holdings: 3,
  yield_on_cost_pct: "0.17",
  current_yield_pct: "0.16",
  months: [
    { month: "2025-11", received_eur: "0", expected_eur: "0" },
    { month: "2026-10", received_eur: "4.00", expected_eur: "2.00" },
    { month: "2026-11", received_eur: "0", expected_eur: "12.00" },
  ],
  years: [
    { year: 2026, total_eur: "78.70", months: Array(12).fill("0") },
    { year: 2025, total_eur: "58.27", months: Array(12).fill("0") },
  ],
  holdings: [
    {
      asset_id: 1, ticker: "ABN", name: "ABN AMRO", is_held: true, received_total_eur: "90.00", received_12m_eur: "45.83",
      payments_12m: 2, expected_12m_eur: "45.83", last_paid_on: "2026-09-09", yield_on_cost_pct: "6.10", current_yield_pct: "4.20",
    },
    {
      asset_id: 2, ticker: "ASML", name: "ASML", is_held: false, received_total_eur: "8.37", received_12m_eur: "8.37",
      payments_12m: 2, expected_12m_eur: "0", last_paid_on: "2026-05-01", yield_on_cost_pct: null, current_yield_pct: null,
    },
  ],
  ...over,
});

function renderIncome() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Income />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Income", () => {
  beforeAll(() => {
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  });
  beforeEach(() => vi.clearAllMocks());

  it("says it's loading, then shows the totals, holdings and years", async () => {
    vi.mocked(api.getDividendIncome).mockResolvedValue(income());
    renderIncome();
    expect(screen.getByRole("status")).toHaveTextContent("Loading dividends…");

    expect(await screen.findByText("Next 12 months")).toBeInTheDocument();
    expect(screen.getByText("expected from 3 holdings")).toBeInTheDocument();
    expect(screen.getByText("2026 so far")).toBeInTheDocument();

    const holdings = within(screen.getByRole("list", { name: "Dividends by holding" }));
    expect(holdings.getByText("ABN AMRO")).toBeInTheDocument();
    expect(holdings.getByText(/2× in 12 months · last 9 Sept 2026 · 4,20% yield · 6,10% on cost/)).toBeInTheDocument();
    expect(holdings.queryByText("ASML")).not.toBeInTheDocument();
    // Sold holdings are folded away underneath.
    const sold = within(screen.getByRole("list", { name: "Sold holdings", hidden: true }));
    expect(sold.getByText("ASML")).toBeInTheDocument();
    expect(sold.getByText(/received in total/)).toBeInTheDocument();
    expect(screen.getByText("Sold holdings (1)")).toBeInTheDocument();

    const years = within(screen.getByRole("list", { name: "Dividends per year" }));
    expect(years.getByText(/vs 2025/)).toBeInTheDocument();
    expect(api.getDividendIncome).toHaveBeenCalledWith(1);
  });

  it("explains what shows up here when there are no dividends yet", async () => {
    vi.mocked(api.getDividendIncome).mockResolvedValue(income({ years: [], holdings: [] }));
    renderIncome();
    expect(await screen.findByText("No dividends yet")).toBeInTheDocument();
  });

  it("offers a retry when the dividends can't be loaded", async () => {
    vi.mocked(api.getDividendIncome).mockRejectedValue(new Error("500"));
    renderIncome();
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the dividends.");
  });
});
