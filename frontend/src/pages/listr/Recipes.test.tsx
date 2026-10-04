import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { listrApi } from "../../api/listrClient";
import type { ListrRecipe } from "../../api/listrTypes";
import ListrRecipes from "./Recipes";

vi.mock("../../api/listrClient", () => ({
  listrApi: {
    listRecipes: vi.fn(),
    listRecipeCategories: vi.fn(() => Promise.resolve([])),
    picnicStatus: vi.fn(() => Promise.resolve({ configured: false })),
    mealieStatus: vi.fn(() => Promise.resolve({ configured: false })),
    createRecipe: vi.fn(),
  },
}));

function recipe(id: number, title: string, servings: number | null, categories: ListrRecipe["categories"] = []): ListrRecipe {
  return {
    id, title, servings, instructions: "", notes: null, is_archived: false, created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z", ingredients: [], categories, mealie_id: null,
  };
}

describe("Recipes", () => {
  it("lists recipes as rows that open the recipe", async () => {
    vi.mocked(listrApi.listRecipes).mockResolvedValue([
      recipe(1, "Pasta pesto", 4, [{ id: 3, name: "Italiaans", color: "#e34948", sort_order: 0, is_archived: false }]),
      recipe(2, "Soep", null),
    ]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ListrRecipes />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const list = await screen.findByRole("list", { name: "Recepten" });
    const rows = within(list).getAllByRole("link");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveAttribute("href", "/listr/recept/1");
    expect(rows[0]).toHaveTextContent("Pasta pesto");
    expect(rows[0]).toHaveTextContent("4 personen");
    expect(rows[0]).toHaveTextContent("Italiaans");
    expect(rows[1]).toHaveTextContent("Personen onbekend");
  });
});
