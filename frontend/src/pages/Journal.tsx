import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { JournalNoteInput, NoteAsset, Position, PositionNote } from "../api/types";
import LabelPicker, { LabelChips } from "../components/LabelPicker";
import GainrTopRow from "../components/GainrTopRow";
import MobileFab from "../components/MobileFab";
import { PageTitle, primaryButtonClass } from "../components/ui/kit";
import NoteBody from "../components/NoteBody";
import { usePortfolio } from "../hooks/usePortfolio";
import { formatRelativeTime } from "../utils/format";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

function Placeholder({ children }: { children: React.ReactNode }) {
  return <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-[15px] text-ui-muted">{children}</div>;
}

/** The positions a note can be linked to: this portfolio's holdings (not the cash row), plus any
 * position the note is already linked to that isn't among them -- held in another portfolio, or
 * since sold -- so editing a note never quietly drops a link just because it isn't listed. */
function positionOptions(positions: Position[], linked: NoteAsset[]): (NoteAsset & { elsewhere: boolean })[] {
  const options = positions
    .filter((p) => p.ticker !== "CASH")
    .map((p) => ({ id: p.asset_id, ticker: p.ticker, name: p.name, elsewhere: false }));
  const listed = new Set(options.map((o) => o.id));
  for (const a of linked) {
    if (!listed.has(a.id)) options.push({ ...a, elsewhere: true });
  }
  return options.sort((a, b) => a.name.localeCompare(b.name));
}

function PositionCheckboxes({
  options,
  selectedIds,
  onChange,
}: {
  options: (NoteAsset & { elsewhere: boolean })[];
  selectedIds: number[];
  onChange: (ids: number[]) => void;
}) {
  const toggle = (id: number) =>
    onChange(selectedIds.includes(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id]);
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="mb-1 flex w-full items-baseline justify-between text-xs font-medium text-slate-500">
        <span>Positions</span>
        <span className="font-normal">{selectedIds.length === 0 ? "pick at least one" : `${selectedIds.length} selected`}</span>
      </legend>
      {options.length === 0 ? (
        <p className="text-sm text-slate-400">No positions in this portfolio yet.</p>
      ) : (
        <div className="grid max-h-52 grid-cols-1 gap-x-4 overflow-y-auto rounded-md border border-slate-200 p-2 sm:grid-cols-2">
          {options.map((o) => (
            <label key={o.id} className="flex min-w-0 cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-slate-50">
              <input type="checkbox" checked={selectedIds.includes(o.id)} onChange={() => toggle(o.id)} />
              <span className="shrink-0 font-medium text-slate-900">{o.ticker}</span>
              <span className="truncate text-slate-500">{o.name}</span>
              {o.elsewhere && <span className="shrink-0 text-xs text-slate-400">(not in this portfolio)</span>}
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

function JournalNoteForm({
  positions,
  initial,
  onCancel,
  onSubmit,
  isSubmitting,
}: {
  positions: Position[];
  initial: PositionNote | undefined;
  onCancel: () => void;
  onSubmit: (input: JournalNoteInput) => void;
  isSubmitting: boolean;
}) {
  const [assetIds, setAssetIds] = useState<number[]>(initial?.assets.map((a) => a.id) ?? []);
  const [title, setTitle] = useState(initial?.title ?? "");
  const [body, setBody] = useState(initial?.body ?? "");
  const [labelIds, setLabelIds] = useState<number[]>(initial?.labels.map((l) => l.id) ?? []);
  const options = positionOptions(positions, initial?.assets ?? []);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (assetIds.length === 0) return;
        onSubmit({ title, body, label_ids: labelIds, asset_ids: assetIds });
      }}
      className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-4"
    >
      <input
        required
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title"
        className={inputClass}
      />
      <textarea
        required
        rows={4}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="What's on your mind? **bold**, *italic*, ~~strikethrough~~, `code`, # headings, - bullets and 1. numbered lists are supported."
        className={`${inputClass} resize-y`}
      />
      <PositionCheckboxes options={options} selectedIds={assetIds} onChange={setAssetIds} />
      <LabelPicker selectedIds={labelIds} onChange={setLabelIds} />
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting || assetIds.length === 0}
          title={assetIds.length === 0 ? "Pick at least one position" : undefined}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {isSubmitting ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}

function JournalTile({ note, onEdit, onDelete }: { note: PositionNote; onEdit: () => void; onDelete: () => void }) {
  const single = note.assets.length === 1 ? note.assets[0] : null;
  return (
    <article className="flex flex-col gap-2 rounded-[20px] border border-ui-border bg-ui-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          {single ? (
            <Link to={`/?position=${single.id}`} className="text-xs font-medium text-blue-700 hover:underline">
              {single.ticker} · {single.name}
            </Link>
          ) : (
            <div className="flex flex-wrap gap-x-2 text-xs font-medium">
              {note.assets.map((a) => (
                <Link key={a.id} to={`/?position=${a.id}`} title={a.name} className="text-blue-700 hover:underline">
                  {a.ticker}
                </Link>
              ))}
            </div>
          )}
          <h3 className="m-0 truncate font-display text-lg font-bold tracking-[-0.02em] text-ui-ink">{note.title}</h3>
        </div>
        <span className="shrink-0 text-xs text-slate-400">{formatRelativeTime(note.created_at)}</span>
      </div>
      <NoteBody note={note} />
      <LabelChips labels={note.labels} />
      <div className="-mb-2 -ml-2 mt-auto flex text-xs">
        <button type="button" onClick={onEdit} className="flex h-9 w-9 items-center justify-center rounded-lg text-ui-muted hover:text-ui-ink" title="Edit" aria-label="Edit">
          <Pencil className="h-4 w-4" strokeWidth={2} />
        </button>
        <button type="button" onClick={onDelete} className="flex h-9 w-9 items-center justify-center rounded-lg text-ui-late" title="Delete" aria-label="Delete">
          <Trash2 className="h-4 w-4" strokeWidth={2} />
        </button>
      </div>
    </article>
  );
}

export default function Journal() {
  const queryClient = useQueryClient();
  const { portfolioId } = usePortfolio();
  const [activeLabelId, setActiveLabelId] = useState<number | null>(null);
  // null = closed; { note: undefined } = adding; { note } = editing that entry.
  const [editing, setEditing] = useState<{ note: PositionNote | undefined } | null>(null);

  const notesQuery = useQuery({ queryKey: ["journal-notes"], queryFn: api.listJournalNotes });
  const labelsQuery = useQuery({ queryKey: ["position-note-labels"], queryFn: () => api.listPositionNoteLabels() });
  // Journal notes themselves aren't portfolio-scoped (a note on a ticker applies wherever it's
  // held), but the "which positions is this about" picker offers the currently selected
  // portfolio's holdings (plus whatever an edited note is already linked to).
  const positionsQuery = useQuery({
    queryKey: ["positions", portfolioId],
    queryFn: () => api.getPositions(portfolioId!),
    enabled: portfolioId !== null,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["journal-notes"] });
    // Same rows every linked position's own Notes tab reads (see PositionNote's backend
    // docstring) -- invalidate that query broadly rather than track which assets changed.
    queryClient.invalidateQueries({ queryKey: ["position-notes"] });
    setEditing(null);
  };
  const createMutation = useMutation({
    mutationFn: (input: JournalNoteInput) => api.createJournalNote(input),
    onSuccess: invalidate,
  });
  const updateMutation = useMutation({
    mutationFn: ({ noteId, input }: { noteId: number; input: JournalNoteInput }) => api.updateJournalNote(noteId, input),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (noteId: number) => api.deleteJournalNote(noteId),
    onSuccess: invalidate,
  });

  const notes = (notesQuery.data ?? []).filter(
    (n) => activeLabelId === null || n.labels.some((l) => l.id === activeLabelId),
  );

  return (
    <div className="flex flex-col gap-4">
      <GainrTopRow>
        {editing === null && (
          <button type="button" onClick={() => setEditing({ note: undefined })} className={`${primaryButtonClass} hidden h-11 sm:inline-flex`}>
            + Add journal item
          </button>
        )}
      </GainrTopRow>
      <PageTitle subtitle={notesQuery.data && notesQuery.data.length > 0 ? `${notesQuery.data.length} ${notesQuery.data.length === 1 ? "entry" : "entries"}` : undefined}>
        Journal
      </PageTitle>

      {(labelsQuery.data ?? []).length > 0 && (
        <div className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
          <button
            type="button"
            onClick={() => setActiveLabelId(null)}
            aria-pressed={activeLabelId === null}
            className={`flex h-9 shrink-0 items-center rounded-full border px-3.5 text-sm font-semibold ${
              activeLabelId === null ? "border-ui-brand bg-ui-brand-soft text-ui-brand-strong" : "border-ui-border bg-ui-surface text-ui-ink-soft hover:border-ui-line"
            }`}
          >
            All
          </button>
          {labelsQuery.data!.map((label) => (
            <button
              key={label.id}
              type="button"
              onClick={() => setActiveLabelId(label.id)}
              aria-pressed={activeLabelId === label.id}
              className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-sm font-semibold ${
                activeLabelId === label.id
                  ? "border-ui-brand bg-ui-brand-soft text-ui-brand-strong"
                  : "border-ui-border bg-ui-surface text-ui-ink-soft hover:border-ui-line"
              }`}
            >
              <span className="h-2 w-2 rounded-full bg-slate-400" style={{ backgroundColor: label.color ?? undefined }} />
              {label.name}
            </button>
          ))}
        </div>
      )}

      {editing && (
        <JournalNoteForm
          positions={positionsQuery.data ?? []}
          initial={editing.note}
          isSubmitting={createMutation.isPending || updateMutation.isPending}
          onCancel={() => setEditing(null)}
          onSubmit={(input) =>
            editing.note ? updateMutation.mutate({ noteId: editing.note.id, input }) : createMutation.mutate(input)
          }
        />
      )}

      {notesQuery.isLoading ? (
        <Placeholder>Loading journal…</Placeholder>
      ) : notesQuery.isError ? (
        <Placeholder>Couldn't load the journal.</Placeholder>
      ) : notes.length === 0 ? (
        editing === null && (
          <Placeholder>
            {activeLabelId !== null ? "No journal entries with that label." : "No journal entries yet — keep notes on why you hold what you hold."}
          </Placeholder>
        )
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {notes.map((note) => (
            <JournalTile
              key={note.id}
              note={note}
              onEdit={() => setEditing({ note })}
              onDelete={() => {
                const about = note.assets.length > 1 ? ` It's linked to ${note.assets.map((a) => a.ticker).join(", ")}.` : "";
                if (confirm(`Delete "${note.title}"?${about}`)) deleteMutation.mutate(note.id);
              }}
            />
          ))}
        </div>
      )}

      {/* The form opens inline at the top of the page, so the FAB scrolls there too. */}
      {editing === null && (
        <MobileFab
          label="Add journal item"
          onClick={() => {
            setEditing({ note: undefined });
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        />
      )}
    </div>
  );
}
