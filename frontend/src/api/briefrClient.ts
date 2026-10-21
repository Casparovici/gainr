import type { BriefrAgent, BriefrItem, BriefrReport, BriefrReportDetail, BriefrReportFilter } from "./briefrTypes";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/** briefr reads and triages agent reports; there's no way to create one from the app. The one
 * write beyond that is planning a suggested recipe in listr's weekplanner. */
export const briefrApi = {
  /** The inbox (or with `archived`, the archive), newest run first. */
  listReports: (filter: BriefrReportFilter = {}) => {
    const params = new URLSearchParams();
    if (filter.archived) params.set("archived", "true");
    if (filter.agent) params.set("agent", filter.agent);
    if (filter.attention) params.set("attention", filter.attention);
    const query = params.toString();
    return request<BriefrReport[]>(`/briefr/reports${query ? `?${query}` : ""}`);
  },
  getReport: (id: number) => request<BriefrReportDetail>(`/briefr/reports/${id}`),
  setRead: (id: number, isRead: boolean) =>
    request<BriefrReport>(`/briefr/reports/${id}/read`, { method: "PUT", body: JSON.stringify({ is_read: isRead }) }),
  setArchived: (id: number, isArchived: boolean) =>
    request<BriefrReport>(`/briefr/reports/${id}/archived`, { method: "PUT", body: JSON.stringify({ is_archived: isArchived }) }),
  listAgents: () => request<BriefrAgent[]>("/briefr/agents"),
  /** Plans a suggested recipe on `date`; a day that already has something is only replaced with
   * `replace` (otherwise a 409). */
  planItem: (itemId: number, date: string, replace = false) =>
    request<BriefrItem>(`/briefr/items/${itemId}/plan`, { method: "POST", body: JSON.stringify({ date, replace }) }),
};
