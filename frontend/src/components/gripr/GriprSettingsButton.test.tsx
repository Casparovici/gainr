import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { griprApi } from "../../api/griprClient";
import type { GriprBankStatus } from "../../api/griprTypes";
import GriprSettingsButton from "./GriprSettingsButton";

vi.mock("../../api/griprClient", () => ({
  griprApi: {
    getBanks: vi.fn(),
    getSettings: vi.fn(() => Promise.resolve({ period_start_day: 1 })),
    listAccounts: vi.fn(() => Promise.resolve([])),
  },
}));

function banks(connected: boolean): GriprBankStatus {
  return {
    configured: true,
    connections: [
      {
        id: 1, name: "ING", kind: "consent", amount_only: false, connected, enabled: true, since: "2026-10-03", last_synced_at: null, last_error: null,
        valid_until: connected ? new Date(Date.now() + 120 * 86_400_000).toISOString() : null, accounts: [],
      },
    ],
    rules: [],
  };
}

function renderButton(path = "/gripr") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <GriprSettingsButton />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GriprSettingsButton", () => {
  beforeEach(() => vi.clearAllMocks());

  it("opens the settings dialog", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(banks(true));
    renderButton();
    await userEvent.click(await screen.findByRole("button", { name: "Settings" }));
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
  });

  it("opens straight away when a bank sends the reader back", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(banks(true));
    renderButton("/gripr?bank=connected");
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(await screen.findByRole("status")).toHaveTextContent(/Connected\./);
  });
});
