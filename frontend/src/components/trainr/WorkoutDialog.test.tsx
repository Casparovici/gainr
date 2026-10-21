import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { trainrApi } from "../../api/trainrClient";
import type { TrainrExercise, TrainrWorkout } from "../../api/trainrTypes";
import WorkoutDialog from "./WorkoutDialog";

vi.mock("../../api/trainrClient", () => ({
  trainrApi: { listExercises: vi.fn(), createExercise: vi.fn() },
}));

const exercise = (over: Partial<TrainrExercise>): TrainrExercise => ({
  id: 1, name: "Dumbbell press", muscle_group: "chest", equipment: "dumbbell", is_archived: false, times_performed: 0,
  last_performed_on: null, last_sets: null, last_reps: null, last_weight_kg: null, best_weight_kg: null, demo_id: null, demo: null, ...over,
});

function renderDialog(props: Partial<React.ComponentProps<typeof WorkoutDialog>> = {}) {
  const onSave = vi.fn();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <WorkoutDialog defaultDate="2026-10-05" isSubmitting={false} onCancel={vi.fn()} onSave={onSave} {...props} />
    </QueryClientProvider>,
  );
  return { onSave };
}

describe("WorkoutDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(trainrApi.listExercises).mockResolvedValue([
      exercise({ id: 1, last_performed_on: "2026-10-01", last_sets: 3, last_reps: 10, last_weight_kg: "12.50", times_performed: 1 }),
      exercise({ id: 2, name: "Goblet squat", muscle_group: "legs" }),
      exercise({ id: 3, name: "Old move", is_archived: true }),
    ]);
  });

  it("logs a gym session, starting an exercise from last time's sets, reps and weight", async () => {
    const { onSave } = renderDialog();
    const select = screen.getByRole("combobox", { name: "Oefening 1" });
    await screen.findByRole("option", { name: "Dumbbell press" });
    expect(screen.queryByRole("option", { name: "Old move" })).not.toBeInTheDocument();

    await userEvent.selectOptions(select, "1");
    expect(screen.getByText("Vorige keer (1 okt): 3 × 10 · 12,5 kg")).toBeInTheDocument();
    const kg = screen.getByRole("textbox", { name: "Kg oefening 1" });
    expect(kg).toHaveValue("12,5");
    await userEvent.clear(kg);
    await userEvent.type(kg, "14");

    await userEvent.click(screen.getByRole("button", { name: "Oefening toevoegen" }));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Oefening 2" }), "2");
    await userEvent.type(screen.getByRole("textbox", { name: "Sets oefening 2" }), "4");
    await userEvent.type(screen.getByRole("textbox", { name: "Herh. oefening 2" }), "8");
    await userEvent.type(screen.getByRole("textbox", { name: "Kg oefening 2" }), "22,5");
    await userEvent.click(screen.getByRole("button", { name: "Opslaan" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        activity_type: "home_gym",
        date: "2026-10-05",
        distance_km: null,
        entries: [
          { exercise_id: 1, sets: 3, reps: 10, weight_kg: "14", duration_seconds: null, notes: null },
          { exercise_id: 2, sets: 4, reps: 8, weight_kg: "22.5", duration_seconds: null, notes: null },
        ],
      }),
    );
  });

  it("logs a run with distance, time and top speed", async () => {
    const { onSave } = renderDialog();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Activiteit" }), "running");
    await userEvent.type(screen.getByRole("textbox", { name: "Afstand (km)" }), "10,5");
    await userEvent.type(screen.getByRole("textbox", { name: "Tijd" }), "52:30");
    await userEvent.type(screen.getByRole("textbox", { name: "Topsnelheid (km/u)" }), "16,2");
    await userEvent.click(screen.getByRole("button", { name: "Opslaan" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ activity_type: "running", distance_km: "10.5", duration_seconds: 3150, max_speed_kmh: "16.2", entries: [] }),
    );
  });

  it("logs a football match with time, calories and heart rates, and no exercises or distance", async () => {
    const { onSave } = renderDialog();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Activiteit" }), "football");
    expect(screen.queryByRole("textbox", { name: "Afstand (km)" })).not.toBeInTheDocument();
    expect(screen.queryByText("Oefeningen")).not.toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: "Tijd" }), "1:30:00");
    await userEvent.type(screen.getByRole("textbox", { name: "Calorieën (kcal)" }), "820");
    await userEvent.type(screen.getByRole("textbox", { name: "Gem. hartslag (bpm)" }), "148");
    await userEvent.type(screen.getByRole("textbox", { name: "Max. hartslag (bpm)" }), "187");
    await userEvent.click(screen.getByRole("button", { name: "Opslaan" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        activity_type: "football", duration_seconds: 5400, calories_kcal: 820, avg_heart_rate_bpm: 148, max_heart_rate_bpm: 187,
        distance_km: null, max_speed_kmh: null, entries: [],
      }),
    );
  });

  it("leaves calories and heart rate out of a run, even after typing them for a match", async () => {
    const { onSave } = renderDialog();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Activiteit" }), "padel");
    await userEvent.type(screen.getByRole("textbox", { name: "Calorieën (kcal)" }), "500");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Activiteit" }), "running");
    await userEvent.click(screen.getByRole("button", { name: "Opslaan" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ activity_type: "running", calories_kcal: null, avg_heart_rate_bpm: null, max_heart_rate_bpm: null }),
    );
  });

  it("won't save a heart rate that is out of range or an average above the maximum", async () => {
    renderDialog();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Activiteit" }), "padel");
    await userEvent.type(screen.getByRole("textbox", { name: "Max. hartslag (bpm)" }), "400");
    expect(screen.getByText("Hartslag is een heel getal van 30 tot 250.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Opslaan" })).toBeDisabled();

    await userEvent.clear(screen.getByRole("textbox", { name: "Max. hartslag (bpm)" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Max. hartslag (bpm)" }), "150");
    await userEvent.type(screen.getByRole("textbox", { name: "Gem. hartslag (bpm)" }), "160");
    expect(screen.getByText("De gemiddelde hartslag kan niet hoger zijn dan de maximale.")).toBeInTheDocument();
  });

  it("won't save a time it can't read", async () => {
    renderDialog();
    await userEvent.type(screen.getByRole("textbox", { name: "Tijd" }), "abc");
    expect(screen.getByText("Tijd: gebruik minuten, mm:ss of u:mm:ss.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Opslaan" })).toBeDisabled();
  });

  it("plans a future workout and logs a past one by default", () => {
    renderDialog({ defaultDate: "2999-01-01" });
    expect(screen.getByRole("checkbox", { name: "Gedaan" })).not.toBeChecked();
  });

  it("opens an existing workout with its exercises filled in", async () => {
    const workout: TrainrWorkout = {
      id: 9, activity_type: "home_gym", date: "2026-10-03", is_completed: true, duration_seconds: 2700, distance_km: null,
      max_speed_kmh: null, calories_kcal: null, avg_heart_rate_bpm: null, max_heart_rate_bpm: null, notes: "zwaar", avg_speed_kmh: null, pace_seconds_per_km: null, volume_kg: "375.00",
      entries: [{ id: 1, exercise_id: 2, exercise_name: "Goblet squat", muscle_group: "legs", sets: 3, reps: 10, weight_kg: "12.50", duration_seconds: null, notes: null }],
    };
    renderDialog({ workout, onDelete: vi.fn() });
    await screen.findByRole("option", { name: "Goblet squat" });
    expect(screen.getByRole("combobox", { name: "Oefening 1" })).toHaveValue("2");
    expect(screen.getByRole("textbox", { name: "Kg oefening 1" })).toHaveValue("12,5");
    expect(screen.getByRole("textbox", { name: "Tijd" })).toHaveValue("45:00");
    expect(screen.getByRole("button", { name: "Verwijderen" })).toBeInTheDocument();
  });
});
