import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { Position } from "../api/types";
import PositionDetailPanel from "./PositionDetailPanel";

vi.mock("../api/client", () => ({ api: { getAssetMetrics: vi.fn() } }));
vi.mock("../hooks/usePortfolio", () => ({
  usePortfolio: () => ({ portfolioId: 1, portfolios: [{ id: 1, name: "Main" }], setPortfolioId: vi.fn(), isLoading: false }),
  useSelectedPortfolioId: () => 1,
}));
// The Notes section has its own tests; the panel only has to hand it the asset.
vi.mock("./notr/LinkedNotes", () => ({
  default: ({ assetId }: { assetId?: number }) => <div data-testid="linked-notes">notes of asset {assetId}</div>,
}));
vi.mock("./PositionMetrics", () => ({ default: () => null }));
vi.mock("./PriceChart", () => ({ default: ({ assetId }: { assetId: number }) => <div data-testid="price-chart">{assetId}</div> }));

const position = (over: Partial<Position>): Position => ({
  asset_id: 7, ticker: "ASML", name: "ASML Holding", asset_class: "stock", quantity: "2", avg_cost_eur: "600",
  cost_basis_eur: "1200", current_price_native: "700", price_date: "2026-10-19", price_quoted_at: null, day_change_eur: null,
  day_change_pct: null, native_currency: "EUR", market_value_eur: "1400", unrealized_pnl_eur: "200", unrealized_pnl_pct: "16.6",
  realized_pnl_eur: "0", weight_pct: "10", price_stale: false, dlt_judgment: null, target_weight_pct: null,
  target_weight_diff_pct: null, target_weight_diff_eur: null, ...over,
});

function renderPanel(p: Position) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PositionDetailPanel position={p} onClose={() => {}} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PositionDetailPanel notes tab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getAssetMetrics).mockResolvedValue({ lens: null, currency: null, metrics: [] });
  });

  it("shows the notes linked to the position", async () => {
    renderPanel(position({}));
    await userEvent.click(await screen.findByRole("button", { name: "Notes" }));
    expect(screen.getByTestId("linked-notes")).toHaveTextContent("notes of asset 7");
  });

  it("has no Notes tab on the cash row", async () => {
    renderPanel(position({ asset_id: 0, ticker: "CASH", name: "Cash" }));
    await screen.findByText("Cash balance");
    expect(screen.queryByRole("button", { name: "Notes" })).not.toBeInTheDocument();
  });
});

describe("PositionDetailPanel price chart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getAssetMetrics).mockResolvedValue({ lens: null, currency: null, metrics: [] });
  });

  it("shows the position's price chart on the Overview", async () => {
    renderPanel(position({}));

    expect(await screen.findByTestId("price-chart")).toHaveTextContent("7");
  });

  it("has no price chart for the cash row, which has no price", async () => {
    renderPanel(position({ asset_id: 0, ticker: "CASH", name: "Cash" }));
    await screen.findByText("Cash balance");

    expect(screen.queryByTestId("price-chart")).not.toBeInTheDocument();
  });
});
