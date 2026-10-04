import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { Asset, TransactionInput } from "../api/types";
import TransactionForm from "./TransactionForm";

vi.mock("../api/client", () => ({ api: { lookupAsset: vi.fn(), createAsset: vi.fn() } }));

function renderForm(opts: { brokers?: string[]; onSubmit?: (input: TransactionInput) => void } = {}) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <TransactionForm
        assets={[]}
        brokers={opts.brokers ?? []}
        initial={undefined}
        portfolioId={1}
        onCancel={vi.fn()}
        onSubmit={opts.onSubmit ?? vi.fn()}
        isSubmitting={false}
      />
    </QueryClientProvider>,
  );
}

// The symbol lookup waits out a typing debounce; on a busy CI runner that can take seconds.
vi.setConfig({ testTimeout: 15_000 });

describe("TransactionForm's auto-calculated Total", () => {
  it("adds costs to the total on a Buy", async () => {
    renderForm();
    // Type defaults to Buy.
    await userEvent.type(screen.getByLabelText("Value (EUR)"), "1000");
    await userEvent.type(screen.getByLabelText("Costs (EUR)"), "5");

    expect(screen.getByLabelText("Total (EUR)")).toHaveValue("1005");
  });

  it("subtracts costs from the total on a Sell -- the broker deducts them from what it pays out", async () => {
    renderForm();
    await userEvent.selectOptions(screen.getByLabelText("Type"), "Sell");
    await userEvent.type(screen.getByLabelText("Value (EUR)"), "1000");
    await userEvent.type(screen.getByLabelText("Costs (EUR)"), "5");

    expect(screen.getByLabelText("Total (EUR)")).toHaveValue("995");
  });

  it("re-derives the total with the new sign when switching an existing Buy to a Sell", async () => {
    renderForm();
    await userEvent.type(screen.getByLabelText("Value (EUR)"), "1000");
    await userEvent.type(screen.getByLabelText("Costs (EUR)"), "5");
    expect(screen.getByLabelText("Total (EUR)")).toHaveValue("1005");

    await userEvent.selectOptions(screen.getByLabelText("Type"), "Sell");

    expect(screen.getByLabelText("Total (EUR)")).toHaveValue("995");
  });
});

describe("TransactionForm's Transfer type", () => {
  it("has no asset or quantity, and relabels Broker to From broker with a second To broker field", async () => {
    renderForm();

    await userEvent.selectOptions(screen.getByLabelText("Type"), "Transfer");

    expect(screen.queryByLabelText("Asset")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Quantity")).not.toBeInTheDocument();
    expect(screen.getByLabelText("From broker")).toBeInTheDocument();
    expect(screen.getByLabelText("To broker")).toBeInTheDocument();
  });

  it("excludes the selected From broker from the To broker options", async () => {
    renderForm({ brokers: ["DEGIRO", "IBKR"] });

    await userEvent.selectOptions(screen.getByLabelText("Type"), "Transfer");
    await userEvent.selectOptions(screen.getByLabelText("From broker"), "DEGIRO");

    const toBrokerOptionLabels = within(screen.getByLabelText("To broker"))
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(toBrokerOptionLabels).not.toContain("DEGIRO");
    expect(toBrokerOptionLabels).toContain("IBKR");
  });

  it("submits a Transfer with no asset, the two brokers, and the amount as total_eur", async () => {
    const onSubmit = vi.fn();
    renderForm({ brokers: ["DEGIRO", "IBKR"], onSubmit });

    await userEvent.selectOptions(screen.getByLabelText("Type"), "Transfer");
    await userEvent.selectOptions(screen.getByLabelText("From broker"), "DEGIRO");
    await userEvent.selectOptions(screen.getByLabelText("To broker"), "IBKR");
    await userEvent.type(screen.getByLabelText("Amount (EUR)"), "500");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "Transfer",
        asset_id: null,
        broker: "DEGIRO",
        to_broker: "IBKR",
        total_eur: "500",
      }),
    );
  });
});


describe("TransactionForm's new asset", () => {
  it("prices it from the listing picked, and lets an auto-filled name follow the pick", async () => {
    vi.mocked(api.lookupAsset).mockResolvedValue({
      query: "TDIV",
      exact: true,
      matches: [
        { symbol: "TDIV", name: "First Trust NASDAQ Technology Dividend Index Fund", exchange: "NASDAQ", quote_type: "ETF" },
        { symbol: "TDIV.AS", name: "VanEck Morningstar Developed Markets Dividend Leaders UCITS ETF", exchange: "Amsterdam", quote_type: "ETF" },
      ],
    });
    vi.mocked(api.createAsset).mockResolvedValue({ id: 99 } as Asset);
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.click(screen.getByPlaceholderText("Search ticker or name…"));
    await userEvent.click(screen.getByText("+ Add new asset…"));
    await userEvent.type(screen.getByPlaceholderText("Ticker (e.g. AAPL)"), "TDIV");
    expect(await screen.findByDisplayValue(/First Trust NASDAQ/, {}, { timeout: 8000 })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("radio", { name: /TDIV\.AS · Amsterdam/ }));
    expect(screen.getByPlaceholderText("Name")).toHaveValue("VanEck Morningstar Developed Markets Dividend Leaders UCITS ETF");

    await userEvent.type(screen.getByLabelText("Value (EUR)"), "121");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(api.createAsset).toHaveBeenCalledWith(expect.objectContaining({ ticker: "TDIV", yahoo_symbol: "TDIV.AS" }));
  });
});
