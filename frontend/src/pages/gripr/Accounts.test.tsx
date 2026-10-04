import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { griprApi } from "../../api/griprClient";
import type { GriprAccount } from "../../api/griprTypes";
import GriprAccounts from "./Accounts";

vi.mock("../../api/griprClient", () => ({
  griprApi: { listAccounts: vi.fn(), listCategories: vi.fn(), listReceivables: vi.fn(), updateAccount: vi.fn(), createAccount: vi.fn(), reorderAccounts: vi.fn() },
}));
// The settings gear has its own tests (GriprSettingsButton.test.tsx) and data needs.
vi.mock("../../components/gripr/GriprSettingsButton", () => ({ default: () => null }));
// The dialog has its own data needs; here it only matters that the right account opens it.
vi.mock("../../components/gripr/AccountDetailDialog", () => ({
  default: ({ account }: { account: GriprAccount }) => <div role="dialog">Details for {account.name}</div>,
}));

function account(id: number, name: string, type: GriprAccount["type"], balance: string, mode: GriprAccount["balance_mode"] = "transactional"): GriprAccount {
  return {
    id, name, type, balance_mode: mode, opening_balance: "0", manual_balance: balance,
    is_archived: false, balance, usage_count: 0, color: null, bank_logo_key: null, held_in_account_id: null,
  };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/gripr"]}>
        <GriprAccounts />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GriprAccounts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(griprApi.listCategories).mockResolvedValue([]);
    vi.mocked(griprApi.listReceivables).mockResolvedValue({ total: "0", items: [] });
    vi.mocked(griprApi.listAccounts).mockResolvedValue([
      account(1, "ING", "checking", "2500.00"),
      account(2, "Onderhoud Auto", "savings", "-500.00"),
      account(3, "Trade Republic", "savings", "20000.00"),
      account(4, "Hypotheek", "loan", "-250000.00", "manual"),
      account(5, "Ford Focus", "asset", "6800.00", "manual"),
    ]);
    vi.mocked(griprApi.updateAccount).mockResolvedValue(account(5, "Ford Focus", "asset", "6500.00", "manual"));
  });

  it("leads with net worth, split into owned and owed", async () => {
    renderPage();
    const header = await screen.findByRole("region", { name: "Net worth" });
    expect(header).toHaveTextContent(/-\s?€?\s?221\.200,00|€ -221\.200,00/);
    expect(header).toHaveTextContent("Owned € 29.300,00");
    expect(header).toHaveTextContent("Owed € 250.500,00");
  });

  it("counts what you're owed for fronted expenses as owned", async () => {
    vi.mocked(griprApi.listReceivables).mockResolvedValue({ total: "102.59", items: [] });
    renderPage();
    const header = await screen.findByRole("region", { name: "Net worth" });
    await vi.waitFor(() => expect(header).toHaveTextContent("Owned € 29.402,59"));
  });

  it("groups accounts by type with a count and subtotal, marking only negatives red", async () => {
    renderPage();
    expect(await screen.findByText("Savings")).toBeInTheDocument();
    const savingsHeader = screen.getByText("Savings").closest("div")!.parentElement!;
    expect(savingsHeader).toHaveTextContent("2");
    expect(savingsHeader).toHaveTextContent("€ 19.500,00");

    const ing = screen.getByRole("button", { name: "ING: details and transactions" });
    expect(within(ing).getByText("€ 2.500,00")).toHaveClass("text-on-surface");
    const overdrawn = screen.getByRole("button", { name: "Onderhoud Auto: details and transactions" });
    expect(within(overdrawn).getByText("€ -500,00")).toHaveClass("text-error");
  });

  it("marks a virtual pot with the account it sits inside", async () => {
    vi.mocked(griprApi.listAccounts).mockResolvedValue([
      account(3, "Trade Republic", "savings", "20000.00"),
      { ...account(2, "Onderhoud Auto", "savings", "-500.00"), held_in_account_id: 3 },
    ]);
    renderPage();
    const pot = await screen.findByRole("button", { name: "Onderhoud Auto: details and transactions" });
    expect(pot).toHaveTextContent("in Trade Republic");
    expect(screen.getByRole("button", { name: "Trade Republic: details and transactions" })).not.toHaveTextContent("in ");
  });

  it("opens an account's details when its row is clicked", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Trade Republic: details and transactions" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Details for Trade Republic");
  });

  it("updates a typed-in balance in place without opening the dialog", async () => {
    renderPage();
    const row = await screen.findByRole("button", { name: "Ford Focus: details and transactions" });
    await userEvent.click(within(row).getByTitle("Typed-in balance — click to update"));
    const input = within(row).getByRole("textbox");
    await userEvent.clear(input);
    await userEvent.type(input, "6500{Enter}");

    expect(griprApi.updateAccount).toHaveBeenCalledWith(5, { manual_balance: "6500" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("says what to do when there are no accounts", async () => {
    vi.mocked(griprApi.listAccounts).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/No accounts yet/)).toBeInTheDocument();
  });
});
