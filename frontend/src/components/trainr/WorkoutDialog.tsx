import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { trainrApi } from "../../api/trainrClient";
import {
  TRAINR_DISTANCE_ACTIVITIES,
  TRAINR_MATCH_ACTIVITIES,
  TRAINR_EQUIPMENT,
  TRAINR_EQUIPMENT_LABELS,
  TRAINR_MUSCLE_GROUP_LABELS,
  TRAINR_MUSCLE_GROUPS,
  type TrainrActivityType,
  type TrainrEquipment,
  type TrainrExercise,
  type TrainrMuscleGroup,
  type TrainrWorkout,
  type TrainrWorkoutInput,
} from "../../api/trainrTypes";
import { decimalInputToApi, todayIsoDate } from "../../utils/format";
import { decimalToInput, formatDuration, formatPace, formatSpeed, lastTimeHint, parseDuration } from "../../utils/trainr";
import ModalOverlay from "../ModalOverlay";
import { IconPlus, IconTrash } from "../ui/kit";
import ActivitySelect from "./ActivitySelect";
import { dateLocale, t } from "../../i18n";

const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const labelClass = "text-xs font-medium uppercase tracking-wide text-slate-500";
const NEW_EXERCISE = "new";

interface EntryDraft {
  key: number;
  exerciseId: number | null;
  sets: string;
  reps: string;
  weight: string;
  duration: string;
}

let nextKey = 1;
function emptyEntry(): EntryDraft {
  return { key: nextKey++, exerciseId: null, sets: "", reps: "", weight: "", duration: "" };
}

/** "" -> null, "12" -> 12, anything else -> undefined (invalid). */
function parseCount(value: string): number | null | undefined {
  const trimmed = value.trim();
  if (!trimmed) return null;
  return /^\d+$/.test(trimmed) && Number(trimmed) > 0 ? Number(trimmed) : undefined;
}
/** A heart rate in bpm: "" -> null, a whole number from 30 to 250 -> that, anything else -> undefined. */
function parseHeartRate(value: string): number | null | undefined {
  const parsed = parseCount(value);
  return parsed === undefined || parsed === null ? parsed : parsed >= 30 && parsed <= 250 ? parsed : undefined;
}
function parseOptionalDuration(value: string): number | null | undefined {
  if (!value.trim()) return null;
  return parseDuration(value) ?? undefined;
}
function parseOptionalDecimal(value: string): string | null | undefined {
  if (!value.trim()) return null;
  const parsed = decimalInputToApi(value);
  return parsed !== null && Number(parsed) >= 0 ? parsed : undefined;
}

function formatDayHeader(dateIso: string): string {
  return new Date(dateIso + "T00:00:00").toLocaleDateString(dateLocale("nl-NL"), { weekday: "long", day: "numeric", month: "long" });
}

/** The exercise picker: the catalogue grouped by muscle group, plus "Nieuwe oefening…". An
 * archived exercise only shows up while it's the one already picked. */
function ExerciseSelect({
  value,
  exercises,
  onChange,
  label,
}: {
  value: number | null;
  exercises: TrainrExercise[];
  onChange: (value: number | typeof NEW_EXERCISE | null) => void;
  label: string;
}) {
  const visible = exercises.filter((e) => !e.is_archived || e.id === value);
  return (
    <select
      aria-label={label}
      value={value ?? ""}
      onChange={(e) => {
        const v = e.target.value;
        onChange(v === "" ? null : v === NEW_EXERCISE ? NEW_EXERCISE : Number(v));
      }}
      className={inputClass}
    >
      <option value="">{t("Kies een oefening…")}</option>
      {TRAINR_MUSCLE_GROUPS.map((group) => {
        const inGroup = visible.filter((e) => e.muscle_group === group);
        if (inGroup.length === 0) return null;
        return (
          <optgroup key={group} label={t(TRAINR_MUSCLE_GROUP_LABELS[group])}>
            {inGroup.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </optgroup>
        );
      })}
      <option value={NEW_EXERCISE}>{t("+ Nieuwe oefening…")}</option>
    </select>
  );
}

/** Adding an exercise without leaving the workout: name, muscle group and equipment. */
function NewExerciseForm({ onCreated, onCancel }: { onCreated: (exercise: TrainrExercise) => void; onCancel: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [group, setGroup] = useState<TrainrMuscleGroup>("chest");
  const [equipment, setEquipment] = useState<TrainrEquipment>("dumbbell");
  const create = useMutation({
    mutationFn: () => trainrApi.createExercise({ name: name.trim(), muscle_group: group, equipment }),
    onSuccess: (exercise) => {
      queryClient.invalidateQueries({ queryKey: ["trainr-exercises"] });
      onCreated(exercise);
    },
  });
  return (
    <div className="flex flex-col gap-2 rounded-md bg-slate-50 p-3">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("Naam, bv. Zercher squat")} aria-label={t("Naam nieuwe oefening")} className={inputClass} autoFocus />
      <div className="grid grid-cols-2 gap-2">
        <select value={group} onChange={(e) => setGroup(e.target.value as TrainrMuscleGroup)} aria-label={t("Spiergroep")} className={inputClass}>
          {TRAINR_MUSCLE_GROUPS.map((g) => (
            <option key={g} value={g}>
              {t(TRAINR_MUSCLE_GROUP_LABELS[g])}
            </option>
          ))}
        </select>
        <select value={equipment} onChange={(e) => setEquipment(e.target.value as TrainrEquipment)} aria-label={t("Materiaal")} className={inputClass}>
          {TRAINR_EQUIPMENT.map((eq) => (
            <option key={eq} value={eq}>
              {t(TRAINR_EQUIPMENT_LABELS[eq])}
            </option>
          ))}
        </select>
      </div>
      {create.isError && (
        <p className="text-xs text-red-600">{create.error.message.startsWith("409") ? t("Die oefening bestaat al.") : t("Toevoegen is mislukt.")}</p>
      )}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="text-xs font-medium text-slate-500 hover:text-slate-800">{t("Annuleren")}</button>
        <button
          type="button"
          onClick={() => create.mutate()}
          disabled={!name.trim() || create.isPending}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >{t("Oefening toevoegen")}</button>
      </div>
    </div>
  );
}

/** Log or plan one workout. Opened from a planner day (with that date), the history, or the
 * "Workout" button (today). Running and cycling take distance, time and top speed -- average
 * speed and pace come back from the backend once saved; a home gym session takes exercises,
 * each with sets, reps, the weight in kg, or a time for a hold. */
export default function WorkoutDialog({
  workout,
  defaultDate,
  isSubmitting,
  error,
  onCancel,
  onSave,
  onDelete,
}: {
  workout?: TrainrWorkout;
  defaultDate: string;
  isSubmitting: boolean;
  error?: string | null;
  onCancel: () => void;
  onSave: (input: TrainrWorkoutInput) => void;
  onDelete?: () => void;
}) {
  const exercisesQuery = useQuery({ queryKey: ["trainr-exercises", true], queryFn: () => trainrApi.listExercises(true) });
  const exercises = exercisesQuery.data ?? [];

  const [activityType, setActivityType] = useState<TrainrActivityType>(workout?.activity_type ?? "home_gym");
  const [date, setDate] = useState(workout?.date ?? defaultDate);
  // A new workout on today or earlier is most likely being logged after the fact; a future one is
  // being planned.
  const [isCompleted, setIsCompleted] = useState(workout?.is_completed ?? defaultDate <= todayIsoDate());
  const [distance, setDistance] = useState(decimalToInput(workout?.distance_km));
  const [duration, setDuration] = useState(formatDuration(workout?.duration_seconds));
  const [maxSpeed, setMaxSpeed] = useState(decimalToInput(workout?.max_speed_kmh));
  const [calories, setCalories] = useState(workout?.calories_kcal?.toString() ?? "");
  const [avgHeartRate, setAvgHeartRate] = useState(workout?.avg_heart_rate_bpm?.toString() ?? "");
  const [maxHeartRate, setMaxHeartRate] = useState(workout?.max_heart_rate_bpm?.toString() ?? "");
  const [notes, setNotes] = useState(workout?.notes ?? "");
  const [entries, setEntries] = useState<EntryDraft[]>(() =>
    workout && workout.entries.length > 0
      ? workout.entries.map((e) => ({
          key: nextKey++,
          exerciseId: e.exercise_id,
          sets: e.sets?.toString() ?? "",
          reps: e.reps?.toString() ?? "",
          weight: decimalToInput(e.weight_kg),
          duration: formatDuration(e.duration_seconds),
        }))
      : [emptyEntry()],
  );
  const [creatingFor, setCreatingFor] = useState<number | null>(null);

  const isDistance = TRAINR_DISTANCE_ACTIVITIES.has(activityType);
  const isMatch = TRAINR_MATCH_ACTIVITIES.has(activityType);
  const exerciseById = new Map(exercises.map((e) => [e.id, e]));

  function updateEntry(key: number, patch: Partial<EntryDraft>) {
    setEntries((rows) => rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  // Picking an exercise into an untouched row starts it from last time's numbers -- the usual
  // next session is "the same, maybe a bit heavier".
  function pickExercise(row: EntryDraft, exercise: TrainrExercise) {
    const untouched = !row.sets && !row.reps && !row.weight && !row.duration;
    updateEntry(row.key, {
      exerciseId: exercise.id,
      ...(untouched && exercise.last_performed_on
        ? {
            sets: exercise.last_sets?.toString() ?? "",
            reps: exercise.last_reps?.toString() ?? "",
            weight: decimalToInput(exercise.last_weight_kg),
          }
        : {}),
    });
  }

  // Parse everything once; `undefined` marks a field the user filled in but that doesn't parse.
  const parsedDuration = parseOptionalDuration(duration);
  const parsedDistance = parseOptionalDecimal(distance);
  const parsedMaxSpeed = parseOptionalDecimal(maxSpeed);
  const parsedCalories = parseCount(calories);
  const parsedAvgHeartRate = parseHeartRate(avgHeartRate);
  const parsedMaxHeartRate = parseHeartRate(maxHeartRate);
  const parsedEntries = entries
    .filter((r) => r.exerciseId !== null)
    .map((r) => ({
      exercise_id: r.exerciseId as number,
      sets: parseCount(r.sets),
      reps: parseCount(r.reps),
      weight_kg: parseOptionalDecimal(r.weight),
      duration_seconds: parseOptionalDuration(r.duration),
      notes: null,
    }));
  const invalid: string[] = [];
  if (parsedDuration === undefined) invalid.push(t("Tijd: gebruik minuten, mm:ss of u:mm:ss."));
  if (isDistance && parsedDistance === undefined) invalid.push(t("Afstand is geen getal."));
  if (isDistance && parsedMaxSpeed === undefined) invalid.push(t("Snelheid is geen getal."));
  if (isMatch && parsedCalories === undefined) invalid.push(t("Calorieën is een heel getal."));
  if (isMatch && (parsedAvgHeartRate === undefined || parsedMaxHeartRate === undefined)) {
    invalid.push(t("Hartslag is een heel getal van 30 tot 250."));
  } else if (isMatch && parsedAvgHeartRate && parsedMaxHeartRate && parsedAvgHeartRate > parsedMaxHeartRate) {
    invalid.push(t("De gemiddelde hartslag kan niet hoger zijn dan de maximale."));
  }
  if (
    !isDistance &&
    !isMatch &&
    parsedEntries.some((e) => e.sets === undefined || e.reps === undefined || e.weight_kg === undefined || e.duration_seconds === undefined)
  ) {
    invalid.push(t("Sets en herhalingen zijn hele getallen, kg een getal, tijd mm:ss."));
  }

  function submit() {
    if (invalid.length > 0) return;
    onSave({
      activity_type: activityType,
      date,
      is_completed: isCompleted,
      duration_seconds: parsedDuration ?? null,
      distance_km: isDistance ? (parsedDistance ?? null) : null,
      max_speed_kmh: isDistance ? (parsedMaxSpeed ?? null) : null,
      calories_kcal: isMatch ? (parsedCalories ?? null) : null,
      avg_heart_rate_bpm: isMatch ? (parsedAvgHeartRate ?? null) : null,
      max_heart_rate_bpm: isMatch ? (parsedMaxHeartRate ?? null) : null,
      notes: notes.trim() || null,
      entries: isDistance || isMatch
        ? []
        : parsedEntries.map((e) => ({
            exercise_id: e.exercise_id,
            sets: e.sets ?? null,
            reps: e.reps ?? null,
            weight_kg: e.weight_kg ?? null,
            duration_seconds: e.duration_seconds ?? null,
            notes: null,
          })),
    });
  }

  return (
    <ModalOverlay onClose={onCancel} cardClassName="flex max-h-[90vh] w-full max-w-lg flex-col rounded-lg bg-white shadow-lg">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex min-h-0 flex-col"
      >
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-base font-semibold capitalize text-slate-900">
            {workout ? t("Workout bewerken") : isCompleted ? t("Workout loggen") : t("Workout plannen")} · {formatDayHeader(date)}
          </h2>
        </div>

        <div className="flex min-h-0 flex-col gap-4 overflow-y-auto px-5 py-4">
          <ActivitySelect value={activityType} onChange={setActivityType} />

          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm">
              <span className={labelClass}>{t("Datum")}</span>
              <input type="date" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} required className={inputClass} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className={labelClass}>{t("Tijd")}</span>
              <input value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="45:00" inputMode="numeric" className={inputClass} />
            </label>
          </div>

          {isDistance ? (
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1 text-sm">
                <span className={labelClass}>{t("Afstand (km)")}</span>
                <input value={distance} onChange={(e) => setDistance(e.target.value)} placeholder="10,5" inputMode="decimal" className={inputClass} />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className={labelClass}>{t("Topsnelheid (km/u)")}</span>
                <input value={maxSpeed} onChange={(e) => setMaxSpeed(e.target.value)} placeholder={t("optioneel")} inputMode="decimal" className={inputClass} />
              </label>
              {workout?.avg_speed_kmh && workout.activity_type === activityType && (
                <p className="col-span-2 text-xs text-slate-500">{t("Gemiddeld {speed} · {pace} (bij de laatste keer opslaan)", { speed: formatSpeed(workout.avg_speed_kmh), pace: formatPace(workout.pace_seconds_per_km) })}</p>
              )}
            </div>
          ) : isMatch ? (
            <div className="grid grid-cols-3 gap-3">
              {(
                [
                  [t("Calorieën (kcal)"), calories, setCalories, "520"],
                  [t("Gem. hartslag (bpm)"), avgHeartRate, setAvgHeartRate, "140"],
                  [t("Max. hartslag (bpm)"), maxHeartRate, setMaxHeartRate, "178"],
                ] as const
              ).map(([fieldLabel, value, setValue, placeholder]) => (
                <label key={fieldLabel} className="flex min-w-0 flex-col gap-1 text-sm">
                  <span className={labelClass}>{fieldLabel}</span>
                  <input value={value} onChange={(e) => setValue(e.target.value)} placeholder={placeholder} inputMode="numeric" className={inputClass} />
                </label>
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <span className={labelClass}>{t("Oefeningen")}</span>
              {exercisesQuery.isError && <p className="text-sm text-red-600">{t("Kon de oefeningen niet laden.")}</p>}
              {entries.map((row, i) => {
                const exercise = row.exerciseId !== null ? exerciseById.get(row.exerciseId) : undefined;
                const hint = lastTimeHint(exercise);
                return (
                  <div key={row.key} className="flex flex-col gap-2 rounded-md border border-slate-200 p-3">
                    <div className="flex items-center gap-2">
                      <ExerciseSelect
                        value={row.exerciseId}
                        exercises={exercises}
                        label={t("Oefening {n}", { n: i + 1 })}
                        onChange={(value) => {
                          if (value === NEW_EXERCISE) setCreatingFor(row.key);
                          else if (value === null) updateEntry(row.key, { exerciseId: null });
                          else {
                            const picked = exerciseById.get(value);
                            if (picked) pickExercise(row, picked);
                          }
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => setEntries((rows) => (rows.length === 1 ? [emptyEntry()] : rows.filter((r) => r.key !== row.key)))}
                        aria-label={t("Oefening {n} verwijderen", { n: i + 1 })}
                        className="shrink-0 p-1 text-slate-400 hover:text-red-600"
                      >
                        <IconTrash size={18} />
                      </button>
                    </div>
                    {creatingFor === row.key && (
                      <NewExerciseForm
                        onCancel={() => setCreatingFor(null)}
                        onCreated={(created) => {
                          setCreatingFor(null);
                          updateEntry(row.key, { exerciseId: created.id });
                        }}
                      />
                    )}
                    <div className="grid grid-cols-4 gap-2">
                      {(
                        [
                          ["sets", t("Sets"), "3", "numeric"],
                          ["reps", t("Herh."), "10", "numeric"],
                          ["weight", t("Kg"), "12,5", "decimal"],
                          ["duration", t("Tijd"), "0:45", "numeric"],
                        ] as const
                      ).map(([field, fieldLabel, placeholder, mode]) => (
                        <label key={field} className="flex min-w-0 flex-col gap-1 text-sm">
                          <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{fieldLabel}</span>
                          <input
                            value={row[field]}
                            onChange={(e) => updateEntry(row.key, { [field]: e.target.value })}
                            placeholder={placeholder}
                            inputMode={mode}
                            aria-label={t("{field} oefening {n}", { field: fieldLabel, n: i + 1 })}
                            className={inputClass}
                          />
                        </label>
                      ))}
                    </div>
                    {hint && <p className="text-xs text-slate-500">{hint}</p>}
                  </div>
                );
              })}
              <button
                type="button"
                onClick={() => setEntries((rows) => [...rows, emptyEntry()])}
                className="flex h-11 items-center justify-center gap-1.5 rounded-xl border-2 border-dashed border-ui-line text-sm font-semibold text-ui-brand-strong hover:border-ui-brand"
              >
                <IconPlus size={16} />{t("Oefening toevoegen")}</button>
            </div>
          )}

          <label className="flex flex-col gap-1 text-sm">
            <span className={labelClass}>{t("Notitie (optioneel)")}</span>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder={t("bv. zware benen, intervallen 6×400 m…")} className={inputClass} />
          </label>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={isCompleted} onChange={(e) => setIsCompleted(e.target.checked)} />{t("Gedaan")}</label>

          {invalid.map((msg) => (
            <p key={msg} className="text-sm text-red-600">
              {msg}
            </p>
          ))}
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-slate-200 px-5 py-3">
          {onDelete ? (
            <button
              type="button"
              onClick={() => {
                if (confirm(t("Deze workout verwijderen? Hij verdwijnt uit de planner en de historie."))) onDelete();
              }}
              disabled={isSubmitting}
              className="text-xs font-medium text-slate-400 hover:text-red-600 disabled:opacity-50"
            >{t("Verwijderen")}</button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button type="button" onClick={onCancel} className="rounded-md px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">{t("Annuleren")}</button>
            <button
              type="submit"
              disabled={isSubmitting || invalid.length > 0}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >{t("Opslaan")}</button>
          </div>
        </div>
      </form>
    </ModalOverlay>
  );
}
