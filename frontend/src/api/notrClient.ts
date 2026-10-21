import type {
  NotrImage,
  NotrLabel,
  NotrNote,
  NotrNoteFilters,
  NotrNoteInput,
  NotrNoteUpdate,
} from "./notrTypes";

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

function noteQuery(filters: NotrNoteFilters): string {
  const q = new URLSearchParams();
  if (filters.q?.trim()) q.set("q", filters.q.trim());
  if (filters.labelId !== undefined) q.set("label_id", String(filters.labelId));
  if (filters.assetId !== undefined) q.set("asset_id", String(filters.assetId));
  if (filters.plantId !== undefined) q.set("plant_id", String(filters.plantId));
  if (filters.recipeId !== undefined) q.set("recipe_id", String(filters.recipeId));
  if (filters.positionsOnly) q.set("positions_only", "true");
  if (filters.archived) q.set("archived", "true");
  const text = q.toString();
  return text ? `?${text}` : "";
}

/** Query keys, so every list and detail of notes invalidates together after a change. */
export const NOTR_KEYS = {
  all: ["notr"] as const,
  notes: ["notr", "notes"] as const,
  labels: ["notr", "labels"] as const,
};

export const notrApi = {
  listNotes: (filters: NotrNoteFilters = {}) => request<NotrNote[]>(`/notr/notes${noteQuery(filters)}`),
  getNote: (id: number) => request<NotrNote>(`/notr/notes/${id}`),
  createNote: (input: NotrNoteInput) =>
    request<NotrNote>("/notr/notes", { method: "POST", body: JSON.stringify(input) }),
  updateNote: (id: number, input: NotrNoteUpdate) =>
    request<NotrNote>(`/notr/notes/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteNote: (id: number) => request<void>(`/notr/notes/${id}`, { method: "DELETE" }),
  /** Ticks or unticks the `index`-th checkbox of the note's body (counting `- [ ]` lines in order). */
  toggleTask: (id: number, index: number, checked: boolean) =>
    request<NotrNote>(`/notr/notes/${id}/tasks`, { method: "PUT", body: JSON.stringify({ index, checked }) }),

  /** A picture for a note's Markdown. Its own multipart action, uploaded before the note is saved
   * (a new note has no id yet); the note claims it when its body shows it. `request` above sets a
   * JSON content type, which would break the multipart boundary, so this one builds its own call. */
  uploadImage: async (file: File): Promise<NotrImage> => {
    const body = new FormData();
    body.append("image", file);
    const res = await fetch("/api/notr/images", { method: "POST", body });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      let detail = text;
      try {
        detail = (JSON.parse(text) as { detail?: string }).detail ?? text;
      } catch {
        // not JSON: show the text as it is
      }
      throw new Error(detail || `${res.status} ${res.statusText}`);
    }
    return res.json() as Promise<NotrImage>;
  },

  listLabels: (includeArchived = false) => request<NotrLabel[]>(`/notr/labels?include_archived=${includeArchived}`),
  createLabel: (name: string) =>
    request<NotrLabel>("/notr/labels", { method: "POST", body: JSON.stringify({ name }) }),
  updateLabel: (id: number, input: { name?: string; color?: string | null; is_archived?: boolean }) =>
    request<NotrLabel>(`/notr/labels/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  reorderLabels: (labelIds: number[]) =>
    request<void>("/notr/labels/reorder", { method: "PUT", body: JSON.stringify({ label_ids: labelIds }) }),
};
