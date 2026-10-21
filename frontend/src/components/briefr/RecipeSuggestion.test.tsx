import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { briefrApi } from "../../api/briefrClient";
import type { BriefrItem, BriefrRecipe } from "../../api/briefrTypes";
import { listrApi } from "../../api/listrClient";
import RecipeSuggestion from "./RecipeSuggestion";

vi.mock("../../api/briefrClient", () => ({ briefrApi: { planItem: vi.fn() } }));
vi.mock("../../api/listrClient", () => ({ listrApi: { listMealPlan: vi.fn() } }));

// Friday 23 October 2026, the morning the home chef's report lands.
const NOW = new Date(2026, 9, 23, 8, 0);

const recipe: BriefrRecipe = {
  url: "https://www.leukerecepten.nl/recepten/pasta/",
  servings: 4,
  minutes: 25,
  ingredients: [
    { name: "Penne", quantity: "400", unit: "gram", note: null },
    { name: "Sojasaus", quantity: "1.5", unit: "el", note: "licht" },
  ],
  steps: ["Kook de pasta.", "Meng alles."],
  listr_recipe_id: null,
  planned_on: [],
};

const item: BriefrItem = {
  id: 5, symbol: null, asset_id: null, verdict: "watch", headline: "Pasta met zalm", detail: "Snel klaar.",
  sources: [recipe.url], recipe,
};

function renderSuggestion(r: BriefrRecipe = recipe) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ul>
          <RecipeSuggestion item={{ ...item, recipe: r }} recipe={r} now={NOW} />
        </ul>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listrApi.listMealPlan).mockResolvedValue([
    { date: "2026-10-24", recipe_id: 3, recipe_title: "Stamppot", leftover_id: null, leftover_name: null, is_cooked: false, notes: null },
  ]);
  vi.mocked(briefrApi.planItem).mockResolvedValue({ ...item, recipe: { ...recipe, listr_recipe_id: 9, planned_on: ["2026-10-26"] } });
});

describe("RecipeSuggestion", () => {
  it("shows the recipe with its facts, source, ingredients and steps", () => {
    renderSuggestion();
    expect(screen.getByText("Pasta met zalm")).toBeInTheDocument();
    expect(screen.getByText("4 servings")).toBeInTheDocument();
    expect(screen.getByText("25 min")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /leukerecepten\.nl/ })).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText("1,5 el Sojasaus (licht)")).toBeInTheDocument();
    expect(screen.getByText("Meng alles.")).toBeInTheDocument();
  });

  it("plans a free day at once", async () => {
    renderSuggestion();
    await userEvent.click(screen.getByRole("button", { name: "Plan in listr" }));
    expect(listrApi.listMealPlan).toHaveBeenCalledWith("2026-10-23", "2026-11-05");
    await userEvent.click(await screen.findByRole("button", { name: /Mon 26 Oct/ }));
    expect(briefrApi.planItem).toHaveBeenCalledWith(5, "2026-10-26", false);
  });

  it("asks before replacing what's already planned on a day", async () => {
    renderSuggestion();
    await userEvent.click(screen.getByRole("button", { name: "Plan in listr" }));
    await userEvent.click(await screen.findByRole("button", { name: /Tomorrow\s*Stamppot/ }));
    expect(screen.getByText("Tomorrow already has Stamppot. Replace it?")).toBeInTheDocument();
    expect(briefrApi.planItem).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Replace" }));
    expect(briefrApi.planItem).toHaveBeenCalledWith(5, "2026-10-24", true);
  });

  it("says when planning failed", async () => {
    vi.mocked(briefrApi.planItem).mockRejectedValue(new Error("500"));
    renderSuggestion();
    await userEvent.click(screen.getByRole("button", { name: "Plan in listr" }));
    await userEvent.click(await screen.findByRole("button", { name: /Today/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't plan the recipe. Try again.");
  });

  it("says when the weekplanner can't be loaded", async () => {
    vi.mocked(listrApi.listMealPlan).mockRejectedValue(new Error("500"));
    renderSuggestion();
    await userEvent.click(screen.getByRole("button", { name: "Plan in listr" }));
    expect(await screen.findByText("Couldn't load the weekplanner.")).toBeInTheDocument();
  });

  it("shows where a planned suggestion is, with links into listr", () => {
    renderSuggestion({ ...recipe, listr_recipe_id: 9, planned_on: ["2026-10-20", "2026-10-26"] });
    expect(screen.getByText(/Planned for Mon 26 Oct/)).toBeInTheDocument();
    expect(screen.queryByText(/Tue 20 Oct/)).not.toBeInTheDocument(); // already past
    expect(screen.getByRole("link", { name: "Open recipe" })).toHaveAttribute("href", "/listr/recept/9");
    expect(screen.getByRole("link", { name: "Open weekplanner" })).toHaveAttribute("href", "/listr/weekplanner");
    expect(screen.getByRole("button", { name: "Plan another day" })).toBeInTheDocument();
  });
});
