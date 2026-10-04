import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listrApi } from "../../api/listrClient";
import type { ListrItem } from "../../api/listrTypes";
import MealieImportDialog from "./MealieImportDialog";

vi.mock("../../api/listrClient", () => ({
  listrApi: {
    mealiePreview: vi.fn(),
    mealieImport: vi.fn(),
    listItems: vi.fn(),
    listCategories: vi.fn(),
    createItem: vi.fn(),
  },
}));

const currypasta = { id: 42, name: "Currypasta", category_name: "Kruiden, Sauzen & Olie" } as ListrItem;

function renderDialog() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MealieImportDialog onClose={() => {}} />
    </QueryClientProvider>,
  );
}

describe("MealieImportDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listrApi.listItems).mockResolvedValue([currypasta]);
    vi.mocked(listrApi.listCategories).mockResolvedValue([]);
    vi.mocked(listrApi.mealiePreview).mockResolvedValue({
      recipes: [
        { mealie_id: "m-1", name: "Frikandelbroodjes", status: "new" },
        { mealie_id: "m-2", name: "Omelet", status: "unchanged" },
      ],
      unmatched_foods: [
        { food_id: "f-ei", name: "ei", recipe_names: ["Frikandelbroodjes"], suggested_item_id: 7, suggested_item_name: "Eieren" },
        { food_id: "f-curry", name: "currysaus", recipe_names: ["Frikandelbroodjes"], suggested_item_id: null, suggested_item_name: null },
      ],
    });
    vi.mocked(listrApi.mealieImport).mockResolvedValue({ created: 1, updated: 0, unchanged: 1 });
  });

  it("pre-selects suggestions and only imports once every ingredient has a product", async () => {
    renderDialog();

    expect(await screen.findByText("✓ Eieren")).toBeInTheDocument();
    const importButton = screen.getByRole("button", { name: "Importeren (1)" });
    expect(importButton).toBeDisabled();
    expect(screen.getByText("Nog 1 ingrediënt te koppelen")).toBeInTheDocument();

    // "currysaus" has no suggestion: its search box starts with the name, pick a product.
    const search = screen.getByDisplayValue("currysaus");
    await userEvent.clear(search);
    await userEvent.type(search, "curry");
    await userEvent.click(await screen.findByRole("button", { name: /Currypasta/ }));

    expect(importButton).toBeEnabled();
    await userEvent.click(importButton);

    await waitFor(() =>
      expect(listrApi.mealieImport).toHaveBeenCalledWith([
        { food_id: "f-ei", grocery_item_id: 7 },
        { food_id: "f-curry", grocery_item_id: 42 },
      ]),
    );
    expect(await screen.findByText(/1 recept toegevoegd, 0 bijgewerkt, 1 al up-to-date/)).toBeInTheDocument();
  });

  it("shows the server's own reason when Mealie can't be reached", async () => {
    vi.mocked(listrApi.mealiePreview).mockRejectedValue(new Error('502 Bad Gateway: {"detail":"Mealie weigerde de API-sleutel"}'));
    renderDialog();
    expect(await screen.findByText("Mealie weigerde de API-sleutel")).toBeInTheDocument();
  });
});
