import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { gardnrApi } from "../../api/gardnrClient";
import type { GardenPlant, GardenPlantListRow } from "../../api/gardnrTypes";
import GardnrPlants from "./Plants";

vi.mock("../../api/gardnrClient", () => ({
  gardnrApi: {
    listPlants: vi.fn(),
    listAreas: vi.fn(),
    createPlant: vi.fn(),
    getPlantDetail: vi.fn(),
  },
}));

function row(id: number, name: string, species: string | null, area_id: number, area_name: string): GardenPlantListRow {
  return {
    id, area_id, area_name, name, species, type: "plant", status: "thriving", is_archived: false,
    next_action: null, is_overdue: false, scheduled_actions: [],
  };
}

function renderPlants() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <GardnrPlants />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GardnrPlants", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(gardnrApi.listPlants).mockResolvedValue([
      row(1, "Tomaat", "Solanum lycopersicum", 1, "Achtertuin"),
      row(2, "Blauwe Regen", "Wisteria", 1, "Achtertuin"),
      row(3, "Hortensia", null, 2, "Voortuin"),
    ]);
    vi.mocked(gardnrApi.listAreas).mockResolvedValue([
      { id: 1, name: "Achtertuin", sort_order: 1, plant_count: 2, overdue_count: 0 },
      { id: 2, name: "Voortuin", sort_order: 2, plant_count: 1, overdue_count: 0 },
    ]);
  });

  it("filters by name or species, and by garden", async () => {
    renderPlants();
    const cards = await screen.findByRole("list", { name: "Planten" });
    expect(within(cards).getAllByRole("listitem")).toHaveLength(3);

    await userEvent.type(screen.getByLabelText("Zoeken"), "wister");
    expect(within(cards).getAllByRole("listitem")).toHaveLength(1);
    expect(within(cards).getByText("Blauwe Regen")).toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText("Zoeken"));
    await userEvent.selectOptions(screen.getByLabelText("Tuin"), "2");
    expect(within(cards).getAllByRole("listitem")).toHaveLength(1);
    expect(within(cards).getByText("Hortensia")).toBeInTheDocument();
  });

  it("adds a plant to a chosen garden without a map position", async () => {
    vi.mocked(gardnrApi.createPlant).mockResolvedValue({ id: 9, area_id: 2 } as GardenPlant);
    renderPlants();
    await screen.findByRole("list", { name: "Planten" });

    await userEvent.click(screen.getAllByRole("button", { name: "Nieuwe plant" })[0]);
    await userEvent.type(screen.getByPlaceholderText("Naam"), "Lavendel");
    await userEvent.selectOptions(within(screen.getByPlaceholderText("Naam").closest("form")!).getByLabelText("Tuin"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Plant toevoegen" }));

    await waitFor(() =>
      expect(gardnrApi.createPlant).toHaveBeenCalledWith({ area_id: 2, name: "Lavendel", type: "plant", species: undefined }),
    );
  });
});
