import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { SymbolMatch } from "../api/types";
import AssetSymbolPicker from "./AssetSymbolPicker";

vi.mock("../api/client", () => ({ api: { lookupAsset: vi.fn() } }));

const FIRST_TRUST: SymbolMatch = { symbol: "TDIV", name: "First Trust NASDAQ Technology Dividend Index Fund", exchange: "NASDAQ", quote_type: "ETF" };
const VANECK: SymbolMatch = { symbol: "TDIV.AS", name: "VanEck Morningstar Developed Markets Dividend Leaders UCITS ETF", exchange: "Amsterdam", quote_type: "ETF" };
const XETRA: SymbolMatch = { symbol: "IQQW.DE", name: "iShares MSCI World UCITS ETF USD (Dist)", exchange: "XETRA", quote_type: "ETF" };

function Harness({ ticker, onPick }: { ticker: string; onPick: (symbol: string | null) => void }) {
  const [value, setValue] = useState<string | null>(null);
  return (
    <AssetSymbolPicker
      ticker={ticker}
      value={value}
      onChange={(symbol) => {
        setValue(symbol);
        onPick(symbol);
      }}
    />
  );
}

function renderPicker(ticker: string, onPick = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <Harness ticker={ticker} onPick={onPick} />
    </QueryClientProvider>,
  );
  return onPick;
}

// The symbol lookup waits out a typing debounce; on a busy CI runner that can take seconds.
vi.setConfig({ testTimeout: 15_000 });

describe("AssetSymbolPicker", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows which fund each listing is, pre-picks the exact one, and lets the reader pick another", async () => {
    vi.mocked(api.lookupAsset).mockResolvedValue({ query: "TDIV", exact: true, matches: [FIRST_TRUST, VANECK] });
    const onPick = renderPicker("TDIV");

    // The lookup waits out a typing debounce first; give it room on a busy test run.
    expect(await screen.findByText(/First Trust NASDAQ Technology/, {}, { timeout: 8000 })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /TDIV · NASDAQ/ })).toBeChecked();

    await userEvent.click(screen.getByRole("radio", { name: /TDIV\.AS · Amsterdam/ }));

    expect(onPick).toHaveBeenLastCalledWith("TDIV.AS");
  });

  it("picks the listing Yahoo does know when the bare ticker isn't one", async () => {
    vi.mocked(api.lookupAsset).mockResolvedValue({ query: "IQQW", exact: false, matches: [XETRA] });
    const onPick = renderPicker("IQQW");

    expect(await screen.findByRole("radio", { name: /IQQW\.DE · XETRA/ }, { timeout: 8000 })).toBeChecked();
    expect(onPick).toHaveBeenCalledWith("IQQW.DE");
  });

  it("warns before saving when Yahoo knows nothing by that name", async () => {
    vi.mocked(api.lookupAsset).mockResolvedValue({ query: "ZZZZ", exact: false, matches: [] });
    const onPick = renderPicker("ZZZZ");

    expect(await screen.findByText(/Yahoo doesn't know “ZZZZ”/, {}, { timeout: 8000 })).toBeInTheDocument();
    expect(onPick).toHaveBeenCalledWith(null);
  });

  it("waits for at least two characters", () => {
    renderPicker("T");
    expect(api.lookupAsset).not.toHaveBeenCalled();
  });
});
