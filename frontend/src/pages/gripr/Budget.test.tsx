import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { griprApi } from "../../api/griprClient";
import type { GriprAccount, GriprCategory } from "../../api/griprTypes";
import GriprBudget from "./Budget";

vi.mock("../../api/griprClient", () => ({
  griprApi: {
    getSettings: vi.fn(),
    getBudgets: vi.fn(),
    listCategories: vi.fn(),
    getBudgetSuggestions: vi.fn(),
    getSavingsGoals: vi.fn(),
    getSavingsGoalSuggestions: vi.fn(),
    listAccounts: vi.fn(),
    listTransactions: vi.fn(),
    setBudget: vi.fn(),
    setSavingsGoal: vi.fn(),
    reorderCategories: vi.fn(),
    createCategory: vi.fn(),
    updateCategory: vi.fn(),
    deleteCategory: vi.fn(),
    createTransaction: vi.fn(),
    updateTransaction: vi.fn(),
    deleteTransaction: vi.fn(),
  },
}));

function category(id: number, name: string, extra: Partial<GriprCategory> = {}): GriprCategory {
  return { id, name, kind: "expense", parent_id: null, is_archived: false, color: null, linked_loan_account_id: null, ...extra };
}

function account(id: number, name: string, type: GriprAccount["type"]): GriprAccount {
  return {
    id, name, type, balance_mode: "transactional", opening_balance: "0", manual_balance: "0",
    is_archived: false, balance: "0", usage_count: 0, color: null, bank_logo_key: null, held_in_account_id: null,
  };
}

const food = category(1, "Eten & Drinken");
const bars = category(11, "Bars", { parent_id: 1 });
const oldBars = category(12, "Kroegen", { parent_id: 1, is_archived: true });
const study = category(2, "Studieschuld", { linked_loan_account_id: 50 });
const hobby = category(3, "Hobby", { is_archived: true });
const salary = category(4, "Salaris", { kind: "income" });

function renderBudget() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <GriprBudget />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function openFoodDialog() {
  renderBudget();
  await userEvent.click(await screen.findByRole("button", { name: "Eten & Drinken: transactions and settings" }));
  return screen.findByText("Category settings");
}

describe("GriprBudget (Budget + category management)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(griprApi.getSettings).mockResolvedValue({ period_start_day: 1 });
    vi.mocked(griprApi.getBudgets).mockResolvedValue([
      { category_id: 1, category_name: "Eten & Drinken", kind: "expense", budgeted: "300", spent: "120" },
      { category_id: 2, category_name: "Studieschuld", kind: "expense", budgeted: "0", spent: "200" },
      { category_id: 4, category_name: "Salaris", kind: "income", budgeted: "3000", spent: "3000" },
    ]);
    vi.mocked(griprApi.listCategories).mockImplementation(async (includeArchived = false) =>
      [food, bars, oldBars, study, hobby, salary].filter((c) => includeArchived || !c.is_archived),
    );
    vi.mocked(griprApi.getBudgetSuggestions).mockResolvedValue([]);
    vi.mocked(griprApi.getSavingsGoals).mockResolvedValue([]);
    vi.mocked(griprApi.getSavingsGoalSuggestions).mockResolvedValue([]);
    vi.mocked(griprApi.listAccounts).mockResolvedValue([account(9, "ING", "checking"), account(50, "DUO", "loan")]);
    vi.mocked(griprApi.listTransactions).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(griprApi.updateCategory).mockResolvedValue(food);
    vi.mocked(griprApi.createCategory).mockResolvedValue(food);
    vi.mocked(griprApi.deleteCategory).mockResolvedValue(undefined);
  });

  it("shows each category's spent, budget and what's left, and marks a loan-linked one", async () => {
    renderBudget();
    const row = await screen.findByRole("button", { name: "Eten & Drinken: transactions and settings" });
    // Spent, budget and what's left are each spelled out on the row.
    expect(within(row).getByText("Spent")).toBeInTheDocument();
    expect(within(row).getByText("€ 120,00")).toBeInTheDocument();
    expect(within(row).getByText("€ 300,00")).toBeInTheDocument();
    expect(within(row).getByText("Left € 180,00")).toBeInTheDocument();
    // Over budget reads as such.
    const study = screen.getByRole("button", { name: "Studieschuld: transactions and settings" });
    expect(within(study).getByText("set budget")).toBeInTheDocument();
    expect(screen.getByLabelText("Pays off DUO")).toBeInTheDocument();
  });

  it("opens the category's transactions for the period when its tile is clicked", async () => {
    await openFoodDialog();
    await waitFor(() =>
      expect(griprApi.listTransactions).toHaveBeenCalledWith(expect.objectContaining({ categoryId: 1 })),
    );
    expect(screen.getByText("No transactions in this period.")).toBeInTheDocument();
  });

  it("editing the budget amount doesn't open the dialog", async () => {
    renderBudget();
    const tile = await screen.findByRole("button", { name: "Eten & Drinken: transactions and settings" });
    await userEvent.click(within(tile).getByTitle("Edit budget"));
    expect(screen.queryByText("Category settings")).not.toBeInTheDocument();
  });

  it("filters the dialog's transactions to one subcategory", async () => {
    await openFoodDialog();
    await userEvent.selectOptions(screen.getByLabelText("Subcategory"), "11");
    await waitFor(() =>
      expect(griprApi.listTransactions).toHaveBeenCalledWith(expect.objectContaining({ categoryId: 11 })),
    );
  });

  it("manages subcategories, archived ones included", async () => {
    await openFoodDialog();
    expect(screen.getByText("(archived)")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Unarchive Kroegen"));
    expect(griprApi.updateCategory).toHaveBeenCalledWith(12, { is_archived: false });

    await userEvent.type(screen.getByLabelText("New subcategory name"), "Lunch");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(griprApi.createCategory).toHaveBeenCalledWith({ name: "Lunch", kind: "expense", parent_id: 1 });
  });

  it("links the category to a loan", async () => {
    await openFoodDialog();
    await userEvent.selectOptions(screen.getByLabelText("Pays off a loan"), "50");
    expect(griprApi.updateCategory).toHaveBeenCalledWith(1, { linked_loan_account_id: 50 });
  });

  it("archives the category", async () => {
    await openFoodDialog();
    await userEvent.click(screen.getByRole("button", { name: "Archive" }));
    expect(griprApi.updateCategory).toHaveBeenCalledWith(1, { is_archived: true });
  });

  it("deletes the category only after confirming, and says transactions are kept", async () => {
    await openFoodDialog();
    const settings = screen.getByText("Category settings").parentElement!;
    await userEvent.click(within(settings).getByRole("button", { name: "Delete" }));
    expect(screen.getByText(/become uncategorized, not deleted/)).toBeInTheDocument();
    expect(screen.getByText(/2 subcategories will be deleted too/)).toBeInTheDocument();
    expect(griprApi.deleteCategory).not.toHaveBeenCalled();

    const confirmButtons = screen.getAllByRole("button", { name: "Delete" });
    await userEvent.click(confirmButtons[confirmButtons.length - 1]);
    await waitFor(() => expect(griprApi.deleteCategory).toHaveBeenCalledWith(1));
  });

  it("renames the category from its dialog", async () => {
    await openFoodDialog();
    await userEvent.click(screen.getByTitle("Edit category name"));
    const input = screen.getByDisplayValue("Eten & Drinken");
    await userEvent.clear(input);
    await userEvent.type(input, "Eten{Enter}");
    expect(griprApi.updateCategory).toHaveBeenCalledWith(1, { name: "Eten" });
  });

  it("adds a category from the tile at the end of the tab", async () => {
    renderBudget();
    await userEvent.click(await screen.findByRole("button", { name: "+ Add category" }));
    await userEvent.type(screen.getByRole("textbox"), "Reizen");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(griprApi.createCategory).toHaveBeenCalledWith({ name: "Reizen", kind: "expense", parent_id: null });
  });

  it("lists archived categories on request and opens them to unarchive", async () => {
    renderBudget();
    await userEvent.click(await screen.findByRole("button", { name: "Show 1 archived category" }));
    await userEvent.click(screen.getByRole("button", { name: /Hobby/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Unarchive" }));
    expect(griprApi.updateCategory).toHaveBeenCalledWith(3, { is_archived: false });
  });

  it("totals the tab at the bottom", async () => {
    renderBudget();
    const totals = await screen.findByRole("region", { name: "Totals" });
    expect(totals).toHaveTextContent("Spent this period");
    expect(totals).toHaveTextContent("€ 320,00");
    expect(totals).toHaveTextContent("of € 300,00");
    expect(totals).toHaveTextContent("Over by € 20,00");
  });

  it("keeps income categories on their own tab, without a loan link", async () => {
    renderBudget();
    await userEvent.click(await screen.findByRole("button", { name: "Income" }));
    await userEvent.click(await screen.findByRole("button", { name: "Salaris: transactions and settings" }));
    await screen.findByText("Category settings");
    expect(screen.queryByLabelText("Pays off a loan")).not.toBeInTheDocument();
  });
});
