import { useQuery } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { NOTR_KEYS, notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import MobileFab from "../../components/MobileFab";
import NoteCard from "../../components/notr/NoteCard";
import { QueryError } from "../../components/ui/QueryError";
import { ModuleTopRow, PageTitle, primaryButtonClass } from "../../components/ui/kit";
import { t, tp } from "../../i18n";

const SEARCH_DELAY_MS = 300;

const cardClass = "rounded-[20px] border border-ui-border bg-ui-surface px-4 py-8 text-center text-ui-muted";
const gridClass = "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3";

function NoteGrid({ notes, label }: { notes: NotrNote[]; label?: string }) {
  return (
    <section aria-label={label} className="flex flex-col gap-2">
      {label && <h2 className="m-0 text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">{label}</h2>}
      <div className={gridClass}>
        {notes.map((note) => (
          <NoteCard key={note.id} note={note} to={`/notr/${note.id}`} />
        ))}
      </div>
    </section>
  );
}

/** notr's list of notes (or, with `archived`, its archive): newest first with pinned notes on top,
 * searchable by text and filterable by label. Tapping a card opens the note. */
export default function Notes({ archived = false }: { archived?: boolean } = {}) {
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [labelId, setLabelId] = useState<number | null>(null);

  // The search waits for a pause in typing instead of asking the server for every keystroke.
  useEffect(() => {
    const timer = window.setTimeout(() => setQ(input.trim()), SEARCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [input]);

  const notesQuery = useQuery({
    queryKey: [...NOTR_KEYS.notes, { archived, q, labelId }],
    queryFn: () => notrApi.listNotes({ archived, q, labelId: labelId ?? undefined }),
  });
  const labelsQuery = useQuery({ queryKey: NOTR_KEYS.labels, queryFn: () => notrApi.listLabels() });

  const notes = notesQuery.data;
  const filtered = q !== "" || labelId !== null;
  const pinned = notes?.filter((n) => n.pinned) ?? [];
  const others = notes?.filter((n) => !n.pinned) ?? [];
  const labels = labelsQuery.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow>
        {!archived && (
          <button type="button" onClick={() => navigate("/notr/new")} className={`${primaryButtonClass} hidden sm:inline-flex`}>
            <Plus size={18} aria-hidden />
            {t("New note")}
          </button>
        )}
      </ModuleTopRow>
      <PageTitle subtitle={notes && notes.length > 0 ? tp(notes.length, "{n} note", "{n} notes") : undefined}>
        {archived ? t("Archive") : t("Notes")}
      </PageTitle>

      <div className="relative">
        <Search size={18} aria-hidden className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ui-muted" />
        <input
          type="search"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("Search notes")}
          aria-label={t("Search notes")}
          className="h-11 w-full rounded-xl border border-ui-line bg-ui-surface pl-10 pr-3 text-base text-ui-ink focus:border-ui-brand focus:outline-none focus:ring-1 focus:ring-ui-brand"
        />
      </div>

      {labels.length > 0 && (
        // One scrolling row on a phone instead of several wrapped ones.
        <div
          role="group"
          aria-label={t("Filter by label")}
          className="-mx-4 flex items-center gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0"
        >
          {labels.map((label) => {
            const selected = labelId === label.id;
            return (
              <button
                key={label.id}
                type="button"
                onClick={() => setLabelId(selected ? null : label.id)}
                aria-pressed={selected}
                className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-sm font-semibold transition-colors ${
                  selected
                    ? "border-ui-brand bg-ui-brand-soft text-ui-brand-strong"
                    : "border-ui-border bg-ui-surface text-ui-ink-soft hover:border-ui-line"
                }`}
              >
                {label.color && <span aria-hidden className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: label.color }} />}
                {label.name}
              </button>
            );
          })}
        </div>
      )}

      {notesQuery.isPending ? (
        <div role="status" aria-label={t("Loading notes…")} className={gridClass}>
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-2xl bg-ui-tile" />
          ))}
        </div>
      ) : notesQuery.isError || !notes ? (
        <QueryError
          className={cardClass}
          message={t("Couldn't load your notes.")}
          onRetry={() => notesQuery.refetch()}
        />
      ) : notes.length === 0 ? (
        <div className={cardClass}>
          <p className="m-0 font-display text-lg font-bold text-ui-ink">
            {filtered ? t("Nothing matches") : archived ? t("Nothing archived") : t("No notes yet")}
          </p>
          <p className="m-0 mt-1">
            {filtered
              ? t("No notes match your search or label.")
              : archived
                ? t("Notes you archive are kept here.")
                : t("Tap + New note to write the first one.")}
          </p>
        </div>
      ) : pinned.length > 0 && others.length > 0 ? (
        <>
          <NoteGrid notes={pinned} label={t("Pinned")} />
          <NoteGrid notes={others} label={t("Others")} />
        </>
      ) : (
        <NoteGrid notes={notes} />
      )}

      {!archived && <MobileFab label={t("New note")} onClick={() => navigate("/notr/new")} />}
    </div>
  );
}
