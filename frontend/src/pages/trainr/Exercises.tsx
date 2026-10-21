import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { trainrApi } from "../../api/trainrClient";
import {
  TRAINR_EQUIPMENT,
  TRAINR_EQUIPMENT_LABELS,
  TRAINR_MUSCLE_GROUP_LABELS,
  TRAINR_MUSCLE_GROUPS,
  type TrainrEquipment,
  type TrainrExercise,
  type TrainrExerciseInput,
  type TrainrMuscleGroup,
} from "../../api/trainrTypes";
import InlineEditText from "../../components/InlineEditText";
import ExerciseDemoPicker from "../../components/trainr/ExerciseDemoPicker";
import { ModuleTopRow, PageTitle, inputClass, primaryButtonClass } from "../../components/ui/kit";
import { entrySummary, formatKg } from "../../utils/trainr";
import { fromIso } from "../../utils/weekCalendar";
import { dateLocale, t } from "../../i18n";

function exerciseStats(e: TrainrExercise): string {
  if (!e.last_performed_on) return t("Nog niet gedaan");
  const last = entrySummary({ sets: e.last_sets, reps: e.last_reps, weight_kg: e.last_weight_kg, duration_seconds: null });
  const day = fromIso(e.last_performed_on).toLocaleDateString(dateLocale("nl-NL"), { day: "numeric", month: "short" });
  return [
    t("{n}× gedaan", { n: e.times_performed }),
    last ? t("laatst {day}: {last}", { day, last }) : t("laatst {day}", { day }),
    e.best_weight_kg ? t("beste {weight}", { weight: formatKg(e.best_weight_kg) }) : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

/** The gym exercise catalogue: the seeded home-gym suggestions plus anything added here or from
 * the workout form. An exercise already used in a workout can be archived (hidden from the
 * picker, kept in the history) but not deleted. Each can link a how-to demo (ADR 0040), which the
 * guided workout shows. */
export default function TrainrExercises() {
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [name, setName] = useState("");
  const [group, setGroup] = useState<TrainrMuscleGroup>("chest");
  const [equipment, setEquipment] = useState<TrainrEquipment>("dumbbell");
  const [rowError, setRowError] = useState<string | null>(null);
  const [demoFor, setDemoFor] = useState<number | null>(null);

  const exercisesQuery = useQuery({
    queryKey: ["trainr-exercises", showArchived],
    queryFn: () => trainrApi.listExercises(showArchived),
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["trainr-exercises"] });

  const create = useMutation({
    mutationFn: (input: TrainrExerciseInput) => trainrApi.createExercise(input),
    onSuccess: () => {
      invalidate();
      setName("");
    },
  });
  const update = useMutation({
    mutationFn: ({ id, input }: { id: number; input: Partial<TrainrExerciseInput> & { is_archived?: boolean } }) =>
      trainrApi.updateExercise(id, input),
    onSuccess: () => {
      setRowError(null);
      invalidate();
    },
    onError: (err: Error) => setRowError(err.message.startsWith("409") ? t("Die naam bestaat al.") : t("Opslaan is mislukt.")),
  });
  const linkDemo = useMutation({
    mutationFn: ({ id, demoId }: { id: number; demoId: string | null }) => trainrApi.updateExercise(id, { demo_id: demoId }),
    onSuccess: async (_, { demoId }) => {
      await invalidate();
      if (demoId !== null) setDemoFor(null);
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => trainrApi.deleteExercise(id),
    onSuccess: () => {
      setRowError(null);
      invalidate();
    },
    onError: (err: Error) =>
      setRowError(err.message.startsWith("409") ? t("Deze oefening staat in een workout — archiveer hem in plaats daarvan.") : t("Verwijderen is mislukt.")),
  });

  const exercises = exercisesQuery.data ?? [];
  const picking = exercises.find((e) => e.id === demoFor);

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow />
      <PageTitle subtitle={t("{n} oefeningen in je catalogus", { n: exercises.filter((e) => !e.is_archived).length })}>{t("Oefeningen")}</PageTitle>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) create.mutate({ name: name.trim(), muscle_group: group, equipment });
        }}
        className="flex flex-col gap-2 rounded-[20px] border border-ui-border bg-ui-surface p-4 sm:flex-row sm:items-center"
      >
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("Nieuwe oefening, bv. Zercher squat")} aria-label={t("Naam")} className={inputClass} />
        <div className="grid grid-cols-2 gap-2 sm:flex">
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
        <button type="submit" disabled={!name.trim() || create.isPending} className={`${primaryButtonClass} h-11 shrink-0`}>{t("Toevoegen")}</button>
      </form>
      {create.isError && (
        <p className="text-sm text-red-600">{create.error.message.startsWith("409") ? t("Die oefening bestaat al.") : t("Toevoegen is mislukt.")}</p>
      )}
      {rowError && <p className="text-sm text-red-600">{rowError}</p>}

      <label className="flex items-center gap-2 self-end text-sm text-ui-muted">
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />{t("Toon gearchiveerde")}</label>

      {exercisesQuery.isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-400">{t("Laden…")}</div>
      ) : exercisesQuery.isError ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">{t("Kon de oefeningen niet laden.")}{" "}
          <button onClick={() => exercisesQuery.refetch()} className="font-medium text-slate-900 underline">{t("Opnieuw proberen")}</button>
        </div>
      ) : exercises.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-400">{t("Nog geen oefeningen — voeg je eerste hierboven toe.")}</div>
      ) : (
        TRAINR_MUSCLE_GROUPS.map((g) => {
          const inGroup = exercises.filter((e) => e.muscle_group === g);
          if (inGroup.length === 0) return null;
          return (
            <section key={g} className="rounded-[20px] border border-ui-border bg-ui-surface p-4">
              <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">{t(TRAINR_MUSCLE_GROUP_LABELS[g])}</h2>
              <ul className="m-0 mt-2 flex list-none flex-col p-0">
                {inGroup.map((e) => (
                  <li key={e.id} className="flex min-h-[52px] flex-col gap-1 border-b border-ui-border py-2 last:border-0 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex min-w-0 items-center gap-3">
                      {e.demo && (
                        <button type="button" onClick={() => setDemoFor(e.id)} aria-label={t("Voorbeeld van {name}", { name: e.name })} className="shrink-0">
                          <img src={e.demo.image_urls[0]} alt="" loading="lazy" className="h-10 w-[3.75rem] rounded-md border border-ui-border bg-white object-contain" />
                        </button>
                      )}
                      <div className="flex min-w-0 flex-col">
                        <div className={`flex min-w-0 items-center gap-2 ${e.is_archived ? "opacity-60" : ""}`}>
                          <InlineEditText
                            value={e.name}
                            title={t("Naam wijzigen")}
                            textClassName="truncate text-[15px] font-semibold text-ui-ink"
                            onSave={(value) => value.trim() && value.trim() !== e.name && update.mutate({ id: e.id, input: { name: value.trim() } })}
                          />
                          <span className="shrink-0 text-xs text-ui-muted">{t(TRAINR_EQUIPMENT_LABELS[e.equipment])}</span>
                        </div>
                        <span className="text-sm text-ui-ink-soft">{exerciseStats(e)}</span>
                      </div>
                    </div>
                    <div className="flex shrink-0 gap-3 text-xs font-medium">
                      <button
                        onClick={() => {
                          linkDemo.reset();
                          setDemoFor(e.id);
                        }}
                        className="text-slate-500 hover:text-slate-800"
                      >
                        {e.demo ? t("Voorbeeld") : t("Voorbeeld kiezen")}
                      </button>
                      <button
                        onClick={() => update.mutate({ id: e.id, input: { is_archived: !e.is_archived } })}
                        className="text-slate-500 hover:text-slate-800"
                      >
                        {e.is_archived ? t("Terugzetten") : t("Archiveren")}
                      </button>
                      {e.times_performed === 0 && (
                        <button
                          onClick={() => {
                            if (confirm(t("\"{name}\" definitief verwijderen? Dit kan alleen zolang hij in geen enkele workout staat.", { name: e.name }))) remove.mutate(e.id);
                          }}
                          className="text-slate-400 hover:text-red-600"
                        >{t("Verwijderen")}</button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          );
        })
      )}

      {picking && (
        <ExerciseDemoPicker
          exercise={picking}
          isSaving={linkDemo.isPending}
          error={linkDemo.isError ? t("Opslaan is mislukt — probeer het opnieuw.") : null}
          onPick={(demoId) => linkDemo.mutate({ id: picking.id, demoId })}
          onClose={() => setDemoFor(null)}
        />
      )}
    </div>
  );
}
