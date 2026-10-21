import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { trainrApi } from "../../api/trainrClient";
import type { TrainrExerciseDemo, TrainrWorkout, TrainrWorkoutInput } from "../../api/trainrTypes";
import WorkoutDialog from "./WorkoutDialog";
import WorkoutRunner from "./WorkoutRunner";
import { t } from "../../i18n";

/** A planned gym session can be run step by step -- it needs exercises to step through. */
export function canStart(workout: TrainrWorkout): boolean {
  return !workout.is_completed && workout.activity_type === "home_gym" && workout.entries.length > 0;
}

/** Opening, saving, ticking off, running and deleting a workout -- shared by the Planner and the
 * History, so both refresh the same queries (a workout ticked off in one shows up in the other,
 * and its exercises' "vorige keer" moves on). */
export function useWorkoutEditor() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<{ date: string; workout?: TrainrWorkout } | null>(null);
  const [running, setRunning] = useState<TrainrWorkout | null>(null);
  // The runner's demos come with the exercise list (the workout form's query, so usually cached).
  const exercisesQuery = useQuery({
    queryKey: ["trainr-exercises", true],
    queryFn: () => trainrApi.listExercises(true),
    enabled: running !== null,
  });
  const demos = useMemo(() => {
    const byId = new Map<number, TrainrExerciseDemo>();
    for (const e of exercisesQuery.data ?? []) if (e.demo) byId.set(e.id, e.demo);
    return byId;
  }, [exercisesQuery.data]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["trainr-workouts"] });
    queryClient.invalidateQueries({ queryKey: ["trainr-summary"] });
    queryClient.invalidateQueries({ queryKey: ["trainr-exercises"] });
  };

  const save = useMutation({
    mutationFn: ({ id, input }: { id?: number; input: TrainrWorkoutInput }) =>
      id === undefined ? trainrApi.createWorkout(input) : trainrApi.updateWorkout(id, input),
    onSuccess: () => {
      invalidate();
      setEditing(null);
      setRunning(null);
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => trainrApi.deleteWorkout(id),
    onSuccess: () => {
      invalidate();
      setEditing(null);
    },
  });
  const toggle = useMutation({
    mutationFn: (workout: TrainrWorkout) => trainrApi.setWorkoutCompleted(workout.id, !workout.is_completed),
    onSuccess: invalidate,
  });

  const open = (date: string, workout?: TrainrWorkout) => {
    save.reset();
    remove.reset();
    setEditing({ date, workout });
  };

  const start = (workout: TrainrWorkout) => {
    save.reset();
    setRunning(workout);
  };

  const current = editing?.workout;
  const runner = running && (
    <WorkoutRunner
      key={running.id}
      workout={running}
      demos={demos}
      isSaving={save.isPending}
      error={save.isError ? t("Opslaan is mislukt — probeer het opnieuw.") : null}
      onClose={() => setRunning(null)}
      onFinish={(input) => save.mutate({ id: running.id, input })}
    />
  );
  const dialog = editing && (
    <WorkoutDialog
      key={current?.id ?? `new-${editing.date}`}
      workout={current}
      defaultDate={editing.date}
      isSubmitting={save.isPending || remove.isPending}
      error={save.isError ? t("Opslaan is mislukt — probeer het opnieuw.") : remove.isError ? t("Verwijderen is mislukt.") : null}
      onCancel={() => setEditing(null)}
      onSave={(input) => save.mutate({ id: current?.id, input })}
      onDelete={current ? () => remove.mutate(current.id) : undefined}
    />
  );

  return { open, start, toggleCompleted: (w: TrainrWorkout) => toggle.mutate(w), toggleError: toggle.isError, dialog, runner };
}
