// Mirrors backend/app/schemas/trainr.py. Decimals arrive as strings, like every other module.
import { msg } from "../i18n";

export type TrainrActivityType = "home_gym" | "running" | "cycling" | "football" | "padel";
export type TrainrMuscleGroup = "chest" | "back" | "shoulders" | "arms" | "legs" | "core" | "full_body";
export type TrainrEquipment = "dumbbell" | "barbell" | "pull_up_bar" | "bodyweight" | "other";

export const TRAINR_ACTIVITY_TYPES: TrainrActivityType[] = ["home_gym", "running", "cycling", "football", "padel"];
export const TRAINR_ACTIVITY_LABELS: Record<TrainrActivityType, string> = {
  home_gym: msg("Home gym"),
  running: msg("Hardlopen"),
  cycling: msg("Fietsen"),
  football: msg("Voetbal"),
  padel: msg("Padel"),
};
/** Which activities carry distance/time/speed rather than exercises -- the backend's
 * DISTANCE_ACTIVITIES, so the form shows the fields the backend will accept. */
export const TRAINR_DISTANCE_ACTIVITIES: ReadonlySet<TrainrActivityType> = new Set(["running", "cycling"]);
/** Football and padel: a time plus calories and heart rate -- the backend's MATCH_ACTIVITIES. */
export const TRAINR_MATCH_ACTIVITIES: ReadonlySet<TrainrActivityType> = new Set(["football", "padel"]);

export const TRAINR_MUSCLE_GROUPS: TrainrMuscleGroup[] = ["chest", "back", "shoulders", "arms", "legs", "core", "full_body"];
export const TRAINR_MUSCLE_GROUP_LABELS: Record<TrainrMuscleGroup, string> = {
  chest: msg("Borst"),
  back: msg("Rug"),
  shoulders: msg("Schouders"),
  arms: msg("Armen"),
  legs: msg("Benen"),
  core: msg("Core"),
  full_body: msg("Full body"),
};

export const TRAINR_EQUIPMENT: TrainrEquipment[] = ["dumbbell", "barbell", "pull_up_bar", "bodyweight", "other"];
export const TRAINR_EQUIPMENT_LABELS: Record<TrainrEquipment, string> = {
  dumbbell: msg("Dumbbells"),
  barbell: msg("Halterstang"),
  pull_up_bar: msg("Optrekstang"),
  bodyweight: msg("Lichaamsgewicht"),
  other: msg("Overig"),
};

/** A how-to demo from the free-exercise-db catalogue (ADR 0040): a start and an end photo to flip
 * between, and the steps (in English, as the catalogue has them). */
export interface TrainrExerciseDemo {
  id: string;
  name: string;
  equipment: string | null;
  image_urls: string[];
  instructions: string[];
}

export interface TrainrExercise {
  id: number;
  name: string;
  muscle_group: TrainrMuscleGroup;
  equipment: TrainrEquipment;
  is_archived: boolean;
  demo_id: string | null;
  demo: TrainrExerciseDemo | null;
  times_performed: number;
  last_performed_on: string | null;
  last_sets: number | null;
  last_reps: number | null;
  last_weight_kg: string | null;
  best_weight_kg: string | null;
}

export interface TrainrExerciseInput {
  name: string;
  muscle_group: TrainrMuscleGroup;
  equipment: TrainrEquipment;
}

export interface TrainrWorkoutEntry {
  id: number;
  exercise_id: number;
  exercise_name: string;
  muscle_group: TrainrMuscleGroup;
  sets: number | null;
  reps: number | null;
  weight_kg: string | null;
  duration_seconds: number | null;
  notes: string | null;
}

export interface TrainrWorkoutEntryInput {
  exercise_id: number;
  sets: number | null;
  reps: number | null;
  weight_kg: string | null;
  duration_seconds: number | null;
  notes: string | null;
}

export interface TrainrWorkout {
  id: number;
  activity_type: TrainrActivityType;
  date: string;
  is_completed: boolean;
  duration_seconds: number | null;
  distance_km: string | null;
  max_speed_kmh: string | null;
  calories_kcal: number | null;
  avg_heart_rate_bpm: number | null;
  max_heart_rate_bpm: number | null;
  notes: string | null;
  entries: TrainrWorkoutEntry[];
  avg_speed_kmh: string | null;
  pace_seconds_per_km: number | null;
  volume_kg: string | null;
}

export interface TrainrWorkoutInput {
  activity_type: TrainrActivityType;
  date: string;
  is_completed: boolean;
  duration_seconds: number | null;
  distance_km: string | null;
  max_speed_kmh: string | null;
  calories_kcal: number | null;
  avg_heart_rate_bpm: number | null;
  max_heart_rate_bpm: number | null;
  notes: string | null;
  entries: TrainrWorkoutEntryInput[];
}

export interface TrainrActivitySummary {
  activity_type: TrainrActivityType;
  workouts: number;
  total_duration_seconds: number;
  total_distance_km: string | null;
  avg_speed_kmh: string | null;
  total_volume_kg: string | null;
  total_calories_kcal: number | null;
  avg_heart_rate_bpm: number | null;
  max_heart_rate_bpm: number | null;
}

export interface TrainrSummary {
  date_from: string;
  date_to: string;
  workouts: number;
  total_duration_seconds: number;
  by_activity: TrainrActivitySummary[];
}

// -- overview (one activity's dashboard) ------------------------------------------------------

export type TrainrPeriodKey = "week" | "month" | "year" | "all";

export interface TrainrPeriodTotals {
  workouts: number;
  duration_seconds: number;
  distance_km: string | null;
  avg_speed_kmh: string | null;
  volume_kg: string | null;
  calories_kcal: number | null;
  avg_heart_rate_bpm: number | null;
  max_heart_rate_bpm: number | null;
}

export interface TrainrPeriodTile {
  key: TrainrPeriodKey;
  date_from: string | null;
  date_to: string;
  current: TrainrPeriodTotals;
  previous: TrainrPeriodTotals | null;
}

export interface TrainrSeriesPoint {
  period_start: string;
  workouts: number;
  duration_seconds: number;
  distance_km: string | null;
  avg_speed_kmh: string | null;
  pace_seconds_per_km: number | null;
  volume_kg: string | null;
  calories_kcal: number | null;
  avg_heart_rate_bpm: number | null;
}

export type TrainrRecordKind =
  | "longest_distance"
  | "longest_duration"
  | "fastest_avg_speed"
  | "best_pace"
  | "heaviest_lift"
  | "biggest_volume"
  | "most_calories"
  | "highest_heart_rate";

export interface TrainrRecord {
  kind: TrainrRecordKind;
  value: string;
  workout_id: number;
  date: string;
  detail: string | null;
}

export interface TrainrMuscleGroupShare {
  muscle_group: TrainrMuscleGroup;
  sets: number;
  volume_kg: string | null;
}

export interface TrainrExerciseProgress {
  exercise_id: number;
  name: string;
  sessions: number;
  best_weight_kg: string | null;
  points: { date: string; max_weight_kg: string | null; volume_kg: string | null }[];
}

export interface TrainrOverview {
  activity_type: TrainrActivityType;
  today: string;
  tiles: TrainrPeriodTile[];
  monthly: TrainrSeriesPoint[];
  yearly: TrainrSeriesPoint[];
  records: TrainrRecord[];
  muscle_groups: TrainrMuscleGroupShare[];
  exercises: TrainrExerciseProgress[];
}
