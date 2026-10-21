import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { trainrApi } from "../../api/trainrClient";
import type { TrainrWorkout } from "../../api/trainrTypes";
import { addDays, startOfWeek, toIso } from "../../utils/weekCalendar";
import TrainrPlanner from "./Planner";

vi.mock("../../api/trainrClient", () => ({
  trainrApi: {
    listWorkouts: vi.fn(),
    listExercises: vi.fn(),
    setWorkoutCompleted: vi.fn(),
    createWorkout: vi.fn(),
    updateWorkout: vi.fn(),
    deleteWorkout: vi.fn(),
  },
}));

const monday = startOfWeek(toIso(new Date()));
const workout = (over: Partial<TrainrWorkout>): TrainrWorkout => ({
  id: 1, activity_type: "running", date: monday, is_completed: false, duration_seconds: null, distance_km: "10.00",
  max_speed_kmh: null, calories_kcal: null, avg_heart_rate_bpm: null, max_heart_rate_bpm: null, notes: null, entries: [], avg_speed_kmh: null, pace_seconds_per_km: null, volume_kg: null, ...over,
});

function renderPlanner() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/trainr"]}>
        <TrainrPlanner />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TrainrPlanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(trainrApi.listExercises).mockResolvedValue([]);
    vi.mocked(trainrApi.listWorkouts).mockResolvedValue([
      workout({}),
      workout({ id: 2, activity_type: "cycling", date: addDays(monday, 2), is_completed: true, distance_km: "40.00" }),
    ]);
    vi.mocked(trainrApi.setWorkoutCompleted).mockResolvedValue(workout({ is_completed: true }));
  });

  it("shows the week's workouts and counts done vs planned", async () => {
    renderPlanner();
    expect(await screen.findByText("Hardlopen · 10 km")).toBeInTheDocument();
    expect(screen.getByText("Fietsen · 40 km")).toBeInTheDocument();
    expect(screen.getByText("1 gedaan · 1 gepland deze week")).toBeInTheDocument();
    expect(trainrApi.listWorkouts).toHaveBeenCalledWith(monday, addDays(monday, 6));
  });

  it("ticks a planned workout off without opening it", async () => {
    renderPlanner();
    await userEvent.click(await screen.findByRole("button", { name: "Hardlopen · 10 km: markeer als gedaan" }));
    await waitFor(() => expect(trainrApi.setWorkoutCompleted).toHaveBeenCalledWith(1, true));
    expect(screen.queryByRole("button", { name: "Opslaan" })).not.toBeInTheDocument();
  });

  it("opens a workout to edit it, and an empty day to plan one", async () => {
    renderPlanner();
    await userEvent.click(await screen.findByRole("button", { name: "Fietsen · 40 km" }));
    expect(screen.getByRole("heading", { name: /Workout bewerken/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Annuleren" }));

    const emptyDay = screen.getAllByText("+ plannen")[0];
    await userEvent.click(emptyDay);
    const heading = screen.getByRole("heading", { name: /Workout (plannen|loggen)/ });
    expect(within(heading).queryByText(/bewerken/)).not.toBeInTheDocument();
  });
});
