import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";
import type { PositionNoteLabel } from "../api/types";

const LABEL_DOT_FALLBACK = "bg-slate-400";

/** Read-only chips for displaying a note's labels (the Journal grid, the Notes tab's list) --
 * distinct from the interactive picker below, which is only for the add/edit form. */
export function LabelChips({ labels }: { labels: PositionNoteLabel[] }) {
  if (labels.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {labels.map((label) => (
        <span
          key={label.id}
          className="flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
        >
          <span className={`h-1.5 w-1.5 rounded-full ${label.color ? "" : LABEL_DOT_FALLBACK}`} style={{ backgroundColor: label.color ?? undefined }} />
          {label.name}
        </span>
      ))}
    </div>
  );
}

/** Toggleable chips over the global label set (see docs/adr/0016-position-journal.md) plus an
 * inline "+ new label" quick-add, the same get-or-create-by-name shape listr's catalog items
 * and Picnic recipe import already use. Shared between the position detail panel's own note
 * form and the Journal's -- labels are global, not per-position, so both need the identical
 * picker over the identical set. */
export default function LabelPicker({ selectedIds, onChange }: { selectedIds: number[]; onChange: (ids: number[]) => void }) {
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("");

  const { data: labels } = useQuery({
    queryKey: ["position-note-labels"],
    queryFn: () => api.listPositionNoteLabels(),
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => api.createPositionNoteLabel(name),
    onSuccess: (label) => {
      queryClient.invalidateQueries({ queryKey: ["position-note-labels"] });
      onChange([...selectedIds, label.id]);
      setNewName("");
    },
  });

  function toggle(id: number) {
    onChange(selectedIds.includes(id) ? selectedIds.filter((i) => i !== id) : [...selectedIds, id]);
  }

  function submitNewLabel() {
    if (newName.trim()) createMutation.mutate(newName.trim());
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {(labels ?? []).map((label) => {
        const selected = selectedIds.includes(label.id);
        return (
          <button
            key={label.id}
            type="button"
            onClick={() => toggle(label.id)}
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
              selected ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 text-slate-600 hover:bg-slate-50"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${label.color ? "" : LABEL_DOT_FALLBACK}`} style={{ backgroundColor: label.color ?? undefined }} />
            {label.name}
          </button>
        );
      })}
      {/* A plain input, not a nested <form> -- this picker is always used inside a bigger note
          form, and a <form> inside a <form> isn't valid HTML. An explicit Add button is the
          primary way to commit (Enter is a convenience on top, not relied on alone). */}
      <input
        value={newName}
        onChange={(e) => setNewName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            submitNewLabel();
          }
        }}
        placeholder="new label…"
        className="w-24 rounded-l-full border border-r-0 border-dashed border-slate-300 py-1 pl-2.5 text-xs text-slate-500 focus:border-slate-500 focus:outline-none"
      />
      <button
        type="button"
        onClick={submitNewLabel}
        disabled={!newName.trim() || createMutation.isPending}
        className="-ml-1.5 rounded-r-full border border-dashed border-slate-300 py-1 pl-1 pr-2.5 text-xs text-slate-500 hover:bg-slate-50 disabled:opacity-40"
      >
        + Add
      </button>
    </div>
  );
}
