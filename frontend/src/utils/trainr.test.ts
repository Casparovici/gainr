import { describe, expect, it } from "vitest";

import type { TrainrExercise, TrainrWorkout } from "../api/trainrTypes";
import {
  decimalToInput,
  formatCountDelta,
  formatKmDelta,
  formatKmRounded,
  entrySummary,
  formatDuration,
  formatDurationLong,
  formatBpm,
  formatKcal,
  formatKm,
  formatPace,
  formatSpeed,
  formatWeekLabel,
  lastTimeHint,
  parseDuration,
  workoutHeadline,
} from "./trainr";
import { addDays, endOfMonth, isoWeekNumber, range, startOfWeek } from "./weekCalendar";

describe("parseDuration", () => {
  it("reads minutes, min:sec and h:min:sec", () => {
    expect(parseDuration("45")).toBe(2700);
    expect(parseDuration("45:30")).toBe(2730);
    expect(parseDuration("1:02:15")).toBe(3735);
    expect(parseDuration(" 0:50 ")).toBe(50);
  });

  it("rejects what isn't a duration", () => {
    expect(parseDuration("")).toBeNull();
    expect(parseDuration("abc")).toBeNull();
    expect(parseDuration("45:75")).toBeNull();
    expect(parseDuration("1:75:00")).toBeNull();
    expect(parseDuration("1:2:3:4")).toBeNull();
    expect(parseDuration("0")).toBeNull();
    expect(parseDuration("4,5")).toBeNull();
  });

  it("round-trips through formatDuration", () => {
    for (const s of [50, 2730, 3735, 36000]) expect(parseDuration(formatDuration(s))).toBe(s);
  });
});

describe("formatting", () => {
  it("formats durations, pace, distance and speed in Dutch notation", () => {
    expect(formatDuration(2730)).toBe("45:30");
    expect(formatDuration(null)).toBe("");
    expect(formatDurationLong(8100)).toBe("2 u 15 min");
    expect(formatDurationLong(2700)).toBe("45 min");
    expect(formatDurationLong(7200)).toBe("2 u");
    expect(formatPace(312)).toBe("5:12 /km");
    expect(formatPace(null)).toBe("—");
    expect(formatKm("10.50")).toBe("10,5 km");
    expect(formatSpeed("24.3")).toBe("24,3 km/u");
    expect(formatSpeed(null)).toBe("—");
    expect(decimalToInput("12.50")).toBe("12,5");
    expect(decimalToInput("40.00")).toBe("40");
    expect(decimalToInput(null)).toBe("");
  });

  it("summarises an exercise entry", () => {
    expect(entrySummary({ sets: 3, reps: 10, weight_kg: "12.50", duration_seconds: null })).toBe("3 × 10 · 12,5 kg");
    expect(entrySummary({ sets: 3, reps: null, weight_kg: null, duration_seconds: 45 })).toBe("3 × 0:45");
    expect(entrySummary({ sets: 3, reps: 10, weight_kg: "12.50", duration_seconds: 130 })).toBe("3 × 10 · 12,5 kg · 2:10");
    expect(entrySummary({ sets: 4, reps: null, weight_kg: null, duration_seconds: null })).toBe("4 sets");
    expect(entrySummary({ sets: null, reps: null, weight_kg: null, duration_seconds: null })).toBe("");
  });
});

describe("overview formatting", () => {
  it("rounds headline distances and signs the change", () => {
    expect(formatKmRounded("15902.34")).toBe("15.902 km");
    expect(formatKmRounded("42.35")).toBe("42,4 km");
    expect(formatKmRounded(null)).toBe("0 km");
    expect(formatKmDelta("120.5", "100")).toBe("+20,5 km");
    expect(formatKmDelta(null, "30")).toBe("−30 km");
    expect(formatKmDelta("10", "10.01")).toBe("even veel");
    expect(formatCountDelta(3, 1)).toBe("+2");
    expect(formatCountDelta(1, 2)).toBe("−1");
    expect(formatCountDelta(2, 2)).toBe("even veel");
  });
});

describe("lastTimeHint", () => {
  const exercise = (over: Partial<TrainrExercise>): TrainrExercise => ({
    id: 1, name: "Dumbbell press", muscle_group: "chest", equipment: "dumbbell", is_archived: false, times_performed: 1,
    last_performed_on: "2026-10-08", last_sets: 3, last_reps: 10, last_weight_kg: "14.00", best_weight_kg: "14.00", demo_id: null, demo: null, ...over,
  });

  it("names the last session's sets, reps and weight", () => {
    expect(lastTimeHint(exercise({}))).toBe("Vorige keer (8 okt): 3 × 10 · 14 kg");
  });

  it("says nothing for an exercise never done", () => {
    expect(lastTimeHint(exercise({ last_performed_on: null }))).toBeNull();
    expect(lastTimeHint(undefined)).toBeNull();
  });
});

describe("workoutHeadline", () => {
  const workout = (over: Partial<TrainrWorkout>): TrainrWorkout => ({
    id: 1, activity_type: "running", date: "2026-10-05", is_completed: true, duration_seconds: null, distance_km: null,
    max_speed_kmh: null, calories_kcal: null, avg_heart_rate_bpm: null, max_heart_rate_bpm: null, notes: null, entries: [], avg_speed_kmh: null, pace_seconds_per_km: null, volume_kg: null, ...over,
  });

  it("leads with the distance or the exercise count", () => {
    expect(workoutHeadline(workout({ distance_km: "10.00" }))).toBe("Hardlopen · 10 km");
    expect(workoutHeadline(workout({ activity_type: "cycling" }))).toBe("Fietsen");
    const entry = { id: 1, exercise_id: 1, exercise_name: "x", muscle_group: "chest" as const, sets: 3, reps: 10, weight_kg: null, duration_seconds: null, notes: null };
    expect(workoutHeadline(workout({ activity_type: "home_gym", entries: [entry, { ...entry, id: 2 }] }))).toBe("Home gym · 2 oefeningen");
  });
});

describe("weekCalendar", () => {
  it("starts weeks on Monday and walks month ends", () => {
    expect(startOfWeek("2026-10-11")).toBe("2026-10-05"); // a Sunday
    expect(startOfWeek("2026-10-05")).toBe("2026-10-05");
    expect(endOfMonth("2026-02-10")).toBe("2026-02-28");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(range("2026-10-30", "2026-11-02")).toEqual(["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"]);
  });
});

describe("formatKcal and formatBpm", () => {
  it("format whole numbers with their unit and a dash for nothing", () => {
    expect(formatKcal(1240)).toBe("1.240 kcal");
    expect(formatBpm(148)).toBe("148 bpm");
    expect(formatKcal(null)).toBe("—");
    expect(formatBpm(undefined)).toBe("—");
  });
});

describe("isoWeekNumber", () => {
  it("counts Monday-based weeks, week 1 holding the year's first Thursday", () => {
    expect(isoWeekNumber("2026-10-12")).toBe(42);
    expect(isoWeekNumber("2026-10-18")).toBe(42);
    expect(isoWeekNumber("2026-01-01")).toBe(1);
    expect(isoWeekNumber("2025-12-29")).toBe(1);
    expect(isoWeekNumber("2027-01-01")).toBe(53);
  });
});

describe("formatWeekLabel", () => {
  it("names the week and its days, with the month and year once when they don't change", () => {
    expect(formatWeekLabel("2026-10-12")).toBe("Week 42 · 12 – 18 okt 2026");
    expect(formatWeekLabel("2026-09-28")).toBe("Week 40 · 28 sep – 4 okt 2026");
    expect(formatWeekLabel("2025-12-29")).toBe("Week 1 · 29 dec 2025 – 4 jan 2026");
  });
});
