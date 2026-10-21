import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { griprApi } from "../../api/griprClient";
import type { GriprAccount, GriprBankConnection, GriprBankStatus } from "../../api/griprTypes";
import BankSettings from "./BankSettings";

vi.mock("../../api/griprClient", () => ({
  griprApi: {
    getBanks: vi.fn(),
    listAccounts: vi.fn(),
    updateBank: vi.fn(),
    mapBankAccount: vi.fn(),
    createBankRule: vi.fn(),
    deleteBankRule: vi.fn(),
    connectBank: vi.fn(),
    disconnectBank: vi.fn(),
    syncBanks: vi.fn(),
  },
}));

function account(id: number, name: string): GriprAccount {
  return {
    id, name, type: "checking", balance_mode: "transactional", opening_balance: "0", manual_balance: "0",
    is_archived: false, balance: "0", usage_count: 0, color: null, bank_logo_key: null, held_in_account_id: null,
  };
}

function bankConnection(id: number, name: string, overrides: Partial<GriprBankConnection> = {}): GriprBankConnection {
  return {
    id, name, kind: "consent", amount_only: false, connected: false, valid_until: null, enabled: false, since: null, last_synced_at: null, last_error: null,
    accounts: [], ...overrides,
  };
}

const ING_CONNECTED = bankConnection(1, "ING", {
  connected: true,
  valid_until: new Date(Date.now() + 120 * 86_400_000).toISOString(),
  enabled: true,
  since: "2026-10-03",
  accounts: [{ iban: "NL11INGB0001234567", product: "Betaalrekening", holder_name: "Hr J Jansen", gripr_account_id: 4, in_consent: true }],
});

function status(overrides: Partial<GriprBankStatus> = {}): GriprBankStatus {
  return {
    configured: true,
    connections: [ING_CONNECTED, bankConnection(2, "Trade Republic")],
    rules: [
      { id: 1, iban: "NL33TRBK0001112223", text_contains: null, amount: null, amount_max: null, day_of_month: null, direction: null, gripr_account_id: 3 },
    ],
    ...overrides,
  };
}

function renderCard(path = "/gripr") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <BankSettings defaultOpen />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BankSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(griprApi.listAccounts).mockResolvedValue([account(3, "Trade Republic"), account(4, "ING")]);
  });

  it("says so on a server without the bank settings", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(status({ configured: false, connections: [bankConnection(1, "ING")] }));
    renderCard();
    expect(await screen.findByText(/aren't set up on this server/)).toBeInTheDocument();
  });

  it("says what failed when the status can't load", async () => {
    vi.mocked(griprApi.getBanks).mockRejectedValue(new Error("500"));
    renderCard();
    expect(await screen.findByText(/Couldn't load your bank connections/)).toBeInTheDocument();
  });

  it("shows each bank on its own: ING syncing, Trade Republic ready to connect", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(status());
    vi.mocked(griprApi.connectBank).mockReturnValue(new Promise(() => {})); // never resolves: no navigation in jsdom
    renderCard();
    const ing = await screen.findByRole("region", { name: "ING" });
    expect(within(ing).getByText(/Betaalrekening/)).toHaveTextContent("•••• 4567");
    expect(await within(ing).findByRole("combobox", { name: /gripr account/ })).toHaveValue("4");

    const tr = screen.getByRole("region", { name: "Trade Republic" });
    await userEvent.click(within(tr).getByRole("button", { name: "Connect Trade Republic" }));
    expect(griprApi.connectBank).toHaveBeenCalledWith(2);
  });

  it("shows the outcome a bank's redirect reports", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(status());
    renderCard("/gripr?bank=connected");
    expect(await screen.findByRole("status")).toHaveTextContent(/Connected\. Check which gripr account/);
  });

  it("switches one bank on from a date without touching the other", async () => {
    const tr = bankConnection(2, "Trade Republic", {
      connected: true,
      valid_until: new Date(Date.now() + 80 * 86_400_000).toISOString(),
      accounts: [{ iban: "NL33TRBK0001112223", product: "", holder_name: "J Jansen", gripr_account_id: 3, in_consent: true }],
    });
    vi.mocked(griprApi.getBanks).mockResolvedValue(status({ connections: [ING_CONNECTED, tr] }));
    vi.mocked(griprApi.updateBank).mockResolvedValue(status());
    renderCard();
    const section = await screen.findByRole("region", { name: "Trade Republic" });
    await userEvent.click(within(section).getByRole("checkbox", { name: "Book new transactions automatically" }));
    expect(griprApi.updateBank).toHaveBeenCalledWith(2, { enabled: true, since: null });
  });

  it("remaps an account to skip it", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(status());
    vi.mocked(griprApi.mapBankAccount).mockResolvedValue(status());
    renderCard();
    const ing = await screen.findByRole("region", { name: "ING" });
    await within(ing).findByRole("option", { name: "ING" });
    await userEvent.selectOptions(within(ing).getByRole("combobox", { name: /gripr account/ }), "Skip this account");
    expect(griprApi.mapBankAccount).toHaveBeenCalledWith("NL11INGB0001234567", null);
  });

  it("adds an own-account rule only once it has something to match on", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(status({ rules: [] }));
    vi.mocked(griprApi.createBankRule).mockResolvedValue(status());
    renderCard();
    const own = await screen.findByRole("region", { name: "Your own accounts" });
    await within(own).findByRole("option", { name: "Trade Republic" });
    await userEvent.selectOptions(within(own).getByRole("combobox", { name: "Transfer with" }), "Trade Republic");
    const add = within(own).getByRole("button", { name: "Add" });
    expect(add).toBeDisabled();
    await userEvent.type(within(own).getByRole("textbox", { name: "Description contains" }), "B 145-58977");
    await userEvent.click(add);
    expect(griprApi.createBankRule).toHaveBeenCalledWith({
      iban: null, text_contains: "B 145-58977", amount: null, amount_max: null, day_of_month: null, direction: null, gripr_account_id: 3,
    });
  });

  it("adds a saveback rule: money out, up to an amount, around a day", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(status({ rules: [] }));
    vi.mocked(griprApi.createBankRule).mockResolvedValue(
      status({
        rules: [{ id: 2, iban: null, text_contains: null, amount: null, amount_max: "15.00", day_of_month: 2, direction: "out", gripr_account_id: 3 }],
      }),
    );
    renderCard();
    const own = await screen.findByRole("region", { name: "Your own accounts" });
    await within(own).findByRole("option", { name: "Trade Republic" });
    await userEvent.type(within(own).getByRole("textbox", { name: "Day of month" }), "2");
    await userEvent.selectOptions(within(own).getByRole("combobox", { name: "Transfer with" }), "Trade Republic");
    expect(within(own).getByRole("button", { name: "Add" })).toBeDisabled(); // a day alone isn't a rule
    await userEvent.selectOptions(within(own).getByRole("combobox", { name: "Amount is" }), "Up to");
    await userEvent.type(within(own).getByRole("textbox", { name: "Amount" }), "15");
    await userEvent.selectOptions(within(own).getByRole("combobox", { name: "Direction" }), "Money out");
    await userEvent.click(within(own).getByRole("button", { name: "Add" }));
    expect(griprApi.createBankRule).toHaveBeenCalledWith({
      iban: null, text_contains: null, amount: null, amount_max: "15", day_of_month: 2, direction: "out", gripr_account_id: 3,
    });
    expect(await within(own).findByText(/money out up to € 15,00 around the 2nd/)).toBeInTheDocument();
  });

  it("explains that an amount-only bank is checked against what you enter", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(status({ connections: [ING_CONNECTED, bankConnection(2, "Trade Republic", { amount_only: true })] }));
    renderCard();
    const tr = await screen.findByRole("region", { name: "Trade Republic" });
    expect(tr).toHaveTextContent("Trade Republic sends only dates and amounts");
  });

  it("reports a sync, with any bank that couldn't be read, and links to what needs categorising", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(status());
    vi.mocked(griprApi.syncBanks).mockResolvedValue({
      booked: 3, matched: 2, fulfilled: 1, counterparts: 0, problems: { "Trade Republic": "not connected" },
    });
    renderCard();
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    const result = await screen.findByRole("status");
    expect(result).toHaveTextContent("3 booked, 1 filed under a recurring rule, 2 already in gripr. Trade Republic: not connected");
    expect(within(result).getByRole("link", { name: "Categorise them" })).toHaveAttribute("href", "/gripr/transactions?category=uncategorized");
  });

  it("asks to reconnect a bank that's switched on but lost its consent", async () => {
    const lapsed = { ...ING_CONNECTED, connected: false, valid_until: null };
    vi.mocked(griprApi.getBanks).mockResolvedValue(status({ connections: [lapsed, bankConnection(2, "Trade Republic")] }));
    renderCard();
    expect(await screen.findByRole("button", { name: "Reconnect ING" })).toBeInTheDocument();
  });

  it("nudges a reconnect when a consent is about to end", async () => {
    const ending = { ...ING_CONNECTED, valid_until: new Date(Date.now() + 5 * 86_400_000).toISOString() };
    vi.mocked(griprApi.getBanks).mockResolvedValue(status({ connections: [ending, bankConnection(2, "Trade Republic")] }));
    renderCard();
    expect(await screen.findByRole("button", { name: "Reconnect ING" })).toBeInTheDocument();
  });
  it("shows Trading 212 as read with the server's key, with nothing to connect or disconnect", async () => {
    const t212 = bankConnection(3, "Trading 212", {
      kind: "api_key",
      connected: true,
      enabled: true,
      since: "2026-10-02",
      accounts: [{ iban: "T212", product: "Invest account", holder_name: "", gripr_account_id: 4, in_consent: true }],
    });
    vi.mocked(griprApi.getBanks).mockResolvedValue(status({ connections: [ING_CONNECTED, t212] }));

    renderCard();

    const section = await screen.findByRole("region", { name: "Trading 212" });
    expect(within(section).getByText("Read with the API key set on the server")).toBeInTheDocument();
    expect(within(section).getByText(/take the category you last gave that shop/)).not.toBeVisible();
    await userEvent.click(within(section).getByRole("button", { name: "About Trading 212" }));
    expect(within(section).getByText(/take the category you last gave that shop/)).toBeVisible();
    expect(within(section).queryByRole("button", { name: /connect/i })).not.toBeInTheDocument();
    expect(within(section).getByRole("checkbox", { name: "Book new transactions automatically" })).toBeChecked();
  });

  it("starts folded, with Sync now as an icon in the section's header", async () => {
    vi.mocked(griprApi.getBanks).mockResolvedValue(status());
    vi.mocked(griprApi.syncBanks).mockResolvedValue({ booked: 2, matched: 0, fulfilled: 0, counterparts: 0, problems: {} });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <BankSettings />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const toggle = await screen.findByRole("button", { name: "Banks" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("region", { name: "ING" })).not.toBeInTheDocument();
    const sync = await screen.findByRole("button", { name: "Sync now" });
    expect(sync).toHaveTextContent(""); // an icon, no word

    await userEvent.click(sync);

    // The result is in the body, so syncing opens the section.
    expect(await screen.findByRole("status")).toHaveTextContent("2 booked");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });
});
