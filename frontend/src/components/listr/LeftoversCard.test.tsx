import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { listrApi } from "../../api/listrClient";
import type { ListrLeftover } from "../../api/listrTypes";
import LeftoversCard from "./LeftoversCard";

vi.mock("../../api/listrClient", () => ({
  listrApi: {
    listLeftovers: vi.fn(),
    createLeftover: vi.fn(),
    adjustLeftoverMeals: vi.fn(),
    deleteLeftover: vi.fn(),
    listRecipes: vi.fn().mockResolvedValue([]),
  },
}));

function daysFromToday(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const bolognese: ListrLeftover = {
  id: 1,
  name: "Bolognese",
  recipe_id: null,
  meals: 2,
  servings_per_meal: 4,
  location: "freezer",
  stored_on: daysFromToday(0),
  use_by: daysFromToday(60),
};

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <LeftoversCard />
    </QueryClientProvider>,
  );
}

describe("LeftoversCard", () => {
  it("shows an empty state", async () => {
    vi.mocked(listrApi.listLeftovers).mockResolvedValue([]);
    renderCard();
    expect(await screen.findByText(/Geen restjes/)).toBeInTheDocument();
  });

  it("shows an error state", async () => {
    vi.mocked(listrApi.listLeftovers).mockRejectedValue(new Error("boom"));
    renderCard();
    expect(await screen.findByText(/Restjes laden mislukt/)).toBeInTheDocument();
  });

  it("lists a batch with its meals, people and location", async () => {
    vi.mocked(listrApi.listLeftovers).mockResolvedValue([bolognese]);
    renderCard();
    expect(await screen.findByText("Bolognese")).toBeInTheDocument();
    expect(screen.getByText(/Vriezer · 4 pers\./)).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("flags a batch that expires soon and one that already has", async () => {
    vi.mocked(listrApi.listLeftovers).mockResolvedValue([
      { ...bolognese, id: 1, name: "Soep", use_by: daysFromToday(2) },
      { ...bolognese, id: 2, name: "Chili", use_by: daysFromToday(-1) },
    ]);
    renderCard();
    expect(await screen.findByText("Nog 2 dagen")).toBeInTheDocument();
    expect(screen.getByText(/Verlopen/)).toBeInTheDocument();
  });

  it("takes a meal off with the minus button", async () => {
    vi.mocked(listrApi.listLeftovers).mockResolvedValue([bolognese]);
    vi.mocked(listrApi.adjustLeftoverMeals).mockResolvedValue({ ...bolognese, meals: 1 });
    renderCard();
    await userEvent.click(await screen.findByLabelText("Een maaltijd minder"));
    await waitFor(() => expect(listrApi.adjustLeftoverMeals).toHaveBeenCalledWith(1, -1));
  });

  it("stores a new batch, leaving use-by blank for the server to default", async () => {
    vi.mocked(listrApi.listLeftovers).mockResolvedValue([]);
    vi.mocked(listrApi.createLeftover).mockResolvedValue(bolognese);
    renderCard();
    await userEvent.click(await screen.findByText("Bewaren"));
    await userEvent.type(screen.getByLabelText("Naam"), "Bolognese");
    await userEvent.click(screen.getByRole("button", { name: "Opslaan" }));
    await waitFor(() =>
      expect(listrApi.createLeftover).toHaveBeenCalledWith({
        name: "Bolognese",
        recipe_id: null,
        meals: 2,
        servings_per_meal: 4,
        location: "freezer",
        use_by: null,
      }),
    );
  });
});
