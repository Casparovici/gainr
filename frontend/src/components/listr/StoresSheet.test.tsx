import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listrApi } from "../../api/listrClient";
import type { ListrCategory, ListrStore } from "../../api/listrTypes";
import StoresSheet from "./StoresSheet";

vi.mock("../../api/listrClient", () => ({
  listrApi: {
    listStores: vi.fn(),
    listCategories: vi.fn(),
    createStore: vi.fn(),
    renameStore: vi.fn(),
    setStoreOrder: vi.fn(),
    deleteStore: vi.fn(),
    reorderCategories: vi.fn(),
  },
}));

const category = (id: number, name: string): ListrCategory => ({ id, name, sort_order: id, color: null, is_archived: false });
const CATEGORIES = [category(1, "Zuivel"), category(2, "Groente"), category(3, "Brood")];
const store = (id: number, name: string, ids: number[] = [], order: number[] = [1, 2, 3]): ListrStore => ({
  id, name, sort_order: id, is_archived: false, category_ids: ids, category_order: order,
});

function renderSheet() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <StoresSheet onClose={() => {}} />
    </QueryClientProvider>,
  );
}

const names = () => within(screen.getByRole("list")).getAllByRole("listitem").map((li) => li.textContent?.replace(/^\d+/, "").trim());

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listrApi.listCategories).mockResolvedValue(CATEGORIES);
  vi.mocked(listrApi.listStores).mockResolvedValue([store(7, "Jumbo", [3, 2], [3, 2, 1])]);
});

describe("StoresSheet", () => {
  it("lists the stores and the standard order", async () => {
    renderSheet();

    expect(await screen.findByRole("button", { name: /Jumbo/ })).toHaveTextContent("2 gangen geordend");
    expect(screen.getByRole("button", { name: /Standaard volgorde/ })).toBeInTheDocument();
  });

  it("says what to do when there are no stores yet", async () => {
    vi.mocked(listrApi.listStores).mockResolvedValue([]);
    renderSheet();

    expect(await screen.findByText(/Nog geen winkels/)).toBeInTheDocument();
  });

  it("says so, with a retry, when the stores can't be loaded", async () => {
    vi.mocked(listrApi.listStores).mockRejectedValue(new Error("500"));
    renderSheet();

    expect(await screen.findByText("Kon de winkels niet laden.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /opnieuw/i })).toBeInTheDocument();
  });

  it("adds a store, optionally from another store's order, and opens it to arrange", async () => {
    vi.mocked(listrApi.createStore).mockResolvedValue(store(8, "Lidl", [3, 2], [3, 2, 1]));
    vi.mocked(listrApi.listStores).mockResolvedValueOnce([store(7, "Jumbo", [3, 2], [3, 2, 1])]).mockResolvedValue([
      store(7, "Jumbo", [3, 2], [3, 2, 1]),
      store(8, "Lidl", [3, 2], [3, 2, 1]),
    ]);
    renderSheet();

    await userEvent.type(await screen.findByPlaceholderText("Naam, bijvoorbeeld Jumbo"), "Lidl");
    await userEvent.selectOptions(screen.getByLabelText("Begin met de volgorde van"), "7");
    await userEvent.click(screen.getByRole("button", { name: "Winkel toevoegen" }));

    await waitFor(() => expect(listrApi.createStore).toHaveBeenCalledWith({ name: "Lidl", copy_order_from_id: 7 }));
    expect(await screen.findByRole("heading", { name: "Lidl" })).toBeInTheDocument();
  });

  it("explains a name that is taken", async () => {
    vi.mocked(listrApi.createStore).mockRejectedValue(new Error("409 Conflict: There is already a store called Jumbo"));
    renderSheet();

    await userEvent.type(await screen.findByPlaceholderText("Naam, bijvoorbeeld Jumbo"), "Jumbo");
    await userEvent.click(screen.getByRole("button", { name: "Winkel toevoegen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Er is al een winkel met die naam.");
  });

  it("shows a store's categories in its order and saves a move at once", async () => {
    vi.mocked(listrApi.setStoreOrder).mockResolvedValue(store(7, "Jumbo", [2, 3, 1], [2, 3, 1]));
    renderSheet();
    await userEvent.click(await screen.findByRole("button", { name: /Jumbo/ }));

    expect(names()).toEqual(["Brood", "Groente", "Zuivel"]);

    await userEvent.click(screen.getByRole("button", { name: "Brood later zetten" }));

    expect(names()).toEqual(["Groente", "Brood", "Zuivel"]);
    await waitFor(() => expect(listrApi.setStoreOrder).toHaveBeenCalledWith(7, [2, 3, 1]));
  });

  it("can't move the first category up or the last one down", async () => {
    renderSheet();
    await userEvent.click(await screen.findByRole("button", { name: /Jumbo/ }));

    expect(screen.getByRole("button", { name: "Brood eerder zetten" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Zuivel later zetten" })).toBeDisabled();
  });

  it("arranges the standard order through the categories' own order", async () => {
    vi.mocked(listrApi.reorderCategories).mockResolvedValue(undefined);
    renderSheet();
    await userEvent.click(await screen.findByRole("button", { name: /Standaard volgorde/ }));

    expect(names()).toEqual(["Zuivel", "Groente", "Brood"]);
    await userEvent.click(screen.getByRole("button", { name: "Brood eerder zetten" }));

    await waitFor(() => expect(listrApi.reorderCategories).toHaveBeenCalledWith([1, 3, 2]));
    expect(listrApi.setStoreOrder).not.toHaveBeenCalled();
  });

  it("deletes a store only after asking, and says what happens to its lists", async () => {
    vi.mocked(listrApi.deleteStore).mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderSheet();
    await userEvent.click(await screen.findByRole("button", { name: /Jumbo/ }));

    await userEvent.click(screen.getByRole("button", { name: "Winkel verwijderen…" }));
    expect(listrApi.deleteStore).not.toHaveBeenCalled();
    expect(confirm.mock.calls[0][0]).toContain("gaan terug naar de standaard volgorde");

    confirm.mockReturnValue(true);
    await userEvent.click(screen.getByRole("button", { name: "Winkel verwijderen…" }));
    await waitFor(() => expect(listrApi.deleteStore).toHaveBeenCalledWith(7));
  });

  it("renames a store", async () => {
    vi.mocked(listrApi.renameStore).mockResolvedValue(store(7, "Jumbo Zuid", [3, 2]));
    renderSheet();
    await userEvent.click(await screen.findByRole("button", { name: /Jumbo/ }));

    const field = screen.getByLabelText("Naam");
    await userEvent.clear(field);
    await userEvent.type(field, "Jumbo Zuid");
    await userEvent.click(screen.getByRole("button", { name: "Opslaan" }));

    await waitFor(() => expect(listrApi.renameStore).toHaveBeenCalledWith(7, "Jumbo Zuid"));
  });
});
