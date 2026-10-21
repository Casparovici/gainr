import { useQuery } from "@tanstack/react-query";
import { Archive, ArchiveRestore, ArrowLeft, MoreHorizontal, Pin, PinOff, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { NOTR_KEYS, notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import NoteForm, { type NoteFormDefaults } from "../../components/notr/NoteForm";
import { NoteReader, confirmDeleteNote, useNoteActions } from "../../components/notr/NoteView";
import Sheet from "../../components/ui/Sheet";
import { QueryError } from "../../components/ui/QueryError";
import { ModuleTopRow, PageTitle, dangerButtonClass, iconButtonClass, secondaryButtonClass } from "../../components/ui/kit";
import { t } from "../../i18n";
import { firstLine } from "../../utils/markdownEditing";

const cardClass = "rounded-[20px] border border-ui-border bg-ui-surface px-4 py-8 text-center text-ui-muted";

function idsFrom(value: string | null): number[] {
  const n = Number(value);
  return value !== null && Number.isInteger(n) && n > 0 ? [n] : [];
}

function BackLink({ to }: { to: string }) {
  return (
    <Link to={to} className="inline-flex h-11 items-center gap-1.5 text-[15px] font-semibold text-ui-brand-strong">
      <ArrowLeft size={18} aria-hidden />
      {t("Notes")}
    </Link>
  );
}

/** A new note, optionally about something: `?asset=ID&plant=ID&recipe=ID` presets what it's linked
 * to (the way a position, plant or recipe opens the editor). Saving opens the note. */
function NewNote() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [defaults] = useState<NoteFormDefaults>(() => ({
    asset_ids: idsFrom(params.get("asset")),
    plant_ids: idsFrom(params.get("plant")),
    recipe_ids: idsFrom(params.get("recipe")),
  }));
  // Back to wherever the note was started from, or to the list when this page was opened directly.
  const leave = () => (location.key !== "default" ? navigate(-1) : navigate("/notr", { replace: true }));

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow left={<BackLink to="/notr" />} />
      <PageTitle>{t("New note")}</PageTitle>
      <NoteForm
        defaults={defaults}
        autoFocus
        onSaved={(note) => navigate(`/notr/${note.id}`, { replace: true })}
        onCancel={leave}
      />
    </div>
  );
}

function ActionsSheet({ note, onClose, onDeleted }: { note: NotrNote; onClose: () => void; onDeleted: () => void }) {
  const navigate = useNavigate();
  const { pin, archive, remove } = useNoteActions(note, onDeleted);
  const failed = pin.isError || archive.isError || remove.isError;
  return (
    <Sheet title={t("Note actions")} onClose={onClose}>
      <div className="flex flex-col gap-2 pt-1">
        <button
          type="button"
          disabled={pin.isPending}
          onClick={() => pin.mutate(undefined, { onSuccess: onClose })}
          className={`${secondaryButtonClass} justify-start`}
        >
          {note.pinned ? <PinOff size={18} aria-hidden /> : <Pin size={18} aria-hidden />}
          {note.pinned ? t("Unpin") : t("Pin")}
        </button>
        <button
          type="button"
          disabled={archive.isPending}
          onClick={() =>
            archive.mutate(undefined, {
              onSuccess: () => {
                onClose();
                // An archived note leaves the list the reader came from.
                if (!note.is_archived) navigate("/notr", { replace: true });
              },
            })
          }
          className={`${secondaryButtonClass} justify-start`}
        >
          {note.is_archived ? <ArchiveRestore size={18} aria-hidden /> : <Archive size={18} aria-hidden />}
          {note.is_archived ? t("Unarchive note") : t("Archive note")}
        </button>
        <button
          type="button"
          disabled={remove.isPending}
          onClick={() => {
            if (confirmDeleteNote()) remove.mutate();
          }}
          className={dangerButtonClass}
        >
          <Trash2 size={18} aria-hidden />
          {t("Delete")}
        </button>
        {failed && (
          <p className="m-0 text-sm text-ui-late" role="alert">
            {t("That didn't work. Try again.")}
          </p>
        )}
      </div>
    </Sheet>
  );
}

function ExistingNote({ id }: { id: number }) {
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [menu, setMenu] = useState(false);
  const noteQuery = useQuery({
    queryKey: [...NOTR_KEYS.notes, id],
    // An unknown id is an answer, not a failure: null says "no such note" without being retried.
    queryFn: () =>
      notrApi.getNote(id).catch((error: Error) => {
        if (error.message.startsWith("404")) return null;
        throw error;
      }),
  });

  if (noteQuery.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <ModuleTopRow left={<BackLink to="/notr" />} />
        <div role="status" aria-label={t("Loading note…")} className="flex flex-col gap-3 pt-2">
          <div className="h-9 w-2/3 animate-pulse rounded-xl bg-ui-tile" />
          <div className="h-40 animate-pulse rounded-2xl bg-ui-tile" />
        </div>
      </div>
    );
  }
  if (noteQuery.isError) {
    return (
      <div className="flex flex-col gap-4">
        <ModuleTopRow left={<BackLink to="/notr" />} />
        <QueryError className={cardClass} message={t("Couldn't load this note.")} onRetry={() => noteQuery.refetch()} />
      </div>
    );
  }

  const note = noteQuery.data;
  if (note === null) {
    return (
      <div className="flex flex-col gap-4">
        <ModuleTopRow left={<BackLink to="/notr" />} />
        <div className={cardClass}>
          <p className="m-0 font-display text-lg font-bold text-ui-ink">{t("Note not found")}</p>
          <p className="m-0 mt-1">{t("It may have been deleted.")}</p>
          <Link to="/notr" className={`${secondaryButtonClass} mt-4`}>
            {t("Back to notes")}
          </Link>
        </div>
      </div>
    );
  }
  const back = note.is_archived ? "/notr/archive" : "/notr";
  const heading = note.title.trim();

  if (editing) {
    return (
      <div className="flex flex-col gap-4">
        <ModuleTopRow left={<BackLink to={back} />} />
        <PageTitle>{t("Edit note")}</PageTitle>
        <NoteForm note={note} autoFocus onSaved={() => setEditing(false)} onCancel={() => setEditing(false)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow left={<BackLink to={back} />}>
        <button type="button" onClick={() => setEditing(true)} className={secondaryButtonClass}>
          {t("Edit")}
        </button>
        <button type="button" onClick={() => setMenu(true)} aria-label={t("More actions")} className={iconButtonClass}>
          <MoreHorizontal size={20} aria-hidden />
        </button>
      </ModuleTopRow>

      {heading ? (
        <PageTitle size="md">{heading}</PageTitle>
      ) : (
        <h1 className="sr-only">{firstLine(note.body) || t("Note")}</h1>
      )}
      {(note.pinned || note.is_archived) && (
        <p className="m-0 flex items-center gap-3 text-sm font-semibold text-ui-brand-strong">
          {note.pinned && (
            <span className="inline-flex items-center gap-1">
              <Pin size={14} aria-hidden className="fill-current" />
              {t("Pinned")}
            </span>
          )}
          {note.is_archived && <span className="text-ui-muted">{t("Archived")}</span>}
        </p>
      )}

      <article className="rounded-[20px] border border-ui-border bg-ui-surface p-4">
        <NoteReader note={note} />
      </article>

      {menu && <ActionsSheet note={note} onClose={() => setMenu(false)} onDeleted={() => navigate("/notr", { replace: true })} />}
    </div>
  );
}

/** One note: `/notr/new` writes one (with `?asset=&plant=&recipe=` to say what it's about), and
 * `/notr/:id` reads one, with Edit in place and a sheet for pinning, archiving and deleting. */
export default function NotePage() {
  const { id } = useParams<{ id: string }>();
  if (id === undefined || id === "new") return <NewNote />;
  const noteId = Number(id);
  if (!Number.isInteger(noteId) || noteId <= 0) {
    return (
      <div className="flex flex-col gap-4">
        <ModuleTopRow left={<BackLink to="/notr" />} />
        <div className={cardClass}>
          <p className="m-0 font-display text-lg font-bold text-ui-ink">{t("Note not found")}</p>
          <Link to="/notr" className={`${secondaryButtonClass} mt-4`}>
            {t("Back to notes")}
          </Link>
        </div>
      </div>
    );
  }
  return <ExistingNote key={noteId} id={noteId} />;
}
