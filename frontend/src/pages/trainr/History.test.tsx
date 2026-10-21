import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { trainrApi } from "../../api/trainrClient";
import type { TrainrSummary, TrainrWorkout } from "../../api/trainrTypes";
import TrainrHistory from "./History";

vi.mock("../../api/trainrClient", () => ({
  trainrApi: { listWorkouts: vi.fn(), getSummary: vi.fn(), listExercises: vi.fn() },
}));

const match: TrainrWorkout = {
  id: 3, activity_type: "football", date: "2026-10-10", is_completed: true, duration_seconds: 5400, distance_km: null,
  max_speed_kmh: null, calories_kcal: 820, avg_heart_rate_bpm: 148, max_heart_rate_bpm: 187, notes: null, entries: [],
  avg_speed_kmh: null, pace_seconds_per_km: null, volume_kg: null,
};
const summary: TrainrSummary = {
  date_from: "2026-10-01", date_to: "2026-10-31", workouts: 1, total_duration_seconds: 5400,
  by_activity: [
    { activity_type: "football", workouts: 1, total_duration_seconds: 5400, total_distance_km: null, avg_speed_kmh: null, total_volume_kg: null,
      total_calories_kcal: 820, avg_heart_rate_bpm: 148, max_heart_rate_bpm: 187 },
  ],
};

function renderHistory() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/trainr/historie"]}>
        <TrainrHistory />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TrainrHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(trainrApi.listWorkouts).mockResolvedValue([match]);
    vi.mocked(trainrApi.getSummary).mockResolvedValue(summary);
    vi.mocked(trainrApi.listExercises).mockResolvedValue([]);
  });

  it("shows a match with its time, calories and heart rates, and totals them in the tile", async () => {
    renderHistory();

    expect(await screen.findByText("1:30:00 · 820 kcal · gem. 148 bpm · max 187 bpm")).toBeInTheDocument();
    expect(screen.getByText("1 u 30 min · 820 kcal · gem. 148 bpm")).toBeInTheDocument();
  });

  it("filters on one activity through a dropdown", async () => {
    renderHistory();
    await screen.findByText("1 u 30 min · 820 kcal · gem. 148 bpm");

    const filter = screen.getByRole("combobox", { name: "Filter op activiteit" });
    expect([...filter.querySelectorAll("option")].map((o) => o.textContent)).toEqual([
      "Alle activiteiten", "Home gym", "Hardlopen", "Fietsen", "Voetbal", "Padel",
    ]);
    await userEvent.selectOptions(filter, "padel");

    expect(trainrApi.listWorkouts).toHaveBeenLastCalledWith(expect.any(String), expect.any(String), { completed: true, activityType: "padel" });
  });

  describe("week period", () => {
    beforeEach(() => {
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(new Date("2026-10-14T12:00:00"));
    });
    afterEach(() => vi.useRealTimers());

    it("shows Monday to Sunday of this week and steps a week at a time", async () => {
      renderHistory();
      await screen.findByText("1 u 30 min · 820 kcal · gem. 148 bpm");

      await userEvent.click(screen.getByRole("button", { name: "Week" }));
      expect(screen.getByRole("button", { name: "Week" })).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByText("Week 42 · 12 – 18 okt 2026")).toBeInTheDocument();
      expect(trainrApi.getSummary).toHaveBeenLastCalledWith("2026-10-12", "2026-10-18");
      expect(trainrApi.listWorkouts).toHaveBeenLastCalledWith("2026-10-12", "2026-10-18", { completed: true, activityType: undefined });

      await userEvent.click(screen.getByRole("button", { name: "Vorige" }));
      expect(screen.getByText("Week 41 · 5 – 11 okt 2026")).toBeInTheDocument();
      expect(trainrApi.getSummary).toHaveBeenLastCalledWith("2026-10-05", "2026-10-11");
    });

    it("says so when the week has no done workouts", async () => {
      vi.mocked(trainrApi.listWorkouts).mockResolvedValue([]);
      renderHistory();

      await userEvent.click(screen.getByRole("button", { name: "Week" }));

      expect(await screen.findByText(/Nog geen gedane workouts in deze week/)).toBeInTheDocument();
    });
  });
});
