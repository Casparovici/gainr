import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { griprApi } from "../../api/griprClient";
import OwedToYou from "./OwedToYou";

vi.mock("../../api/griprClient", () => ({ griprApi: { listReceivables: vi.fn(), writeOffReceivable: vi.fn() } }));

const PIZZA = {
  id: 480, date: "2026-06-26", amount: "57.60", notes: "SaaS Pizza", account_name: "Trade Republic", category_name: "Restaurants",
  expected_back: "57.60", expected_from: null, received: "0", outstanding: "57.60",
};

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OwedToYou />
    </QueryClientProvider>,
  );
}

describe("OwedToYou", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists what's owed with its total", async () => {
    vi.mocked(griprApi.listReceivables).mockResolvedValue({ total: "57.60", items: [PIZZA] });

    renderCard();

    expect(await screen.findByText("SaaS Pizza")).toBeInTheDocument();
    expect(screen.getByText(/0,00 of € 57,60 back/)).toBeInTheDocument();
  });

  it("stays hidden while nothing is owed", async () => {
    vi.mocked(griprApi.listReceivables).mockResolvedValue({ total: "0", items: [] });

    const { container } = renderCard();

    await vi.waitFor(() => expect(griprApi.listReceivables).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("writes off after saying what that means", async () => {
    vi.mocked(griprApi.listReceivables).mockResolvedValue({ total: "57.60", items: [PIZZA] });
    vi.mocked(griprApi.writeOffReceivable).mockResolvedValue({ total: "0", items: [] });
    renderCard();

    await userEvent.click(await screen.findByRole("button", { name: "Write off" }));
    expect(screen.getByText(/counts as your own spending/)).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Write off" }).at(-1)!);

    expect(griprApi.writeOffReceivable).toHaveBeenCalledWith(480);
  });
});
