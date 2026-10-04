import type {
  GardenArea,
  GardenAreaDetail,
  GardenCareLog,
  GardenCareSchedule,
  GardenPlant,
  GardenPlantDetail,
  GardenPlantListRow,
  GardenZone,
} from "./gardnrTypes";

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

export const gardnrApi = {
  listAreas: () => request<GardenArea[]>("/gardnr/areas"),
  createArea: (name: string) => request<GardenArea>("/gardnr/areas", { method: "POST", body: JSON.stringify({ name }) }),
  updateArea: (id: number, input: { name?: string }) =>
    request<GardenArea>(`/gardnr/areas/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteArea: (id: number) => request<void>(`/gardnr/areas/${id}`, { method: "DELETE" }),
  reorderAreas: (areaIds: number[]) =>
    request<void>("/gardnr/areas/reorder", { method: "PUT", body: JSON.stringify({ area_ids: areaIds }) }),
  getAreaDetail: (id: number) => request<GardenAreaDetail>(`/gardnr/areas/${id}`),

  createZone: (areaId: number, input: Omit<GardenZone, "id" | "area_id" | "sort_order">) =>
    request<GardenZone>(`/gardnr/areas/${areaId}/zones`, { method: "POST", body: JSON.stringify(input) }),
  updateZone: (id: number, input: Partial<Omit<GardenZone, "id" | "area_id" | "sort_order">>) =>
    request<GardenZone>(`/gardnr/zones/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteZone: (id: number) => request<void>(`/gardnr/zones/${id}`, { method: "DELETE" }),

  listPlants: (includeArchived = false) =>
    request<GardenPlantListRow[]>(`/gardnr/plants?include_archived=${includeArchived}`),
  createPlant: (input: Partial<GardenPlant> & { area_id: number; name: string; type: GardenPlant["type"] }) =>
    request<GardenPlant>("/gardnr/plants", { method: "POST", body: JSON.stringify(input) }),
  updatePlant: (id: number, input: Partial<GardenPlant>) =>
    request<GardenPlant>(`/gardnr/plants/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deletePlant: (id: number) => request<void>(`/gardnr/plants/${id}`, { method: "DELETE" }),
  getPlantDetail: (id: number) => request<GardenPlantDetail>(`/gardnr/plants/${id}`),

  createLog: (plantId: number, input: Omit<GardenCareLog, "id" | "plant_id" | "has_photo">) =>
    request<GardenCareLog>(`/gardnr/plants/${plantId}/logs`, { method: "POST", body: JSON.stringify(input) }),
  updateLog: (id: number, input: Partial<Omit<GardenCareLog, "id" | "plant_id" | "has_photo">>) =>
    request<GardenCareLog>(`/gardnr/logs/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteLog: (id: number) => request<void>(`/gardnr/logs/${id}`, { method: "DELETE" }),

  // A log's photo is its own multipart action, not part of the JSON create/update above --
  // matching listr's picnic-mapping precedent for "a deliberate one-time step" over "just
  // another form field" (see docs/adr/0012's addendum).
  setLogPhoto: (logId: number, file: File) => {
    const body = new FormData();
    body.append("photo", file);
    return fetch(`/api/gardnr/logs/${logId}/photo`, { method: "PUT", body }).then(async (res) => {
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text().catch(() => "")}`);
      return res.json() as Promise<GardenCareLog>;
    });
  },
  deleteLogPhoto: (logId: number) => request<GardenCareLog>(`/gardnr/logs/${logId}/photo`, { method: "DELETE" }),
  logPhotoUrl: (logId: number) => `/api/gardnr/logs/${logId}/photo`,

  createSchedule: (plantId: number, input: Omit<GardenCareSchedule, "id" | "plant_id" | "next_due" | "is_overdue">) =>
    request<GardenCareSchedule>(`/gardnr/plants/${plantId}/schedules`, { method: "POST", body: JSON.stringify(input) }),
  updateSchedule: (id: number, input: Partial<Omit<GardenCareSchedule, "id" | "plant_id" | "next_due" | "is_overdue">>) =>
    request<GardenCareSchedule>(`/gardnr/schedules/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteSchedule: (id: number) => request<void>(`/gardnr/schedules/${id}`, { method: "DELETE" }),
};
