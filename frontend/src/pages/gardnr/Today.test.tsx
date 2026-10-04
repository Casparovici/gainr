import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { gardnrApi } from "../../api/gardnrClient";
import type { GardenActionSummary, GardenPlantListRow } from "../../api/gardnrTypes";
import { addDaysISO, todayLocalISO } from "../../utils/gardnr";
import GardnrToday from "./Today";

vi.mock("../../api/gardnrClient", () => ({
  gardnrApi: {
    listPlants: vi.fn(),
    createLog: vi.fn(),
    deleteLog: vi.fn(),
    getPlantDetail: vi.fn(),
  },
}));

const today = todayLocalISO();

function action(schedule_id: number, action_type: GardenActionSummary["action_type"], date: string): GardenActionSummary {
  return { schedule_id, action_type, custom_label: null, date, is_overdue: date <= today };
}

function plant(id: number, name: string, actions: GardenActionSummary[]): GardenPlantListRow {
  return {
    id,
    area_id: 1,
    area_name: "Achtertuin",
    name,
    species: null,
    type: "plant",
    status: "thriving",
    is_archived: false,
    next_action: actions[0] ?? null,
    is_overdue: actions[0] ? actions[0].date <= today : false,
    scheduled_actions: actions,
  };
}

function renderToday() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <GardnrToday />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GardnrToday", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(gardnrApi.listPlants).mockResolvedValue([
      // Two things due on one plant: both must show, not just the soonest.
      plant(1, "Tomaat", [action(10, "water", addDaysISO(today, -2)), action(11, "fertilize", today)]),
      plant(2, "Roos", [action(20, "prune", addDaysISO(today, 3))]),
      plant(3, "Eik", [action(30, "prune", addDaysISO(today, 60))]),
    ]);
  });

  it("splits what's late, due today and coming up this week", async () => {
    renderToday();

    const late = await screen.findByRole("region", { name: "Te laat" });
    expect(within(late).getByText("Tomaat")).toBeInTheDocument();
    expect(within(late).getByText(/Water geven/)).toBeInTheDocument();

    const dueToday = screen.getByRole("region", { name: "Vandaag" });
    expect(within(dueToday).getByText(/Bemesten/)).toBeInTheDocument();

    const soon = screen.getByRole("region", { name: /Binnenkort/ });
    expect(within(soon).getByText("Roos")).toBeInTheDocument();
    expect(screen.queryByText("Eik")).not.toBeInTheDocument();
  });

  it("offers to undo a Gedaan, deleting the log it just created", async () => {
    vi.mocked(gardnrApi.createLog).mockResolvedValue({
      id: 77, plant_id: 1, action_type: "fertilize", custom_label: null, performed_on: today, notes: null, has_photo: false,
    });
    vi.mocked(gardnrApi.deleteLog).mockResolvedValue(undefined);
    renderToday();

    const dueToday = await screen.findByRole("region", { name: "Vandaag" });
    await userEvent.click(within(dueToday).getByRole("button", { name: /Gedaan/ }));

    expect(await screen.findByRole("status")).toHaveTextContent("Bemesten geregistreerd voor Tomaat.");
    await userEvent.click(screen.getByRole("button", { name: "Ongedaan maken" }));

    await waitFor(() => expect(gardnrApi.deleteLog).toHaveBeenCalledWith(77));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
