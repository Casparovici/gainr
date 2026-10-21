import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { griprApi } from "../../api/griprClient";
import DepreciationCard from "./DepreciationCard";

vi.mock("../../api/griprClient", () => ({ griprApi: { getDepreciation: vi.fn() } }));

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DepreciationCard />
    </QueryClientProvider>,
  );
}

describe("DepreciationCard", () => {
  it("shows each asset's pace and what the fund covers", async () => {
    vi.mocked(griprApi.getDepreciation).mockResolvedValue({
      assets: [
        { account_id: 29, name: "Ford Focus", value: "6800.00", monthly: "96.00", months_left: 70 },
        { account_id: 30, name: "Peugeot 107", value: "500.00", monthly: "25.00", months_left: 20 },
      ],
      funds: [{ account_id: 11, name: "Afschrijving Auto", balance: "1800.00", assets_value: "7300.00", monthly: "121.00", covers_pct: "24.7" }],
    });

    renderCard();

    const card = await screen.findByRole("region", { name: "Depreciation" });
    expect(card).toHaveTextContent("Ford Focus");
    expect(card).toHaveTextContent("€ 6.800,00");
    expect(card).toHaveTextContent("−€ 96,00 a month · 70 months left");
    expect(card).toHaveTextContent("Afschrijving Auto");
    expect(card).toHaveTextContent("covers 24,7% of the value");
  });

  it("stays hidden until a transfer is a depreciation", async () => {
    vi.mocked(griprApi.getDepreciation).mockResolvedValue({ assets: [], funds: [] });

    const { container } = renderCard();

    await vi.waitFor(() => expect(griprApi.getDepreciation).toHaveBeenCalled());
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
