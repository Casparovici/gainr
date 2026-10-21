import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { NOTR_KEYS, notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import { t } from "../../i18n";
import { taskLineNumbers } from "../../utils/markdownEditing";
import { LabelChips } from "../LabelPicker";
import Markdown from "../Markdown";
import { LinkChips, noteLinks } from "./LinkChips";
import { noteDate } from "./noteDate";

/** `body` with its `index`-th checkbox ticked or unticked -- the same change the server makes, shown
 * at once while the request is on its way. */
function withTask(body: string, index: number, checked: boolean): string {
  const line = taskLineNumbers(body)[index];
  if (line === undefined) return body;
  const lines = body.split("\n");
  lines[line - 1] = lines[line - 1].replace(/\[[ xX]\]/, checked ? "[x]" : "[ ]");
  return lines.join("\n");
}

/** A note to read: when it was written, its labels and links, and the Markdown body, whose
 * checkboxes tick through the server. The tick shows straight away and is undone when the server
 * says no. */
export function NoteReader({ note, linksAsLinks = true }: { note: NotrNote; linksAsLinks?: boolean }) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState(note.body);
  useEffect(() => setBody(note.body), [note.body]);

  const toggle = useMutation({
    mutationFn: ({ index, checked }: { index: number; checked: boolean }) => notrApi.toggleTask(note.id, index, checked),
    onMutate: ({ index, checked }) => setBody((current) => withTask(current, index, checked)),
    onError: () => setBody(note.body),
    onSettled: () => queryClient.invalidateQueries({ queryKey: NOTR_KEYS.all }),
  });

  const links = noteLinks(note);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="text-sm text-ui-muted">{noteDate(note.created_at)}</span>
        <LabelChips labels={note.labels} />
      </div>
      <LinkChips links={links} asLinks={linksAsLinks} />
      {body.trim() ? (
        <Markdown text={body} onToggleTask={(index, checked) => toggle.mutate({ index, checked })} />
      ) : (
        <p className="m-0 text-sm text-ui-muted">{t("This note has no text.")}</p>
      )}
      {toggle.isError && (
        <p className="m-0 text-sm text-ui-late" role="alert">
          {t("Couldn't tick that box. Try again.")}
        </p>
      )}
    </div>
  );
}

/** Whether to delete a note: says what actually happens to it. */
export function confirmDeleteNote(): boolean {
  return window.confirm(
    t("Delete this note? It's removed from everything it's linked to and its pictures are deleted too. This can't be undone."),
  );
}

/** Pin, archive and delete for one note; each refreshes every notes list. */
export function useNoteActions(note: NotrNote | undefined, onDeleted?: () => void) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: NOTR_KEYS.all });
  const pin = useMutation({
    mutationFn: () => notrApi.updateNote(note!.id, { pinned: !note!.pinned }),
    onSuccess: refresh,
  });
  const archive = useMutation({
    mutationFn: () => notrApi.updateNote(note!.id, { is_archived: !note!.is_archived }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => notrApi.deleteNote(note!.id),
    onSuccess: async () => {
      await refresh();
      onDeleted?.();
    },
  });
  return { pin, archive, remove };
}
