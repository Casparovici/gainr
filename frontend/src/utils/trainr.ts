import type { TrainrExercise, TrainrWorkout, TrainrWorkoutEntry } from "../api/trainrTypes";
import { TRAINR_ACTIVITY_LABELS } from "../api/trainrTypes";
import { toNumber } from "./format";
import { addDays, fromIso, isoWeekNumber } from "./weekCalendar";
import { dateLocale, t, tp } from "../i18n";

// Numbers keep the European notation in both languages; dates follow the chosen language.
const NUMBER_LOCALE = "nl-NL";

/** Seconds from what the user typed as a duration: "45" (minutes), "45:30" (min:sec) or
 * "1:02:15" (h:min:sec). Null for anything else, including an empty field. */
export function parseDuration(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parts = trimmed.split(":");
  if (parts.length > 3 || parts.some((p) => !/^\d+$/.test(p))) return null;
  const nums = parts.map(Number);
  let seconds: number;
  if (nums.length === 1) seconds = nums[0] * 60;
  else if (nums.length === 2) seconds = nums[0] * 60 + nums[1];
  else seconds = nums[0] * 3600 + nums[1] * 60 + nums[2];
  if (nums.length > 1 && nums[nums.length - 1] >= 60) return null;
  if (nums.length === 3 && nums[1] >= 60) return null;
  return seconds > 0 ? seconds : null;
}

/** "45:30" or "1:02:15" -- the same shape parseDuration reads back. */
export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

/** A total for the history tiles: "2 u 15 min", "45 min". */
export function formatDurationLong(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  if (h === 0) return t("{m} min", { m });
  return m === 0 ? t("{h} u", { h }) : t("{h} u {m} min", { h, m });
}

/** "5:12 /km" */
export function formatPace(secondsPerKm: number | null | undefined): string {
  if (!secondsPerKm) return "—";
  return `${formatDuration(secondsPerKm)} /km`;
}

function formatNumber(value: string | null | undefined, maxDigits: number): string | null {
  const n = toNumber(value ?? null);
  if (n === null) return null;
  return n.toLocaleString(NUMBER_LOCALE, { maximumFractionDigits: maxDigits });
}

/** "10,5 km" */
export function formatKm(value: string | null | undefined): string {
  const n = formatNumber(value, 2);
  return n === null ? "—" : `${n} km`;
}

/** "24,3 km/u" */
export function formatSpeed(value: string | null | undefined): string {
  const n = formatNumber(value, 1);
  return n === null ? "—" : t("{n} km/u", { n });
}

/** "640 kcal" */
export function formatKcal(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toLocaleString(NUMBER_LOCALE)} kcal`;
}

/** "148 bpm" */
export function formatBpm(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value} bpm`;
}

/** "12,5 kg" */
export function formatKg(value: string | null | undefined): string {
  const n = formatNumber(value, 2);
  return n === null ? "—" : `${n} kg`;
}

/** One exercise line: "3 × 10 · 12,5 kg", "3 × 0:45" for a timed hold, or "" when nothing was
 * filled in yet (a planned exercise). A counted exercise that was timed (a guided workout) ends
 * with the time it took: "3 × 10 · 12,5 kg · 2:10". */
export function entrySummary(entry: Pick<TrainrWorkoutEntry, "sets" | "reps" | "weight_kg" | "duration_seconds">): string {
  const parts: string[] = [];
  const work = entry.reps !== null ? String(entry.reps) : entry.duration_seconds ? formatDuration(entry.duration_seconds) : null;
  if (entry.sets !== null && work !== null) parts.push(`${entry.sets} × ${work}`);
  else if (entry.sets !== null) parts.push(t("{n} sets", { n: entry.sets }));
  else if (work !== null) parts.push(work);
  if (entry.weight_kg !== null) parts.push(formatKg(entry.weight_kg));
  if (entry.reps !== null && entry.duration_seconds) parts.push(formatDuration(entry.duration_seconds));
  return parts.join(" · ");
}

/** The "vorige keer" hint under an exercise in the form, from the exercise's own stats. */
export function lastTimeHint(exercise: TrainrExercise | undefined): string | null {
  if (!exercise?.last_performed_on) return null;
  const summary = entrySummary({
    sets: exercise.last_sets,
    reps: exercise.last_reps,
    weight_kg: exercise.last_weight_kg,
    duration_seconds: null,
  });
  const day = new Date(exercise.last_performed_on + "T00:00:00").toLocaleDateString(dateLocale("nl-NL"), { day: "numeric", month: "short" });
  return summary ? t("Vorige keer ({day}): {summary}", { day, summary }) : t("Vorige keer: {day}", { day });
}

/** A workout's one-line headline for a planner chip or a history row: the distance for a run or
 * ride, the exercise count for a gym session. */
export function workoutHeadline(workout: TrainrWorkout): string {
  const label = t(TRAINR_ACTIVITY_LABELS[workout.activity_type]);
  if (workout.distance_km) return `${label} · ${formatKm(workout.distance_km)}`;
  if (workout.entries.length > 0) {
    return `${label} · ${tp(workout.entries.length, "{n} oefening", "{n} oefeningen")}`;
  }
  return label;
}

/** A stored decimal ("12.50") as a form field value without trailing zeros ("12,5"). */
export function decimalToInput(value: string | null | undefined): string {
  const n = toNumber(value ?? null);
  return n === null ? "" : String(n).replace(".", ",");
}

/** A headline distance: one decimal below 100 km, whole km above ("15.902 km"). */
export function formatKmRounded(value: string | null | undefined): string {
  const n = toNumber(value ?? null);
  if (n === null) return "0 km";
  return `${n.toLocaleString(NUMBER_LOCALE, { maximumFractionDigits: Math.abs(n) < 100 ? 1 : 0 })} km`;
}

/** "+12 km" / "−3,5 km" / "even veel" -- a tile's change against the previous period. */
export function formatKmDelta(current: string | null, previous: string | null): string {
  const diff = (toNumber(current) ?? 0) - (toNumber(previous) ?? 0);
  if (Math.abs(diff) < 0.05) return t("even veel");
  const text = formatKmRounded(String(Math.abs(diff)));
  return `${diff > 0 ? "+" : "−"}${text}`;
}

/** "+2" / "−1" / "even veel" for a count. */
export function formatCountDelta(current: number, previous: number): string {
  const diff = current - previous;
  return diff === 0 ? t("even veel") : `${diff > 0 ? "+" : "−"}${Math.abs(diff)}`;
}

/** A Monday-based week's heading in Historie: "Week 42 · 12 – 18 okt 2026", "Week 1 · 29 dec 2025 – 4 jan 2026". */
export function formatWeekLabel(mondayIso: string): string {
  const start = fromIso(mondayIso);
  const end = fromIso(addDays(mondayIso, 6));
  const sameYear = start.getFullYear() === end.getFullYear();
  const startText = sameYear && start.getMonth() === end.getMonth()
    ? String(start.getDate())
    : start.toLocaleDateString(dateLocale("nl-NL"), { day: "numeric", month: "short", ...(sameYear ? {} : { year: "numeric" }) });
  const endText = end.toLocaleDateString(dateLocale("nl-NL"), { day: "numeric", month: "short", year: "numeric" });
  return t("Week {week} · {start} – {end}", { week: isoWeekNumber(mondayIso), start: startText, end: endText });
}
