import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { gardnrApi } from "../../api/gardnrClient";
import { todayLocalISO } from "../../utils/gardnr";
import GardnrAreas from "./Areas";

vi.mock("../../api/gardnrClient", () => ({
  gardnrApi: {
    listAreas: vi.fn(),
    listPlants: vi.fn(),
    getAreaDetail: vi.fn(),
    reorderAreas: vi.fn(),
    updateArea: vi.fn(),
    deleteArea: vi.fn(),
    createArea: vi.fn(),
  },
}));

function renderAreas() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/gardnr"]}>
        <Routes>
          <Route path="/gardnr" element={<GardnrAreas />} />
          <Route path="/gardnr/areas/:id" element={<p>kaart geopend</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GardnrAreas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(gardnrApi.listAreas).mockResolvedValue([
      { id: 1, name: "Achtertuin", sort_order: 1, plant_count: 3, overdue_count: 0 },
      { id: 2, name: "Voortuin", sort_order: 2, plant_count: 1, overdue_count: 0 },
    ]);
    vi.mocked(gardnrApi.reorderAreas).mockResolvedValue(undefined);
    vi.mocked(gardnrApi.listPlants).mockResolvedValue([]);
    vi.mocked(gardnrApi.getAreaDetail).mockResolvedValue({ area: { id: 1, name: "x", sort_order: 1, plant_count: 0, overdue_count: 0 }, zones: [], plants: [] });
  });

  it("opens a garden when its name is tapped, instead of starting a rename", async () => {
    renderAreas();
    await userEvent.click(await screen.findByText("Achtertuin"));
    expect(screen.getByText("kaart geopend")).toBeInTheDocument();
  });

  it("reorders with buttons in edit mode, which a finger can use", async () => {
    renderAreas();
    await screen.findByText("Achtertuin");
    expect(screen.queryByRole("button", { name: "Achtertuin later zetten" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Bewerken/ }));
    expect(screen.getByRole("button", { name: "Achtertuin eerder zetten" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Achtertuin later zetten" }));

    await waitFor(() => expect(gardnrApi.reorderAreas).toHaveBeenCalledWith([2, 1]));
  });

  it("sums up the gardens and flags overdue and due-today work, per garden and in a banner", async () => {
    const today = todayLocalISO();
    const action = (date: string, overdue: boolean) => ({ schedule_id: 1, action_type: "water" as const, custom_label: null, date, is_overdue: overdue });
    const plant = (id: number, areaId: number, actions: ReturnType<typeof action>[]) => ({
      id, area_id: areaId, area_name: "", name: `Plant ${id}`, species: null, type: "plant" as const, status: "thriving" as const,
      is_archived: false, next_action: actions[0] ?? null, is_overdue: actions.some((a) => a.is_overdue), scheduled_actions: actions,
    });
    vi.mocked(gardnrApi.listPlants).mockResolvedValue([
      plant(10, 1, [action("2026-01-01", true), action(today, false)]),
      plant(11, 1, [action("2026-01-02", true)]),
      plant(12, 2, [action(today, false)]),
    ]);
    renderAreas();

    expect(await screen.findByText("2 tuinen · 4 planten")).toBeInTheDocument();
    const banner = await screen.findByRole("link", { name: /2 taken te laat/ });
    expect(banner).toHaveTextContent("en 2 voor vandaag, in 2 tuinen");
    expect(banner).toHaveAttribute("href", "/gardnr/vandaag");

    const achtertuin = screen.getByRole("link", { name: /Achtertuin/ });
    expect(achtertuin).toHaveTextContent("2 te laat");
    expect(achtertuin).toHaveTextContent("1 vandaag");
    expect(screen.getByRole("link", { name: /Voortuin/ })).toHaveTextContent("1 vandaag");
  });

  it("marks a garden with nothing due as on schedule, with no banner", async () => {
    renderAreas();
    expect(await screen.findAllByText("Op schema")).toHaveLength(2);
    expect(screen.queryByText(/te laat/)).not.toBeInTheDocument();
  });
});
