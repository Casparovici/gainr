import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listrApi } from "../../api/listrClient";
import type { ListrListDetail, ListrListItem, ListrStore } from "../../api/listrTypes";
import { readCollapsed } from "../../hooks/useCollapsedGroups";
import ListrListDetailPage, { groupByCategory } from "./ListDetail";

vi.mock("../../api/listrClient", () => ({
  listrApi: {
    getList: vi.fn(),
    listStores: vi.fn(),
    listCategories: vi.fn(() => Promise.resolve([])),
    updateList: vi.fn(),
    updateListItem: vi.fn(),
    picnicStatus: vi.fn(() => Promise.resolve({ configured: false })),
    listItems: vi.fn(() => Promise.resolve([])),
  },
}));

function line(id: number, name: string, categoryId: number, categoryName: string): ListrListItem {
  return {
    id, list_id: 1, grocery_item_id: id, grocery_item_name: name, category_id: categoryId, category_name: categoryName,
    quantity: "1", unit: "stuks", is_checked: false, sort_order: id, picnic_product_id: null, picnic_product_name: null,
    picnic_price: null, picnic_unit_quantity: null, picnic_image_url: null,
  };
}

const ITEMS = [line(1, "Melk", 1, "Zuivel"), line(2, "Appels", 2, "Groente"), line(3, "Volkorenbrood", 3, "Brood"), line(4, "Kaas", 1, "Zuivel")];

function detail(overrides: Partial<ListrListDetail> = {}): ListrListDetail {
  return {
    id: 1, name: "Weekboodschappen", is_archived: false, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
    item_count: 4, checked_count: 0, store_id: null, items: ITEMS, category_order: [1, 2, 3], ...overrides,
  };
}

const jumbo: ListrStore = { id: 7, name: "Jumbo", sort_order: 1, is_archived: false, category_ids: [3, 2], category_order: [3, 2, 1] };

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/listr/lijst/1"]}>
        <Routes>
          <Route path="/listr/lijst/:id" element={<ListrListDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const groupNames = () => screen.getAllByText(/^(Zuivel|Groente|Brood)$/, { selector: "span.text-\\[15px\\]" }).map((e) => e.textContent);

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.mocked(listrApi.listStores).mockResolvedValue([jumbo]);
  vi.mocked(listrApi.getList).mockResolvedValue(detail());
});

describe("groupByCategory", () => {
  it("puts the groups in the order the server gives, a category it doesn't know last", () => {
    const groups = groupByCategory(ITEMS, [3, 1]);

    expect(groups.map((g) => g.categoryName)).toEqual(["Brood", "Zuivel", "Groente"]);
    expect(groups[1].items.map((i) => i.grocery_item_name)).toEqual(["Melk", "Kaas"]);
  });

  it("orders unknown categories by name among themselves", () => {
    expect(groupByCategory(ITEMS, []).map((g) => g.categoryName)).toEqual(["Brood", "Groente", "Zuivel"]);
  });
});

describe("a list and its store", () => {
  it("shows the groups in the list's category order", async () => {
    vi.mocked(listrApi.getList).mockResolvedValue(detail({ store_id: 7, category_order: [3, 2, 1] }));
    renderPage();

    await screen.findByText("Weekboodschappen");
    expect(groupNames()).toEqual(["Brood", "Groente", "Zuivel"]);
    expect(screen.getByLabelText("Winkel")).toHaveValue("7");
  });

  it("follows the standard order when it has no store", async () => {
    renderPage();

    await screen.findByText("Weekboodschappen");
    expect(groupNames()).toEqual(["Zuivel", "Groente", "Brood"]);
    expect(screen.getByLabelText("Winkel")).toHaveValue("");
  });

  it("sets the store the list follows", async () => {
    vi.mocked(listrApi.updateList).mockResolvedValue({ ...detail(), store_id: 7 });
    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText("Winkel"), "Jumbo");

    await waitFor(() => expect(listrApi.updateList).toHaveBeenCalledWith(1, { store_id: 7 }));
  });

  it("goes back to the standard order", async () => {
    vi.mocked(listrApi.getList).mockResolvedValue(detail({ store_id: 7, category_order: [3, 2, 1] }));
    vi.mocked(listrApi.updateList).mockResolvedValue(detail());
    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText("Winkel"), "Standaard volgorde");

    await waitFor(() => expect(listrApi.updateList).toHaveBeenCalledWith(1, { store_id: null }));
  });

  it("opens the stores sheet instead of choosing a store from the last option", async () => {
    renderPage();

    await userEvent.selectOptions(await screen.findByLabelText("Winkel"), "Winkels beheren…");

    expect(await screen.findByRole("dialog", { name: "Winkels" })).toBeInTheDocument();
    expect(listrApi.updateList).not.toHaveBeenCalled();
  });
});

describe("collapsing categories", () => {
  const header = (name: string) => screen.getByRole("button", { name: new RegExp(`^${name}`) });

  it("starts with every category open", async () => {
    renderPage();
    expect(await screen.findByRole("checkbox", { name: "Melk" })).toBeVisible();
    expect(header("Zuivel")).toHaveAttribute("aria-expanded", "true");
  });

  it("folds a category away and opens it again, leaving the others", async () => {
    renderPage();
    await screen.findByRole("checkbox", { name: "Melk" });
    await userEvent.click(header("Zuivel"));
    expect(header("Zuivel")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("checkbox", { name: "Melk" })).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Appels" })).toBeVisible();
    await userEvent.click(header("Zuivel"));
    expect(screen.getByRole("checkbox", { name: "Melk" })).toBeVisible();
  });

  it("still counts what's ticked in a folded category", async () => {
    vi.mocked(listrApi.getList).mockResolvedValue(
      detail({ items: ITEMS.map((i) => (i.id === 1 ? { ...i, is_checked: true } : i)), checked_count: 1 }),
    );
    renderPage();
    await screen.findByRole("checkbox", { name: "Melk" });
    await userEvent.click(header("Zuivel"));
    expect(header("Zuivel")).toHaveTextContent("1 / 2");
  });

  it("folds and opens every category at once", async () => {
    renderPage();
    await screen.findByRole("checkbox", { name: "Melk" });
    await userEvent.click(screen.getByRole("button", { name: "Alles inklappen" }));
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Alles uitklappen" }));
    expect(screen.getAllByRole("checkbox")).toHaveLength(4);
  });

  it("remembers what was folded on this list", async () => {
    const first = renderPage();
    await screen.findByRole("checkbox", { name: "Melk" });
    await userEvent.click(header("Brood"));
    expect(readCollapsed("listr-collapsed-1")).toEqual(new Set([3]));
    first.unmount();
    renderPage();
    await screen.findByRole("checkbox", { name: "Melk" });
    expect(header("Brood")).toHaveAttribute("aria-expanded", "false");
    expect(header("Zuivel")).toHaveAttribute("aria-expanded", "true");
  });

  it("ignores a stored value it can't read", () => {
    localStorage.setItem("listr-collapsed-1", "not json");
    expect(readCollapsed("listr-collapsed-1")).toEqual(new Set());
    localStorage.setItem("listr-collapsed-1", '["x", 2]');
    expect(readCollapsed("listr-collapsed-1")).toEqual(new Set([2]));
  });

  it("ticks an item from its name, not only from the checkbox", async () => {
    vi.mocked(listrApi.updateListItem).mockResolvedValue(ITEMS[0]);
    renderPage();
    const row = (await screen.findByRole("checkbox", { name: "Melk" })).closest("li") as HTMLElement;
    await userEvent.click(within(row).getByText("Melk"));
    expect(listrApi.updateListItem).toHaveBeenCalledWith(1, 1, { is_checked: true });
  });
});
