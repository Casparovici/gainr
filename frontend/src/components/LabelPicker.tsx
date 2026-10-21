import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { NOTR_KEYS, notrApi } from "../api/notrClient";
import { QueryError } from "./ui/QueryError";
import { t } from "../i18n";

const LABEL_DOT_FALLBACK = "bg-ui-muted";

/** What a chip needs of a label -- a notr label, or the same three fields from anywhere else. */
interface LabelLike {
  id: number;
  name: string;
  color: string | null;
}

/** Read-only chips for displaying a note's labels (a card, the Journal, the Notes sections) --
 * distinct from the interactive picker below, which is only for the note form. */
export function LabelChips({ labels }: { labels: LabelLike[] }) {
  if (labels.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {labels.map((label) => (
        <span
          key={label.id}
          className="flex items-center gap-1 rounded-full bg-ui-tile px-2 py-0.5 text-xs text-ui-ink-soft"
        >
          <span className={`h-1.5 w-1.5 rounded-full ${label.color ? "" : LABEL_DOT_FALLBACK}`} style={{ backgroundColor: label.color ?? undefined }} />
          {label.name}
        </span>
      ))}
    </div>
  );
}

/** Toggleable chips over notr's global label set (docs/adr/0050) plus an inline "+ new label"
 * quick-add. Labels belong to no position, plant or recipe, so every place a note is written
 * uses this one picker over the one set. */
export default function LabelPicker({ selectedIds, onChange }: { selectedIds: number[]; onChange: (ids: number[]) => void }) {
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("");

  const { data: labels, isError, refetch } = useQuery({
    queryKey: NOTR_KEYS.labels,
    queryFn: () => notrApi.listLabels(),
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => notrApi.createLabel(name),
    onSuccess: (label) => {
      queryClient.invalidateQueries({ queryKey: NOTR_KEYS.labels });
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
      {isError && <QueryError className="text-sm" message={t("Couldn't load labels.")} onRetry={() => refetch()} />}
      {(labels ?? []).map((label) => {
        const selected = selectedIds.includes(label.id);
        return (
          <button
            key={label.id}
            type="button"
            onClick={() => toggle(label.id)}
            className={`flex items-center gap-1.5 min-h-8 rounded-full border px-3 py-1 text-sm font-medium ${
              selected ? "border-ui-brand bg-ui-brand text-white" : "border-ui-line text-ui-ink-soft hover:bg-ui-tile"
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
        placeholder={t("new label…")}
        className="h-8 w-28 rounded-l-full border border-r-0 border-dashed border-ui-line bg-transparent py-1 pl-3 text-sm text-ui-ink focus:border-ui-brand focus:outline-none"
      />
      <button
        type="button"
        onClick={submitNewLabel}
        disabled={!newName.trim() || createMutation.isPending}
        className="-ml-1.5 h-8 rounded-r-full border border-dashed border-ui-line pl-1 pr-3 text-sm text-ui-muted hover:bg-ui-tile disabled:opacity-40"
      >{t("+ Add")}</button>
    </div>
  );
}
