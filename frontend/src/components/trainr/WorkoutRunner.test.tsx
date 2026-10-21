import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TrainrExerciseDemo, TrainrWorkout, TrainrWorkoutEntry } from "../../api/trainrTypes";
import WorkoutRunner from "./WorkoutRunner";

const entry = (over: Partial<TrainrWorkoutEntry>): TrainrWorkoutEntry => ({
  id: 1, exercise_id: 1, exercise_name: "Dumbbell press", muscle_group: "chest", sets: 2, reps: 10, weight_kg: "12.50",
  duration_seconds: null, notes: null, ...over,
});

const pressDemo: TrainrExerciseDemo = {
  id: "Dumbbell_Bench_Press", name: "Dumbbell Bench Press", equipment: "dumbbell",
  image_urls: ["https://cdn.example/press/0.jpg", "https://cdn.example/press/1.jpg"], instructions: ["Press the dumbbells up."],
};

const planned: TrainrWorkout = {
  id: 7, activity_type: "home_gym", date: "2026-10-12", is_completed: false, duration_seconds: null, distance_km: null,
  max_speed_kmh: null, calories_kcal: null, avg_heart_rate_bpm: null, max_heart_rate_bpm: null, notes: "benen morgen", avg_speed_kmh: null, pace_seconds_per_km: null, volume_kg: null,
  entries: [entry({}), entry({ id: 2, exercise_id: 2, exercise_name: "Plank", sets: 1, reps: null, weight_kg: null, duration_seconds: 30 })],
};

function renderRunner(workout: TrainrWorkout = planned, demos?: ReadonlyMap<number, TrainrExerciseDemo>) {
  const onFinish = vi.fn();
  const onClose = vi.fn();
  render(<WorkoutRunner workout={workout} demos={demos} isSaving={false} onClose={onClose} onFinish={onFinish} />);
  return { onFinish, onClose };
}

const click = (name: string) => fireEvent.click(screen.getByRole("button", { name }));

describe("WorkoutRunner", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-14T10:00:00"));
  });
  afterEach(() => vi.useRealTimers());

  it("walks through the sets with rests, a timed hold and the actual numbers, then saves", () => {
    const { onFinish } = renderRunner();

    expect(screen.getByRole("heading", { name: "Dumbbell press" })).toBeInTheDocument();
    expect(screen.getByText(/Set 1 van 2/)).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(40_000));
    expect(screen.getByRole("timer", { name: "Duur van deze set" })).toHaveTextContent("0:40");
    click("Set klaar");

    // The rest between sets counts down and can be skipped.
    expect(screen.getByText("Rust")).toBeInTheDocument();
    expect(screen.getByRole("timer", { name: "Rust over" })).toHaveTextContent("1:30");
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.getByRole("timer", { name: "Rust over" })).toHaveTextContent("1:20");
    click("Rust overslaan");

    // Second set went heavier. The 10 s of rest above isn't part of its time.
    expect(screen.getByText(/Set 2 van 2/)).toBeInTheDocument();
    expect(screen.getByRole("timer", { name: "Duur van deze set" })).toHaveTextContent("0:00");
    act(() => vi.advanceTimersByTime(30_000));
    click("Gewicht omhoog");
    expect(screen.getByText("15 kg")).toBeInTheDocument();
    click("Set klaar");
    click("Rust overslaan");

    // The plank is a countdown that finishes by itself.
    expect(screen.getByRole("heading", { name: "Plank" })).toBeInTheDocument();
    click("Start");
    act(() => vi.advanceTimersByTime(30_500));

    expect(screen.getByRole("heading", { name: "Goed gedaan" })).toBeInTheDocument();
    click("Opslaan als gedaan");

    expect(onFinish).toHaveBeenCalledTimes(1);
    const input = onFinish.mock.calls[0][0];
    expect(input).toMatchObject({ activity_type: "home_gym", date: "2026-10-14", is_completed: true, notes: "benen morgen" });
    expect(input.duration_seconds).toBeGreaterThanOrEqual(80);
    // Each counted exercise carries the time it took (no rest in it); the hold its held time.
    expect(input.entries).toEqual([
      { exercise_id: 1, sets: 1, reps: 10, weight_kg: "12.5", duration_seconds: 40, notes: null },
      { exercise_id: 1, sets: 1, reps: 10, weight_kg: "15", duration_seconds: 30, notes: null },
      { exercise_id: 2, sets: 1, reps: null, weight_kg: null, duration_seconds: 30, notes: null },
    ]);
  });

  it("ticks a whole exercise off and skips the next, saving only what was done", () => {
    const { onFinish } = renderRunner();
    click("Oefening afvinken");
    click("Rust overslaan");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    click("Oefening overslaan");

    expect(screen.getByRole("heading", { name: "Goed gedaan" })).toBeInTheDocument();
    expect(screen.getByText(/2 van 3 sets/)).toBeInTheDocument();
    click("Opslaan als gedaan");
    expect(onFinish.mock.calls[0][0].entries).toEqual([{ exercise_id: 1, sets: 2, reps: 10, weight_kg: "12.5", duration_seconds: null, notes: null }]);
  });

  it("cannot be saved with nothing ticked off, and stopping asks first once there's progress", () => {
    const { onFinish, onClose } = renderRunner();
    click("Stoppen");
    expect(onClose).toHaveBeenCalledTimes(1);

    expect(screen.getByRole("button", { name: "Afronden" })).toBeDisabled();
    click("Set overslaan");
    click("Set overslaan");
    click("Set overslaan");
    expect(screen.getByRole("heading", { name: "Niets afgevinkt" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Opslaan als gedaan" })).toBeDisabled();
    expect(onFinish).not.toHaveBeenCalled();
  });

  it("lets you finish early from the header and carry on again", () => {
    renderRunner();
    click("Set klaar");
    click("Rust overslaan");
    click("Afronden");
    expect(screen.getByRole("heading", { name: "Goed gedaan" })).toBeInTheDocument();
    click("Verder met de workout");
    expect(screen.getByText(/Set 2 van 2/)).toBeInTheDocument();
  });

  it("adds up the time of identical sets and leaves the rest between them out", () => {
    const { onFinish } = renderRunner();
    act(() => vi.advanceTimersByTime(20_000));
    click("Set klaar");
    // The rest runs out by itself; the next set is timed from the moment it ended.
    act(() => vi.advanceTimersByTime(95_000));
    expect(screen.getByText(/Set 2 van 2/)).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(15_000));
    click("Set klaar");
    click("Afronden");
    click("Opslaan als gedaan");
    expect(onFinish.mock.calls[0][0].entries).toEqual([{ exercise_id: 1, sets: 2, reps: 10, weight_kg: "12.5", duration_seconds: 40, notes: null }]);
  });

  it("credits the set in progress when a whole exercise is ticked off", () => {
    const { onFinish } = renderRunner();
    act(() => vi.advanceTimersByTime(25_000));
    click("Oefening afvinken");
    click("Afronden");
    click("Opslaan als gedaan");
    expect(onFinish.mock.calls[0][0].entries).toEqual([{ exercise_id: 1, sets: 2, reps: 10, weight_kg: "12.5", duration_seconds: 25, notes: null }]);
  });

  it("shows the exercise's demo during its sets and the next one's during the rest, and can hide them", () => {
    localStorage.clear();
    const demos = new Map([[1, pressDemo]]);
    renderRunner(planned, demos);

    expect(screen.getByRole("button", { name: "Voorbeeld: Dumbbell Bench Press" })).toBeInTheDocument();
    click("Set klaar");
    // Resting before set 2 of the press: its demo, without the steps.
    expect(screen.getByRole("button", { name: "Voorbeeld: Dumbbell Bench Press" })).toBeInTheDocument();
    expect(screen.queryByText("Uitleg (Engels)")).not.toBeInTheDocument();
    click("Rust overslaan");

    click("Voorbeeld verbergen");
    expect(screen.queryByRole("button", { name: /Voorbeeld:/ })).not.toBeInTheDocument();
    expect(localStorage.getItem("trainr.runner.demosHidden")).toBe("1");
    click("Voorbeeld tonen");
    expect(screen.getByRole("button", { name: "Voorbeeld: Dumbbell Bench Press" })).toBeInTheDocument();

    // The plank has no demo linked: nothing shown, and no toggle either.
    click("Set klaar");
    click("Rust overslaan");
    expect(screen.getByRole("heading", { name: "Plank" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Voorbeeld/ })).not.toBeInTheDocument();
  });
});
