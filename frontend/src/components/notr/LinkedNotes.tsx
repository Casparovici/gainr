import { useQuery } from "@tanstack/react-query";
import { Pin, PinOff, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { NOTR_KEYS, notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import { firstLine } from "../../utils/markdownEditing";
import { t } from "../../i18n";
import Sheet from "../ui/Sheet";
import { QueryError } from "../ui/QueryError";
import { dangerButtonClass, secondaryButtonClass } from "../ui/kit";
import NoteCard from "./NoteCard";
import NoteForm from "./NoteForm";
import { NoteReader, confirmDeleteNote, useNoteActions } from "./NoteView";

type Open = { kind: "read"; id: number } | { kind: "edit"; id: number } | { kind: "new" };

function NoteSheet({ note, onClose, onEdit }: { note: NotrNote; onClose: () => void; onEdit: () => void }) {
  const { pin, remove } = useNoteActions(note, onClose);
  return (
    <Sheet
      title={note.title.trim() || firstLine(note.body) || t("Note")}
      onClose={onClose}
      footer={
        <>
          {(pin.isError || remove.isError) && (
            <p className="m-0 text-sm text-ui-late" role="alert">
              {t("That didn't work. Try again.")}
            </p>
          )}
          <div className="grid grid-cols-2 gap-2">
            <button type="button" onClick={onEdit} className={secondaryButtonClass}>
              {t("Edit")}
            </button>
            <button type="button" onClick={() => pin.mutate()} disabled={pin.isPending} className={secondaryButtonClass}>
              {note.pinned ? <PinOff size={16} aria-hidden /> : <Pin size={16} aria-hidden />}
              {note.pinned ? t("Unpin") : t("Pin")}
            </button>
            <Link to={`/notr/${note.id}`} className={secondaryButtonClass}>
              {t("Open in notr")}
            </Link>
            <button
              type="button"
              onClick={() => {
                if (confirmDeleteNote()) remove.mutate();
              }}
              disabled={remove.isPending}
              className={`${dangerButtonClass} justify-center`}
            >
              {t("Delete")}
            </button>
          </div>
        </>
      }
    >
      <NoteReader note={note} />
    </Sheet>
  );
}

/** The "Notes" section of a position, a plant or a recipe: the notes linked to it, a tap on one
 * opens it to read (with Edit, Pin, Delete and "Open in notr"), and "Add note" writes a new one
 * already linked here. The notes live in notr, so what's written here shows up there too. */
export default function LinkedNotes({ assetId, plantId, recipeId }: { assetId?: number; plantId?: number; recipeId?: number }) {
  const [open, setOpen] = useState<Open | null>(null);
  const notesQuery = useQuery({
    queryKey: [...NOTR_KEYS.notes, { assetId, plantId, recipeId }],
    queryFn: () => notrApi.listNotes({ assetId, plantId, recipeId }),
  });

  const notes = notesQuery.data;
  const defaults = {
    asset_ids: assetId !== undefined ? [assetId] : [],
    plant_ids: plantId !== undefined ? [plantId] : [],
    recipe_ids: recipeId !== undefined ? [recipeId] : [],
  };
  const openNote = open && open.kind !== "new" ? notes?.find((n) => n.id === open.id) : undefined;

  return (
    <section className="flex flex-col gap-3" aria-label={t("Notes")}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="m-0 font-display text-lg font-bold text-ui-ink">{t("Notes")}</h3>
        <button type="button" onClick={() => setOpen({ kind: "new" })} className={`${secondaryButtonClass} h-10`}>
          <Plus size={16} aria-hidden />
          {t("Add note")}
        </button>
      </div>

      {notesQuery.isPending ? (
        <div role="status" aria-label={t("Loading notes…")} className="flex flex-col gap-2">
          <div className="h-20 animate-pulse rounded-2xl bg-ui-tile" />
          <div className="h-20 animate-pulse rounded-2xl bg-ui-tile" />
        </div>
      ) : notesQuery.isError || !notes ? (
        <QueryError message={t("Couldn't load the notes.")} onRetry={() => notesQuery.refetch()} className="text-sm" />
      ) : notes.length === 0 ? (
        <p className="m-0 rounded-2xl border border-dashed border-ui-line px-4 py-5 text-center text-sm text-ui-muted">
          {t("No notes yet. Tap Add note to write the first.")}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {notes.map((note) => (
            <NoteCard key={note.id} note={note} onOpen={() => setOpen({ kind: "read", id: note.id })} />
          ))}
        </div>
      )}

      {open?.kind === "new" && (
        <Sheet title={t("New note")} onClose={() => setOpen(null)}>
          <NoteForm
            defaults={defaults}
            fixedLinks
            requireAsset={assetId !== undefined}
            autoFocus
            onSaved={() => setOpen(null)}
            onCancel={() => setOpen(null)}
          />
        </Sheet>
      )}
      {open?.kind === "read" && openNote && (
        <NoteSheet note={openNote} onClose={() => setOpen(null)} onEdit={() => setOpen({ kind: "edit", id: openNote.id })} />
      )}
      {open?.kind === "edit" && openNote && (
        <Sheet title={t("Edit note")} onClose={() => setOpen(null)}>
          <NoteForm
            note={openNote}
            fixedLinks
            requireAsset={assetId !== undefined}
            onSaved={() => setOpen({ kind: "read", id: openNote.id })}
            onCancel={() => setOpen({ kind: "read", id: openNote.id })}
          />
        </Sheet>
      )}
    </section>
  );
}
