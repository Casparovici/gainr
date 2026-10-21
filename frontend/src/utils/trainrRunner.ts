import type { TrainrWorkout, TrainrWorkoutEntryInput } from "../api/trainrTypes";
import { toNumber } from "./format";

/** The guided runner's pure half: a planned gym session flattened into sets, and the sets that
 * were actually done folded back into entries. The UI (WorkoutRunner) only holds the clock and
 * the taps; none of this logic lives there. */

export const DEFAULT_REST_SECONDS = 90;
export const WEIGHT_STEP_KG = 2.5;

/** reps: a counted set; hold: a timed set (plank) that counts down; plain: a set with no target. */
export type StepKind = "reps" | "hold" | "plain";

export interface RunnerStep {
  entryIndex: number;
  exerciseId: number;
  exerciseName: string;
  /** 1-based, within the exercise. */
  setNumber: number;
  setCount: number;
  kind: StepKind;
  targetReps: number | null;
  targetWeightKg: number | null;
  targetSeconds: number | null;
}

export type StepStatus = "pending" | "done" | "skipped";

export interface StepResult {
  status: StepStatus;
  reps: number | null;
  weightKg: number | null;
  /** A hold's time: the target while pending, the time actually held once done. */
  seconds: number | null;
  /** Active time spent on a counted set (from starting it to ticking it off, rest excluded);
   * null for a hold -- its `seconds` is the time -- and for a set ticked off without doing it. */
  activeSeconds: number | null;
}

/** One step per set: "3 × 10" becomes three steps. An entry without a set count is one set. */
export function buildSteps(workout: TrainrWorkout): RunnerStep[] {
  return workout.entries.flatMap((entry, entryIndex) => {
    const setCount = Math.max(entry.sets ?? 1, 1);
    const kind: StepKind = entry.reps !== null ? "reps" : entry.duration_seconds ? "hold" : "plain";
    return Array.from({ length: setCount }, (_, i) => ({
      entryIndex,
      exerciseId: entry.exercise_id,
      exerciseName: entry.exercise_name,
      setNumber: i + 1,
      setCount,
      kind,
      targetReps: entry.reps,
      targetWeightKg: toNumber(entry.weight_kg),
      targetSeconds: entry.duration_seconds,
    }));
  });
}

export function pendingResult(step: RunnerStep): StepResult {
  return { status: "pending", reps: step.targetReps, weightKg: step.targetWeightKg, seconds: step.targetSeconds, activeSeconds: null };
}

/** The index of the first step still to do, or null when every set is done or skipped. */
export function firstPending(results: StepResult[]): number | null {
  const i = results.findIndex((r) => r.status === "pending");
  return i === -1 ? null : i;
}

export function doneCount(results: StepResult[]): number {
  return results.filter((r) => r.status === "done").length;
}

/** Weight after a +/- tap: never below zero, and kept off binary-float noise. */
export function adjustWeight(current: number | null, delta: number): number {
  return Math.max(0, Math.round(((current ?? 0) + delta) * 100) / 100);
}

/** Reps after a +/- tap: at least one. */
export function adjustReps(current: number | null, delta: number): number {
  return Math.max(1, (current ?? 0) + delta);
}

/** The sets that were done, folded back into the workout's entries. Neighbouring sets of one
 * exercise with identical numbers share an entry ("3 × 10 at 12,5 kg"); a set that came out
 * different becomes its own entry -- the same shape the form uses for sets that differ in weight.
 * Skipped and pending sets are dropped, and so is an exercise left with no done set.
 *
 * An entry's time keeps its two meanings: for a hold it is the time of one set (so equal holds
 * merge, "3 × 0:45"); for a counted exercise it is the active time spent on the entry's sets in
 * total, rests excluded, so merging sets adds their times up. */
export function entriesFromResults(
  workout: TrainrWorkout,
  steps: RunnerStep[],
  results: StepResult[],
): TrainrWorkoutEntryInput[] {
  const out: TrainrWorkoutEntryInput[] = [];
  let previous: { step: RunnerStep; entry: TrainrWorkoutEntryInput } | null = null;
  steps.forEach((step, i) => {
    const result = results[i];
    if (result.status !== "done") return;
    const reps = step.kind === "reps" ? result.reps : null;
    const isHold = step.kind === "hold";
    // A plain set (no reps, no hold) stays untimed: with no reps, a time on its entry would read as per set.
    const seconds = isHold ? result.seconds : step.kind === "reps" ? result.activeSeconds : null;
    const weight = result.weightKg !== null ? String(result.weightKg) : null;
    const last = previous;
    if (
      last &&
      last.step.entryIndex === step.entryIndex &&
      last.entry.reps === reps &&
      last.entry.weight_kg === weight &&
      (!isHold || last.entry.duration_seconds === seconds)
    ) {
      last.entry.sets = (last.entry.sets ?? 0) + 1;
      if (!isHold && seconds) last.entry.duration_seconds = (last.entry.duration_seconds ?? 0) + seconds;
      return;
    }
    const entry: TrainrWorkoutEntryInput = {
      exercise_id: step.exerciseId,
      sets: 1,
      reps,
      weight_kg: weight,
      duration_seconds: seconds || null,
      notes: workout.entries[step.entryIndex].notes,
    };
    out.push(entry);
    previous = { step, entry };
  });
  return out;
}

/** Seconds left on a countdown that ends at `endsAt` (ms epoch), never negative. */
export function secondsLeft(endsAt: number, now: number): number {
  return Math.max(0, Math.ceil((endsAt - now) / 1000));
}
