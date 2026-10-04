import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { gardnrApi } from "../../api/gardnrClient";
import type { GardenCareSchedule, GardenPlantDetail } from "../../api/gardnrTypes";
import PlantDetailPanel from "./PlantDetailPanel";

vi.mock("../../api/gardnrClient", () => ({
  gardnrApi: {
    getPlantDetail: vi.fn(),
    updateSchedule: vi.fn(),
    createLog: vi.fn(),
  },
}));

const schedule: GardenCareSchedule = {
  id: 4, plant_id: 7, action_type: "water", custom_label: null, interval_value: 3, frequency: "daily",
  is_active: true, start_date: null, notes: null, next_due: "2030-01-01", is_overdue: false,
};

const detail: GardenPlantDetail = {
  plant: {
    id: 7, area_id: 1, name: "Tomaat", species: null, type: "plant", planted_date: null, notes: null, x: null, y: null,
    marker_shape: "circle", marker_width: "6", marker_height: "6", icon: null, status: "thriving", is_archived: false,
  },
  care_logs: [],
  care_schedules: [schedule],
};

describe("PlantDetailPanel schedules", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(gardnrApi.getPlantDetail).mockResolvedValue(detail);
    vi.mocked(gardnrApi.updateSchedule).mockResolvedValue({ ...schedule, interval_value: 5 });
  });

  it("edits an existing schedule's interval instead of only pausing or deleting it", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <PlantDetailPanel plantId={7} onClose={() => {}} />
      </QueryClientProvider>,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Schema" }));
    await userEvent.click(await screen.findByRole("button", { name: "Schema bewerken" }));
    const interval = screen.getByDisplayValue("3");
    await userEvent.clear(interval);
    await userEvent.type(interval, "5");
    await userEvent.click(screen.getByRole("button", { name: "Opslaan" }));

    await waitFor(() =>
      expect(gardnrApi.updateSchedule).toHaveBeenCalledWith(4, {
        action_type: "water",
        custom_label: null,
        interval_value: 5,
        frequency: "daily",
        is_active: true,
        start_date: null,
        notes: null,
      }),
    );
  });

  it("lets a schedule start on a chosen date", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <PlantDetailPanel plantId={7} onClose={() => {}} />
      </QueryClientProvider>,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Schema" }));
    await userEvent.click(await screen.findByRole("button", { name: "Schema bewerken" }));
    await userEvent.type(screen.getByLabelText("Eerste keer (optioneel)"), "2030-03-01");
    await userEvent.click(screen.getByRole("button", { name: "Opslaan" }));

    await waitFor(() =>
      expect(gardnrApi.updateSchedule).toHaveBeenCalledWith(4, expect.objectContaining({ start_date: "2030-03-01" })),
    );
  });
});
