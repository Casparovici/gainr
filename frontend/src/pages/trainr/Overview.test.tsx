import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { trainrApi } from "../../api/trainrClient";
import type { TrainrActivityType, TrainrOverview, TrainrPeriodTotals } from "../../api/trainrTypes";
import TrainrOverviewPage from "./Overview";

vi.mock("../../api/trainrClient", () => ({ trainrApi: { getOverview: vi.fn() } }));

const totals = (over: Partial<TrainrPeriodTotals> = {}): TrainrPeriodTotals => ({
  workouts: 0, duration_seconds: 0, distance_km: null, avg_speed_kmh: null, volume_kg: null,
  calories_kcal: null, avg_heart_rate_bpm: null, max_heart_rate_bpm: null, ...over,
});
const point = (period_start: string, km: string | null) => ({
  period_start, workouts: km ? 1 : 0, duration_seconds: km ? 3600 : 0, distance_km: km, avg_speed_kmh: km ? "25.0" : null,
  pace_seconds_per_km: null, volume_kg: null, calories_kcal: null, avg_heart_rate_bpm: null,
});

function overview(activity: TrainrActivityType, over: Partial<TrainrOverview> = {}): TrainrOverview {
  return {
    activity_type: activity,
    today: "2026-10-14",
    tiles: [
      { key: "week", date_from: "2026-10-12", date_to: "2026-10-14", current: totals(), previous: totals({ workouts: 1, distance_km: "44.90" }) },
      { key: "month", date_from: "2026-10-01", date_to: "2026-10-14", current: totals({ workouts: 2, distance_km: "44.90", duration_seconds: 7080 }), previous: totals({ workouts: 3, distance_km: "50.20" }) },
      { key: "year", date_from: "2026-01-01", date_to: "2026-10-14", current: totals({ workouts: 69, distance_km: "2382.24" }), previous: totals({ workouts: 40, distance_km: "1440" }) },
      { key: "all", date_from: null, date_to: "2026-10-14", current: totals({ workouts: 558, distance_km: "15902.30" }), previous: null },
    ],
    monthly: [point("2026-09-01", "60.00"), point("2026-10-01", "44.90")],
    yearly: [point("2013-01-01", "120.00"), point("2026-01-01", "2382.24")],
    records: [{ kind: "longest_distance", value: "133.32", workout_id: 1, date: "2017-07-15", detail: null }],
    muscle_groups: [],
    exercises: [],
    ...over,
  };
}

function renderPage(path = "/trainr/overzicht") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <TrainrOverviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TrainrOverviewPage", () => {
  beforeAll(() => {
    // Recharts' ResponsiveContainer measures itself with ResizeObserver, which jsdom lacks; the
    // charts then render at zero size, which is fine -- these tests read the text around them.
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
  });

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(trainrApi.getOverview).mockImplementation(async (a) =>
      a === "home_gym"
        ? overview("home_gym", {
            tiles: overview("home_gym").tiles.map((t) => ({ ...t, current: totals({ workouts: 4, volume_kg: "1200.00" }) })),
            records: [{ kind: "heaviest_lift", value: "16.00", workout_id: 2, date: "2026-10-12", detail: "Dumbbell press" }],
            muscle_groups: [{ muscle_group: "chest", sets: 8, volume_kg: "960.00" }],
            exercises: [{ exercise_id: 1, name: "Dumbbell press", sessions: 2, best_weight_kg: "16.00", points: [] }],
          })
        : overview(a),
    );
  });

  it("opens on cycling with km per period against last time", async () => {
    renderPage();
    expect(await screen.findByText("15.902 km")).toBeInTheDocument();
    expect(trainrApi.getOverview).toHaveBeenCalledWith("cycling");
    expect(screen.getByText("2.382 km")).toBeInTheDocument();
    expect(screen.getByText("+942 km t.o.v. vorig jaar")).toBeInTheDocument();
    expect(screen.getByText("−5,3 km t.o.v. vorige maand")).toBeInTheDocument();
    expect(screen.getByText("sinds 2013")).toBeInTheDocument();
    expect(screen.getAllByText("Nog niets")).toHaveLength(1); // the empty week
    expect(screen.getByText("Langste afstand")).toBeInTheDocument();
    expect(screen.getByText("133,32 km")).toBeInTheDocument();
  });

  it("switches to the gym dashboard and remembers the choice", async () => {
    renderPage();
    await screen.findByText("15.902 km");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Activiteit" }), "home_gym");

    expect(await screen.findByText("Progressie per oefening")).toBeInTheDocument();
    expect(screen.getByText("Sets per spiergroep")).toBeInTheDocument();
    expect(screen.getAllByText("4×").length).toBeGreaterThan(0);
    expect(screen.getByText("Dumbbell press · 12 okt 2026")).toBeInTheDocument();
    expect(localStorage.getItem("trainr.overview.activity")).toBe("home_gym");
  });

  it("offers every activity in one dropdown and shows a match's calories and heart rate", async () => {
    vi.mocked(trainrApi.getOverview).mockImplementation(async (a) =>
      overview(a, {
        tiles: overview(a).tiles.map((t) => ({
          ...t,
          current: totals({ workouts: 3, duration_seconds: 16200, calories_kcal: 2400, avg_heart_rate_bpm: 148, max_heart_rate_bpm: 186 }),
        })),
        records: [
          { kind: "most_calories", value: "910", workout_id: 4, date: "2026-10-10", detail: null },
          { kind: "highest_heart_rate", value: "191", workout_id: 5, date: "2026-10-03", detail: null },
        ],
      }),
    );
    renderPage();
    const select = await screen.findByRole("combobox", { name: "Activiteit" });
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Fietsen", "Hardlopen", "Home gym", "Voetbal", "Padel",
    ]);

    await userEvent.selectOptions(select, "football");

    expect(await screen.findAllByText("4 u 30 min · 2.400 kcal · gem. 148 bpm")).not.toHaveLength(0);
    expect(trainrApi.getOverview).toHaveBeenCalledWith("football");
    expect(screen.getByText("Meeste calorieën")).toBeInTheDocument();
    expect(screen.getByText("910 kcal")).toBeInTheDocument();
    expect(screen.getByText("191 bpm")).toBeInTheDocument();
    expect(screen.queryByText("Sets per spiergroep")).not.toBeInTheDocument();
  });

  it("takes the activity from the URL", async () => {
    renderPage("/trainr/overzicht?activiteit=running");
    await screen.findByText("Gemiddeld tempo per maand");
    expect(trainrApi.getOverview).toHaveBeenCalledWith("running");
  });

  it("says when an activity has nothing yet", async () => {
    vi.mocked(trainrApi.getOverview).mockResolvedValue(overview("running", { tiles: overview("running").tiles.map((t) => ({ ...t, current: totals() })) }));
    renderPage("/trainr/overzicht?activiteit=running");
    expect(await screen.findByText(/Nog geen gedane hardlopen-workouts/)).toBeInTheDocument();
  });

  it("offers a retry when loading fails", async () => {
    vi.mocked(trainrApi.getOverview).mockRejectedValue(new Error("500"));
    renderPage();
    expect(await screen.findByRole("button", { name: "Opnieuw proberen" })).toBeInTheDocument();
  });
});
