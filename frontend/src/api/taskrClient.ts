import type { Agenda, TaskrTask, TaskrTaskInput, Today } from "./taskrTypes";

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

/** taskr reads the other modules' items (completed in their own module) and owns its tasks. */
export const taskrApi = {
  /** What's due from `dateFrom` to `dateTo` (inclusive, YYYY-MM-DD, at most 366 days apart), plus
   * everything still open from before `dateFrom`. */
  getAgenda: (dateFrom: string, dateTo: string) =>
    request<Agenda>(`/taskr/agenda?${new URLSearchParams({ date_from: dateFrom, date_to: dateTo })}`),
  /** Vandaag: today's agenda and what waits in each module; `portfolioId` picks the gainr
   * portfolio shown (the first one without it). */
  getToday: (portfolioId: number | null) =>
    request<Today>(`/taskr/today${portfolioId !== null ? `?portfolio_id=${portfolioId}` : ""}`),
  createTask: (input: TaskrTaskInput) => request<TaskrTask>("/taskr/tasks", { method: "POST", body: JSON.stringify(input) }),
  updateTask: (id: number, input: Partial<TaskrTaskInput>) =>
    request<TaskrTask>(`/taskr/tasks/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  setTaskCompleted: (id: number, isCompleted: boolean) =>
    request<TaskrTask>(`/taskr/tasks/${id}/completed`, { method: "PUT", body: JSON.stringify({ is_completed: isCompleted }) }),
  deleteTask: (id: number) => request<void>(`/taskr/tasks/${id}`, { method: "DELETE" }),
};
