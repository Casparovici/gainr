import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render as rtlRender, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { griprApi } from "../../api/griprClient";
import type { GriprAccount, GriprCategory, GriprTransaction } from "../../api/griprTypes";
import GriprTransactionForm from "./GriprTransactionForm";

vi.mock("../../api/griprClient", () => ({
  griprApi: { listReceivables: vi.fn(), transactionAttachments: { key: "gripr", invalidates: [], list: vi.fn(), upload: vi.fn(), remove: vi.fn(), url: vi.fn() } },
}));

function render(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return rtlRender(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function account(id: number, name: string): GriprAccount {
  return {
    id, name, type: "checking", balance_mode: "transactional", opening_balance: "0", manual_balance: "0",
    is_archived: false, balance: "0", usage_count: 0, color: null, bank_logo_key: null, held_in_account_id: null,
  };
}

const accounts = [account(1, "Trade Republic"), account(2, "ING")];
const categories: GriprCategory[] = [
  { id: 10, name: "Eten & Drinken", kind: "expense", parent_id: null, is_archived: false, color: null, linked_loan_account_id: null },
  { id: 20, name: "Salaris", kind: "income", parent_id: null, is_archived: false, color: null, linked_loan_account_id: null },
];

const dinner: GriprTransaction = {
  id: 7, date: "2026-09-28", type: "expense", amount: "60.00", account_id: 1, counter_account_id: null,
  category_id: 10, refund_of_id: null, notes: "Dinner with Sam", account_name: "Trade Republic",
  counter_account_name: null, category_name: "Eten & Drinken", is_recurring: false, refunded_amount: "0", refund_of: null, expected_back: null, expected_from: null, outstanding: "0", attachment_count: 0,
};

describe("GriprTransactionForm refunds", () => {
  beforeEach(() => {
    vi.mocked(griprApi.listReceivables).mockResolvedValue({ total: "0", items: [] });
  });

  it("offers 'Got money back' while editing an expense", async () => {
    const onAddRefund = vi.fn();
    render(
      <GriprTransactionForm
        accounts={accounts} categories={categories} initial={dinner} onAddRefund={onAddRefund}
        onCancel={vi.fn()} onSubmit={vi.fn()} isSubmitting={false}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Got money back" }));
    expect(onAddRefund).toHaveBeenCalledWith(dinner);
  });

  it("prefills a linked refund for half the expense, in its category, and submits the link", async () => {
    const onSubmit = vi.fn();
    render(
      <GriprTransactionForm
        accounts={accounts} categories={categories} initial={undefined} refundOf={dinner}
        onCancel={vi.fn()} onSubmit={onSubmit} isSubmitting={false}
      />,
    );
    expect(screen.getByText("Add refund")).toBeInTheDocument();
    expect(screen.getByText(/Dinner with Sam/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("30,00")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Received in"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ type: "refund", account_id: 2, category_id: 10, refund_of_id: 7, amount: "30" }),
      [],
    );
  });

  it("drops the link on Unlink, keeping the refund itself", async () => {
    const onSubmit = vi.fn();
    render(
      <GriprTransactionForm
        accounts={accounts} categories={categories} initial={undefined} refundOf={dinner}
        onCancel={vi.fn()} onSubmit={onSubmit} isSubmitting={false}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Unlink" }));
    await userEvent.selectOptions(screen.getByLabelText("Received in"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ type: "refund", refund_of_id: null, category_id: 10 }), []);
  });

  it("lists only expense categories for a refund", async () => {
    render(
      <GriprTransactionForm
        accounts={accounts} categories={categories} initial={undefined}
        onCancel={vi.fn()} onSubmit={vi.fn()} isSubmitting={false}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText("Type"), "refund");
    expect(screen.getByRole("option", { name: "Eten & Drinken" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Salaris" })).not.toBeInTheDocument();
  });

  it("saves what an expense expects back, and from whom", async () => {
    const onSubmit = vi.fn();
    render(
      <GriprTransactionForm
        accounts={accounts} categories={categories} initial={dinner}
        onCancel={vi.fn()} onSubmit={onSubmit} isSubmitting={false}
      />,
    );

    await userEvent.type(screen.getByLabelText("Expecting back (EUR)"), "45");
    await userEvent.type(screen.getByLabelText("From"), "Sam");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ type: "expense", expected_back: "45", expected_from: "Sam" }), []);
  });

  it("turns incoming money into the repayment of something still owed", async () => {
    vi.mocked(griprApi.listReceivables).mockResolvedValue({
      total: "45.00",
      items: [{
        id: 7, date: "2026-09-28", amount: "60.00", notes: "Dinner with Sam", account_name: "Trade Republic",
        category_name: "Eten & Drinken", expected_back: "45.00", expected_from: "Sam", received: "0", outstanding: "45.00",
      }],
    });
    const tikkie: GriprTransaction = {
      ...dinner, id: 9, type: "income", amount: "45.00", category_id: null, category_name: null, notes: "Tikkie Sam",
    };
    const onSubmit = vi.fn();
    render(
      <GriprTransactionForm
        accounts={accounts} categories={categories} initial={tikkie}
        onCancel={vi.fn()} onSubmit={onSubmit} isSubmitting={false}
      />,
    );

    await userEvent.selectOptions(await screen.findByLabelText("Money back for…"), "7");
    expect(screen.getByText("Money back for")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ type: "refund", refund_of_id: 7, expected_back: null }), []);
  });
});

describe("GriprTransactionForm attachments", () => {
  it("hands the files picked on a new transaction to onSubmit, to upload once it's saved", async () => {
    const onSubmit = vi.fn();
    render(
      <GriprTransactionForm
        accounts={accounts} categories={categories} initial={undefined} defaultAccountId={1}
        onCancel={vi.fn()} onSubmit={onSubmit} isSubmitting={false}
      />,
    );
    const receipt = new File(["%PDF-1.7"], "receipt.pdf", { type: "application/pdf" });

    await userEvent.upload(screen.getByLabelText("Choose files to attach"), receipt);
    await userEvent.type(screen.getByLabelText("Amount (EUR)"), "12");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ amount: "12" }), [receipt]);
  });
});
