import type {
  TrainrActivityType,
  TrainrExercise,
  TrainrExerciseDemo,
  TrainrExerciseInput,
  TrainrOverview,
  TrainrSummary,
  TrainrWorkout,
  TrainrWorkoutInput,
} from "./trainrTypes";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const trainrApi = {
  listExercises: (includeArchived = false) =>
    request<TrainrExercise[]>(`/trainr/exercises?include_archived=${includeArchived}`),
  createExercise: (input: TrainrExerciseInput) =>
    request<TrainrExercise>("/trainr/exercises", { method: "POST", body: JSON.stringify(input) }),
  updateExercise: (id: number, input: Partial<TrainrExerciseInput> & { is_archived?: boolean; demo_id?: string | null }) =>
    request<TrainrExercise>(`/trainr/exercises/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteExercise: (id: number) => request<void>(`/trainr/exercises/${id}`, { method: "DELETE" }),
  searchExerciseDemos: (query: string) =>
    request<TrainrExerciseDemo[]>(`/trainr/exercise-demos?q=${encodeURIComponent(query)}`),

  listWorkouts: (dateFrom: string, dateTo: string, opts: { activityType?: TrainrActivityType; completed?: boolean } = {}) => {
    const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
    if (opts.activityType) params.set("activity_type", opts.activityType);
    if (opts.completed !== undefined) params.set("completed", String(opts.completed));
    return request<TrainrWorkout[]>(`/trainr/workouts?${params}`);
  },
  getOverview: (activityType: TrainrActivityType) =>
    request<TrainrOverview>(`/trainr/overview?activity_type=${activityType}`),
  getSummary: (dateFrom: string, dateTo: string) =>
    request<TrainrSummary>(`/trainr/summary?date_from=${dateFrom}&date_to=${dateTo}`),
  createWorkout: (input: TrainrWorkoutInput) =>
    request<TrainrWorkout>("/trainr/workouts", { method: "POST", body: JSON.stringify(input) }),
  updateWorkout: (id: number, input: TrainrWorkoutInput) =>
    request<TrainrWorkout>(`/trainr/workouts/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  setWorkoutCompleted: (id: number, isCompleted: boolean) =>
    request<TrainrWorkout>(`/trainr/workouts/${id}/completed`, {
      method: "PUT",
      body: JSON.stringify({ is_completed: isCompleted }),
    }),
  deleteWorkout: (id: number) => request<void>(`/trainr/workouts/${id}`, { method: "DELETE" }),
};
