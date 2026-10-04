import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { griprApi } from "../../api/griprClient";
import type { GriprAccount } from "../../api/griprTypes";
import AccountDetailDialog from "./AccountDetailDialog";

vi.mock("../../api/griprClient", () => ({
  griprApi: {
    listTransactions: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
    listPortfolioLinks: vi.fn(() => Promise.resolve([])),
    listBankLogos: vi.fn(() => Promise.resolve([])),
    updateAccount: vi.fn(),
    updatePortfolioLink: vi.fn(),
    syncPortfolioLinks: vi.fn(),
    createTransaction: vi.fn(),
    updateTransaction: vi.fn(),
    deleteTransaction: vi.fn(),
  },
}));
vi.mock("../../hooks/usePortfolio", () => ({ usePortfolio: () => ({ portfolios: [] }) }));

function account(id: number, name: string, balance: string, overrides: Partial<GriprAccount> = {}): GriprAccount {
  return {
    id, name, type: "savings", balance_mode: "transactional", opening_balance: "100.00", manual_balance: "0",
    is_archived: false, balance, usage_count: 0, color: null, bank_logo_key: null, held_in_account_id: null, ...overrides,
  };
}

const TRADE_REPUBLIC = account(3, "Trade Republic", "35000.00");
const ACCOUNTS = [
  TRADE_REPUBLIC,
  account(9, "Reservering Vakantie", "400.00", { held_in_account_id: 3 }),
  account(10, "Onderhoud Auto", "-500.00", { held_in_account_id: 3 }),
  account(4, "ING", "1348.04", { type: "checking" }),
];

function renderDialog(subject: GriprAccount) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AccountDetailDialog account={subject} accounts={ACCOUNTS} categories={[]} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("AccountDetailDialog", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows what's actually at the bank for an account holding pots, with the breakdown", () => {
    renderDialog(TRADE_REPUBLIC);

    expect(screen.getByText("At Trade Republic, pots included")).toBeInTheDocument();
    expect(screen.getByText("€ 34.900,00")).toBeInTheDocument(); // 35.000 + 400 − 500
    const breakdown = screen.getByRole("list", { name: "Balance breakdown" });
    expect(within(breakdown).getByText("Unallocated").nextSibling).toHaveTextContent("€ 35.000,00");
    expect(within(breakdown).getByText("Onderhoud Auto").nextSibling).toHaveTextContent("€ -500,00");
  });

  it("checks a correction against the bank total and puts the difference on the unallocated part", async () => {
    vi.mocked(griprApi.updateAccount).mockResolvedValue(TRADE_REPUBLIC);
    renderDialog(TRADE_REPUBLIC);

    await userEvent.click(screen.getByRole("button", { name: "Correct balance" }));
    await userEvent.type(screen.getByRole("textbox", { name: /total in your Trade Republic app/ }), "34910,00");
    await userEvent.click(screen.getByRole("button", { name: "Just correct it" }));

    expect(griprApi.updateAccount).toHaveBeenCalledWith(3, { opening_balance: "110.00" }); // 100 + the €10 difference
  });

  it("keeps a plain balance for an account without pots", () => {
    renderDialog(ACCOUNTS[3]);

    expect(screen.getByText("Balance (from transactions)")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Balance breakdown" })).not.toBeInTheDocument();
  });
});
