import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listrApi } from "../../api/listrClient";
import type { ListrCategory, ListrItem } from "../../api/listrTypes";
import { readCollapsed } from "../../hooks/useCollapsedGroups";
import Producten from "./Producten";

vi.mock("../../api/listrClient", () => ({
  listrApi: {
    listCategories: vi.fn(),
    listItems: vi.fn(),
    picnicStatus: vi.fn(() => Promise.resolve({ configured: false, connected: false })),
  },
}));

const category = (id: number, name: string): ListrCategory => ({ id, name, sort_order: id, color: null, is_archived: false });

function item(id: number, name: string, categoryId: number): ListrItem {
  return {
    id, name, category_id: categoryId, category_name: null, default_unit: "stuks", is_archived: false,
    picnic_product_id: null, picnic_product_name: null, picnic_price: null, picnic_price_currency: null,
    picnic_unit_quantity: null, picnic_price_at: null, picnic_image_url: null,
    inventory_status: null, inventory_count: 0, inventory_minimum: 0,
  };
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Producten />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const header = (name: string) => screen.getByRole("button", { name: new RegExp(`^${name}`) });

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.mocked(listrApi.listCategories).mockResolvedValue([category(1, "Zuivel"), category(2, "Brood")]);
  vi.mocked(listrApi.listItems).mockResolvedValue([item(1, "Melk", 1), item(2, "Kaas", 1), item(3, "Volkorenbrood", 2)]);
});

describe("Producten: collapsing categories", () => {
  it("starts with every category open", async () => {
    renderPage();
    expect(await screen.findByText("Melk")).toBeVisible();
    expect(header("Zuivel")).toHaveAttribute("aria-expanded", "true");
  });

  it("folds a category away, with its products, and opens it again", async () => {
    renderPage();
    await screen.findByText("Melk");
    await userEvent.click(header("Zuivel"));
    expect(header("Zuivel")).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("Melk")).not.toBeVisible();
    expect(screen.getByText("Volkorenbrood")).toBeVisible();
    await userEvent.click(header("Zuivel"));
    expect(screen.getByText("Melk")).toBeVisible();
  });

  it("folds and opens every category at once", async () => {
    renderPage();
    await screen.findByText("Melk");
    await userEvent.click(screen.getByRole("button", { name: "Alles inklappen" }));
    expect(screen.getByText("Melk")).not.toBeVisible();
    expect(screen.getByText("Volkorenbrood")).not.toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Alles uitklappen" }));
    expect(screen.getByText("Melk")).toBeVisible();
  });

  it("remembers what was folded", async () => {
    const first = renderPage();
    await screen.findByText("Melk");
    await userEvent.click(header("Brood"));
    expect(readCollapsed("listr-collapsed-products")).toEqual(new Set([2]));
    first.unmount();
    renderPage();
    await screen.findByText("Melk");
    expect(header("Brood")).toHaveAttribute("aria-expanded", "false");
    expect(header("Zuivel")).toHaveAttribute("aria-expanded", "true");
  });
});
