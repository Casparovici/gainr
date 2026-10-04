import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { Asset, BrokerStatus } from "../api/types";
import Trading212Sync from "./Trading212Sync";

vi.mock("../api/client", () => ({
  api: {
    getTrading212: vi.fn(),
    updateTrading212: vi.fn(),
    syncTrading212: vi.fn(),
    listAssets: vi.fn(),
    listPortfolios: vi.fn(),
    updateAsset: vi.fn(),
    createAsset: vi.fn(),
    lookupAsset: vi.fn(),
  },
}));

function status(overrides: Partial<BrokerStatus> = {}): BrokerStatus {
  return {
    configured: true, enabled: true, since: "2026-10-02", portfolio_id: 1, last_synced_at: null, last_error: null, unmapped: [],
    ...overrides,
  };
}

const GRID = { isin: "IE000J80JTL1", ticker: "GRIDd_EQ", name: "First Trust Smart Grid", currency: "EUR", records: 2, first_date: "2026-10-02" };

function asset(id: number, ticker: string, name: string): Asset {
  return { id, ticker, name, asset_class: "equity", native_currency: "EUR", yahoo_symbol: null, isin: null, notes: null, dlt_judgment: null };
}

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <Trading212Sync portfolioId={1} portfolioName="Main" />
    </QueryClientProvider>,
  );
}

describe("Trading212Sync", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(api.listAssets).mockResolvedValue([asset(1, "GRIDINAV", "Smart Grid ETF"), asset(2, "AMZN", "Amazon")]);
    vi.mocked(api.listPortfolios).mockResolvedValue([{ id: 1, name: "Main", is_archived: false }, { id: 2, name: "Kids", is_archived: false }]);
  });

  it("stays out of the way on a server without a Trading 212 key", async () => {
    vi.mocked(api.getTrading212).mockResolvedValue(status({ configured: false, enabled: false }));

    const { container } = renderCard();

    await vi.waitFor(() => expect(api.getTrading212).toHaveBeenCalled());
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("says when it can't load", async () => {
    vi.mocked(api.getTrading212).mockRejectedValue(new Error("down"));

    renderCard();

    expect(await screen.findByText(/Couldn't load the Trading 212 sync/)).toBeInTheDocument();
  });

  it("switches on for the portfolio being viewed", async () => {
    vi.mocked(api.getTrading212).mockResolvedValue(status({ enabled: false, portfolio_id: null, since: null }));
    vi.mocked(api.updateTrading212).mockResolvedValue(status());
    renderCard();
    await userEvent.click(await screen.findByRole("button", { name: "Trading 212" }));

    await userEvent.click(screen.getByRole("checkbox", { name: "Book Trading 212 into Main" }));

    expect(api.updateTrading212).toHaveBeenCalledWith({ enabled: true, since: null, portfolio_id: 1 });
  });

  it("opens by itself to link a held-back instrument to an existing asset", async () => {
    vi.mocked(api.getTrading212).mockResolvedValue(status({ unmapped: [GRID] }));
    vi.mocked(api.updateAsset).mockResolvedValue(asset(1, "GRIDINAV", "Smart Grid ETF"));
    renderCard();

    expect(await screen.findByText("1 to link")).toBeInTheDocument();
    expect(screen.getByText(/GRIDd_EQ · IE000J80JTL1 · 2 records/)).toBeInTheDocument();
    await userEvent.click(screen.getByPlaceholderText("This is…"));
    await userEvent.click(await screen.findByText("Smart Grid ETF"));

    expect(api.updateAsset).toHaveBeenCalledWith(1, { isin: "IE000J80JTL1" });
    expect(await screen.findByText(/Linked\./)).toBeInTheDocument();
  });

  it("adds a new asset for a held-back instrument, with its ISIN", async () => {
    vi.mocked(api.getTrading212).mockResolvedValue(status({ unmapped: [GRID] }));
    vi.mocked(api.lookupAsset).mockResolvedValue({ query: "GRID", exact: false, matches: [] });
    vi.mocked(api.createAsset).mockResolvedValue(asset(3, "GRID", "First Trust Smart Grid"));
    renderCard();

    await userEvent.click(await screen.findByPlaceholderText("This is…"));
    await userEvent.click(screen.getByText("+ Add new asset…"));
    expect(screen.getByLabelText("New asset ticker")).toHaveValue("GRID");
    await userEvent.click(screen.getByRole("button", { name: "Add GRID" }));

    expect(api.createAsset).toHaveBeenCalledWith(expect.objectContaining({ ticker: "GRID", isin: "IE000J80JTL1", native_currency: "EUR" }));
  });

  it("keeps what it does behind the ⓘ next to its title", async () => {
    vi.mocked(api.getTrading212).mockResolvedValue(status());
    renderCard();

    const about = await screen.findByRole("button", { name: "About Trading 212" });
    expect(screen.getByText(/are booked here every morning/)).not.toBeVisible();
    await userEvent.click(about);
    expect(screen.getByText(/are booked here every morning/)).toBeVisible();
  });

  it("syncs now and says what happened", async () => {
    vi.mocked(api.getTrading212).mockResolvedValue(status({ last_synced_at: new Date().toISOString() }));
    vi.mocked(api.syncTrading212).mockResolvedValue({ booked: 2, matched: 1, deposits: 1, unmapped: [], problems: [] });
    renderCard();
    await userEvent.click(await screen.findByRole("button", { name: "Trading 212" }));

    await userEvent.click(screen.getByRole("button", { name: "Sync now" }));

    expect(await screen.findByText("2 booked, 1 already in gainr, 1 weekly interest/cashback deposit.")).toBeInTheDocument();
  });

  it("points at the other portfolio when it books there", async () => {
    vi.mocked(api.getTrading212).mockResolvedValue(status({ portfolio_id: 2 }));
    renderCard();
    await userEvent.click(await screen.findByRole("button", { name: "Trading 212" }));

    expect(await screen.findByText("Kids")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
