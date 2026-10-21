import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { listrApi } from "../../api/listrClient";
import type { ListrRecipe } from "../../api/listrTypes";
import ListrRecipeDetail from "./RecipeDetail";

vi.mock("../../api/listrClient", () => ({ listrApi: { getRecipe: vi.fn() } }));
vi.mock("../../components/ModuleSwitcher", () => ({ default: () => null }));
vi.mock("../../components/ModuleIndicators", () => ({ default: () => null }));
vi.mock("../../components/ModuleSettingsButton", () => ({ default: () => null }));
vi.mock("../../components/notr/LinkedNotes", () => ({
  default: ({ recipeId }: { recipeId?: number }) => <div data-testid="linked-notes">notities van recept {recipeId}</div>,
}));

const recipe: ListrRecipe = {
  id: 5, title: "Pasta pesto", servings: 4, instructions: "Koken.", notes: "Meer basilicum", is_archived: false,
  created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z", ingredients: [], categories: [], has_photo: false, mealie_id: null, source_url: null,
};

describe("ListrRecipeDetail", () => {
  it("shows the recipe's own note and, apart from it, the notr notes linked to the recipe", async () => {
    vi.mocked(listrApi.getRecipe).mockResolvedValue(recipe);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/listr/recepten/5"]}>
          <Routes>
            <Route path="/listr/recepten/:id" element={<ListrRecipeDetail />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Meer basilicum")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Notities in notr" })).toContainElement(screen.getByTestId("linked-notes"));
    expect(screen.getByTestId("linked-notes")).toHaveTextContent("recept 5");
  });
});
