import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { listrApi } from "../../api/listrClient";
import type { ListrItem } from "../../api/listrTypes";
import ListrInventory from "./Inventory";

vi.mock("../../api/listrClient", () => ({
  listrApi: {
    listInventory: vi.fn(),
    listLeftovers: vi.fn().mockResolvedValue([]),
    setItemInventoryTracking: vi.fn(),
    adjustInventoryMinimum: vi.fn(),
    adjustInventoryCount: vi.fn(),
    addInventoryToList: vi.fn(),
    listItems: vi.fn(),
    listCategories: vi.fn(),
    createItem: vi.fn(),
  },
}));

const ovenfrites: ListrItem = {
  id: 316,
  name: "Ovenfrites",
  category_id: 10,
  category_name: "Diepvries",
  default_unit: "stuks",
  is_archived: false,
  picnic_product_id: null,
  picnic_product_name: null,
  picnic_price: null,
  picnic_price_currency: null,
  picnic_unit_quantity: null,
  picnic_price_at: null,
  picnic_image_url: null,
  inventory_status: "out",
  inventory_count: 0,
  inventory_minimum: 1,
};

function renderInventory() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/listr/voorraad"]}>
        <ListrInventory />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ListrInventory status dot", () => {
  it("recomputes the dot from the optimistic count bump, not just after the server round-trip", async () => {
    vi.mocked(listrApi.listInventory).mockResolvedValue([ovenfrites]);
    vi.mocked(listrApi.listItems).mockResolvedValue([]);
    vi.mocked(listrApi.listCategories).mockResolvedValue([]);
    // Deliberately never resolves during this test -- if the dot only turned green once this
    // settled, this assertion would time out, proving the fix works off the local optimistic
    // patch rather than a refetch.
    vi.mocked(listrApi.adjustInventoryCount).mockReturnValue(new Promise(() => {}));

    renderInventory();

    expect(await screen.findByTitle("Op")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Een meer"));

    expect(await screen.findByTitle("Op voorraad")).toBeInTheDocument();
    expect(screen.queryByTitle("Op")).not.toBeInTheDocument();
  });

  it("recomputes the dot from an optimistic minimum bump the same way", async () => {
    const stocked: ListrItem = { ...ovenfrites, inventory_count: 2, inventory_minimum: 2, inventory_status: "in_stock" };
    vi.mocked(listrApi.listInventory).mockResolvedValue([stocked]);
    vi.mocked(listrApi.listItems).mockResolvedValue([]);
    vi.mocked(listrApi.listCategories).mockResolvedValue([]);
    vi.mocked(listrApi.adjustInventoryMinimum).mockReturnValue(new Promise(() => {}));

    renderInventory();

    expect(await screen.findByTitle("Op voorraad")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Minimum een hoger"));

    expect(await screen.findByTitle("Bijna op")).toBeInTheDocument();
    expect(screen.queryByTitle("Op voorraad")).not.toBeInTheDocument();
  });
});
