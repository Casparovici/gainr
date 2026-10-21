import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Pin, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { NOTR_KEYS, notrApi } from "../api/notrClient";
import type { NotrNote } from "../api/notrTypes";
import GainrTopRow from "../components/GainrTopRow";
import { LabelChips } from "../components/LabelPicker";
import MobileFab from "../components/MobileFab";
import NoteBody from "../components/NoteBody";
import NoteForm from "../components/notr/NoteForm";
import { PageTitle, primaryButtonClass } from "../components/ui/kit";
import { QueryError } from "../components/ui/QueryError";
import Sheet from "../components/ui/Sheet";
import { positionPath } from "../config/modules";
import { formatRelativeTime } from "../utils/format";
import { firstLine } from "../utils/markdownEditing";
import { t, tp } from "../i18n";

function Placeholder({ children }: { children: React.ReactNode }) {
  return <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-[15px] text-ui-muted">{children}</div>;
}

/** What the delete confirmation calls a note: its title, else the first line. An untitled tile
 * shows no heading, since its body starts with that line anyway. */
function noteName(note: NotrNote): string {
  return note.title || firstLine(note.body);
}

function JournalTile({ note, onEdit, onDelete }: { note: NotrNote; onEdit: () => void; onDelete: () => void }) {
  const single = note.assets.length === 1 ? note.assets[0] : null;
  return (
    <article className="flex flex-col gap-2 rounded-[20px] border border-ui-border bg-ui-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          {single ? (
            <Link to={positionPath(single.id)} className="text-xs font-medium text-blue-700 hover:underline">
              {single.ticker} · {single.name}
            </Link>
          ) : (
            <div className="flex flex-wrap gap-x-2 text-xs font-medium">
              {note.assets.map((a) => (
                <Link key={a.id} to={positionPath(a.id)} title={a.name} className="text-blue-700 hover:underline">
                  {a.ticker}
                </Link>
              ))}
            </div>
          )}
          {note.title && (
            <h3 className="m-0 flex items-center gap-1.5 font-display text-lg font-bold tracking-[-0.02em] text-ui-ink">
              {note.pinned && <Pin aria-label={t("Pinned")} role="img" className="h-4 w-4 shrink-0 text-ui-muted" strokeWidth={2} />}
              <span className="truncate">{note.title}</span>
            </h3>
          )}
        </div>
        <span className="shrink-0 text-xs text-slate-400">{formatRelativeTime(note.created_at)}</span>
      </div>
      <NoteBody note={note} />
      <LabelChips labels={note.labels} />
      <div className="-mb-2 -ml-2 mt-auto flex text-xs">
        <button type="button" onClick={onEdit} className="flex h-9 w-9 items-center justify-center rounded-lg text-ui-muted hover:text-ui-ink" title={t("Edit")} aria-label={t("Edit")}>
          <Pencil className="h-4 w-4" strokeWidth={2} />
        </button>
        <button type="button" onClick={onDelete} className="flex h-9 w-9 items-center justify-center rounded-lg text-ui-late" title={t("Delete")} aria-label={t("Delete")}>
          <Trash2 className="h-4 w-4" strokeWidth={2} />
        </button>
      </div>
    </article>
  );
}

/** gainr's Journal: the notes linked to at least one position (docs/adr/0050). The same notes
 * show in notr, and on each position's Notes tab; writing one here needs a position. */
export default function Journal() {
  const [activeLabelId, setActiveLabelId] = useState<number | null>(null);
  // null = closed; { note: undefined } = adding; { note } = editing that entry.
  const [editing, setEditing] = useState<{ note: NotrNote | undefined } | null>(null);

  const notesQuery = useQuery({
    queryKey: [...NOTR_KEYS.notes, { positionsOnly: true }],
    queryFn: () => notrApi.listNotes({ positionsOnly: true }),
  });
  const labelsQuery = useQuery({ queryKey: NOTR_KEYS.labels, queryFn: () => notrApi.listLabels() });
  // Deleting a note removes it from every position, plant and recipe it is about, so the confirm
  // names the other positions. Everything that lists notes refreshes through NOTR_KEYS.all.
  const queryClient = useQueryClient();
  const deleteMutation = useMutation({
    mutationFn: (id: number) => notrApi.deleteNote(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOTR_KEYS.all }),
  });
  const remove = (note: NotrNote) => {
    const about = note.assets.length > 1 ? ` ${t("It's linked to {tickers}.", { tickers: note.assets.map((a) => a.ticker).join(", ") })}` : "";
    if (!confirm(`${t("Delete “{title}”?", { title: noteName(note) })}${about}`)) return;
    deleteMutation.mutate(note.id);
  };

  const notes = (notesQuery.data ?? []).filter(
    (n) => activeLabelId === null || n.labels.some((l) => l.id === activeLabelId),
  );

  return (
    <div className="flex flex-col gap-4">
      <GainrTopRow>
        <button type="button" onClick={() => setEditing({ note: undefined })} className={`${primaryButtonClass} hidden h-11 sm:inline-flex`}>{t("+ Add journal item")}</button>
      </GainrTopRow>
      <PageTitle subtitle={notesQuery.data && notesQuery.data.length > 0 ? tp(notesQuery.data.length, "{n} entry", "{n} entries") : undefined}>{t("Journal")}</PageTitle>

      {(labelsQuery.data ?? []).length > 0 && (
        <div className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
          <button
            type="button"
            onClick={() => setActiveLabelId(null)}
            aria-pressed={activeLabelId === null}
            className={`flex h-9 shrink-0 items-center rounded-full border px-3.5 text-sm font-semibold ${
              activeLabelId === null ? "border-ui-brand bg-ui-brand-soft text-ui-brand-strong" : "border-ui-border bg-ui-surface text-ui-ink-soft hover:border-ui-line"
            }`}
          >{t("All")}</button>
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

      {deleteMutation.isError && (
        <p className="m-0 text-sm text-ui-late" role="alert">{t("Couldn't delete the entry. Try again.")}</p>
      )}

      {notesQuery.isLoading ? (
        <Placeholder>{t("Loading journal…")}</Placeholder>
      ) : notesQuery.isError ? (
        <Placeholder>
          <QueryError message={t("Couldn't load the journal.")} onRetry={() => notesQuery.refetch()} />
        </Placeholder>
      ) : notes.length === 0 ? (
        <Placeholder>
          {activeLabelId !== null ? t("No journal entries with that label.") : t("No journal entries yet — keep notes on why you hold what you hold.")}
        </Placeholder>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {notes.map((note) => (
            <JournalTile key={note.id} note={note} onEdit={() => setEditing({ note })} onDelete={() => remove(note)} />
          ))}
        </div>
      )}

      {editing && (
        <Sheet title={editing.note ? t("Edit journal item") : t("Add journal item")} onClose={() => setEditing(null)}>
          <div className="pt-2">
            <NoteForm note={editing.note} requireAsset autoFocus onSaved={() => setEditing(null)} onCancel={() => setEditing(null)} />
          </div>
        </Sheet>
      )}

      {editing === null && <MobileFab label={t("Add journal item")} onClick={() => setEditing({ note: undefined })} />}
    </div>
  );
}
