import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { PortfolioProvider } from "../hooks/usePortfolio";
import GainrSettingsButton from "./GainrSettingsButton";

vi.mock("../api/client", () => ({
  api: {
    getTrading212: vi.fn(),
    listAssets: vi.fn(() => Promise.resolve([])),
    listPortfolios: vi.fn(() => Promise.resolve([{ id: 1, name: "Main", is_archived: false }])),
  },
}));

vi.mock("../api/griprClient", () => ({ griprApi: { listAccounts: vi.fn(() => Promise.resolve([])) } }));

describe("GainrSettingsButton", () => {
  beforeEach(() => vi.clearAllMocks());

  it("opens gainr's settings with the Trading 212 sync", async () => {
    vi.mocked(api.getTrading212).mockResolvedValue({
      configured: true, enabled: true, since: "2026-10-02", portfolio_id: 1, cashback_account_id: null, last_synced_at: null, last_error: null, unmapped: [],
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <PortfolioProvider>
            <GainrSettingsButton />
          </PortfolioProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Settings" }));

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Trading 212" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Close settings" }));
    expect(screen.queryByRole("heading", { name: "Settings" })).not.toBeInTheDocument();
  });
});
