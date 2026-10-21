import { describe, expect, it } from "vitest";

import type { TrainrWorkout, TrainrWorkoutEntry } from "../api/trainrTypes";
import {
  adjustReps,
  adjustWeight,
  buildSteps,
  doneCount,
  entriesFromResults,
  firstPending,
  pendingResult,
  secondsLeft,
  type StepResult,
} from "./trainrRunner";

function entry(over: Partial<TrainrWorkoutEntry>): TrainrWorkoutEntry {
  return {
    id: 1,
    exercise_id: 1,
    exercise_name: "Dumbbell press",
    muscle_group: "chest",
    sets: 3,
    reps: 10,
    weight_kg: "12.50",
    duration_seconds: null,
    notes: null,
    ...over,
  };
}

function workout(entries: TrainrWorkoutEntry[]): TrainrWorkout {
  return {
    id: 7,
    activity_type: "home_gym",
    date: "2026-10-14",
    is_completed: false,
    duration_seconds: null,
    distance_km: null,
    max_speed_kmh: null,
    calories_kcal: null,
    avg_heart_rate_bpm: null,
    max_heart_rate_bpm: null,
    notes: null,
    entries,
    avg_speed_kmh: null,
    pace_seconds_per_km: null,
    volume_kg: null,
  };
}

const done = (over: Partial<StepResult> = {}): StepResult => ({ status: "done", reps: 10, weightKg: 12.5, seconds: null, activeSeconds: null, ...over });
const skipped = (): StepResult => ({ status: "skipped", reps: 10, weightKg: 12.5, seconds: null, activeSeconds: null });

describe("buildSteps", () => {
  it("makes one step per set, numbered within the exercise", () => {
    const steps = buildSteps(workout([entry({ sets: 3 }), entry({ exercise_id: 2, exercise_name: "Pull-up", sets: 2, reps: 6, weight_kg: null })]));
    expect(steps).toHaveLength(5);
    expect(steps.map((s) => `${s.exerciseName} ${s.setNumber}/${s.setCount}`)).toEqual([
      "Dumbbell press 1/3",
      "Dumbbell press 2/3",
      "Dumbbell press 3/3",
      "Pull-up 1/2",
      "Pull-up 2/2",
    ]);
    expect(steps[0]).toMatchObject({ kind: "reps", targetReps: 10, targetWeightKg: 12.5 });
    expect(steps[3].targetWeightKg).toBeNull();
  });

  it("treats a timed entry as a hold and an entry with no target as one plain set", () => {
    const steps = buildSteps(workout([entry({ sets: 2, reps: null, weight_kg: null, duration_seconds: 45 }), entry({ sets: null, reps: null, weight_kg: null })]));
    expect(steps.map((s) => s.kind)).toEqual(["hold", "hold", "plain"]);
    expect(steps[0].targetSeconds).toBe(45);
    expect(steps[2]).toMatchObject({ setNumber: 1, setCount: 1 });
  });

  it("gives an empty plan no steps", () => {
    expect(buildSteps(workout([]))).toEqual([]);
  });
});

describe("progress helpers", () => {
  it("finds the first pending step and counts done ones", () => {
    const steps = buildSteps(workout([entry({ sets: 3 })]));
    const results = steps.map(pendingResult);
    expect(firstPending(results)).toBe(0);
    results[0] = done();
    results[1] = skipped();
    expect(firstPending(results)).toBe(2);
    expect(doneCount(results)).toBe(1);
    results[2] = done();
    expect(firstPending(results)).toBeNull();
  });

  it("steps weight and reps without going below their floor", () => {
    expect(adjustWeight(12.5, 2.5)).toBe(15);
    expect(adjustWeight(1, -2.5)).toBe(0);
    expect(adjustWeight(null, 2.5)).toBe(2.5);
    expect(adjustReps(10, 1)).toBe(11);
    expect(adjustReps(1, -1)).toBe(1);
  });

  it("counts a countdown down to zero and no further", () => {
    expect(secondsLeft(10_000, 4_500)).toBe(6);
    expect(secondsLeft(10_000, 10_000)).toBe(0);
    expect(secondsLeft(10_000, 12_000)).toBe(0);
  });
});

describe("entriesFromResults", () => {
  it("folds identical neighbouring sets back into one entry", () => {
    const w = workout([entry({ sets: 3 })]);
    const steps = buildSteps(w);
    const out = entriesFromResults(w, steps, [done(), done(), done()]);
    expect(out).toEqual([{ exercise_id: 1, sets: 3, reps: 10, weight_kg: "12.5", duration_seconds: null, notes: null }]);
  });

  it("splits a set that came out different into its own entry", () => {
    const w = workout([entry({ sets: 3 })]);
    const out = entriesFromResults(w, buildSteps(w), [done(), done(), done({ reps: 8, weightKg: 10 })]);
    expect(out.map((e) => [e.sets, e.reps, e.weight_kg])).toEqual([
      [2, 10, "12.5"],
      [1, 8, "10"],
    ]);
  });

  it("drops skipped sets and exercises with no done set, and keeps the entry's note", () => {
    const w = workout([entry({ sets: 2, notes: "langzaam" }), entry({ exercise_id: 2, exercise_name: "Pull-up", sets: 2 })]);
    const out = entriesFromResults(w, buildSteps(w), [done(), skipped(), skipped(), skipped()]);
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ exercise_id: 1, sets: 1, notes: "langzaam" });
  });

  it("does not merge equal sets of two different exercises", () => {
    const w = workout([entry({ sets: 1 }), entry({ exercise_id: 2, exercise_name: "Row", sets: 1 })]);
    expect(entriesFromResults(w, buildSteps(w), [done(), done()])).toHaveLength(2);
  });

  it("records a hold's time and no reps", () => {
    const w = workout([entry({ sets: 2, reps: null, weight_kg: null, duration_seconds: 45 })]);
    const out = entriesFromResults(w, buildSteps(w), [
      { status: "done", reps: null, weightKg: null, seconds: 45, activeSeconds: null },
      { status: "done", reps: null, weightKg: null, seconds: 45, activeSeconds: null },
    ]);
    expect(out).toEqual([{ exercise_id: 1, sets: 2, reps: null, weight_kg: null, duration_seconds: 45, notes: null }]);
  });

  it("sums the time of merged counted sets, whatever each took", () => {
    const w = workout([entry({ sets: 3 })]);
    const out = entriesFromResults(w, buildSteps(w), [done({ activeSeconds: 40 }), done({ activeSeconds: 35 }), done({ activeSeconds: null })]);
    expect(out).toEqual([{ exercise_id: 1, sets: 3, reps: 10, weight_kg: "12.5", duration_seconds: 75, notes: null }]);
  });

  it("keeps each different set's own time, and no time when none was measured", () => {
    const w = workout([entry({ sets: 2 })]);
    const out = entriesFromResults(w, buildSteps(w), [done({ activeSeconds: 40 }), done({ reps: 8, activeSeconds: null })]);
    expect(out.map((e) => e.duration_seconds)).toEqual([40, null]);
  });

  it("leaves a plain set untimed, since a time on a repless entry would read as per set", () => {
    const w = workout([entry({ sets: 1, reps: null, weight_kg: null, duration_seconds: null })]);
    const out = entriesFromResults(w, buildSteps(w), [done({ reps: null, weightKg: null, activeSeconds: 50 })]);
    expect(out[0].duration_seconds).toBeNull();
  });
});
