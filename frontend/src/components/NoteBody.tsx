import { useEffect, useRef, useState } from "react";

import Markdown from "./Markdown";
import ModalOverlay from "./ModalOverlay";
import { firstLine } from "../utils/markdownEditing";
import { formatRelativeTime } from "../utils/format";
import { t } from "../i18n";

/** Just the fields NoteBody/NoteExpandDialog actually render -- a notr note, or anything shaped
 * like one. */
interface NoteLike {
  title: string;
  body: string;
  created_at: string;
}

function NoteExpandDialog({ note, onClose }: { note: NoteLike; onClose: () => void }) {
  return (
    <ModalOverlay onClose={onClose} cardClassName="w-full max-w-lg max-h-[80vh] overflow-y-auto rounded-lg bg-white p-5 shadow-lg">
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="text-base font-semibold text-slate-900">{note.title || firstLine(note.body)}</h4>
        <span className="shrink-0 text-xs text-slate-400" title={note.created_at}>
          {formatRelativeTime(note.created_at)}
        </span>
      </div>
      <Markdown text={note.body} className="mt-3" />
      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >{t("Close")}</button>
      </div>
    </ModalOverlay>
  );
}

/** A note's body (Markdown, pictures included), clamped to 3 lines with a "Show more" affordance
 * that opens the full text in a dialog -- only shown when the body actually overflows 3 lines, measured after render rather
 * than guessed from character count, since block formatting (headings, lists) changes how much
 * text fits in three lines. Shared by the Journal and the other places a note is listed
 * in short. */
export default function NoteBody({ note }: { note: NoteLike }) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const el = bodyRef.current;
    if (el) setIsOverflowing(el.scrollHeight > el.clientHeight + 1);
  }, [note.body]);

  return (
    <>
      <div ref={bodyRef} className="line-clamp-3 max-h-[4.8rem] overflow-hidden">
        <Markdown text={note.body} className="!text-sm" />
      </div>
      {isOverflowing && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-0.5 text-xs font-medium text-blue-700 hover:underline"
        >{t("Show more")}</button>
      )}
      {expanded && <NoteExpandDialog note={note} onClose={() => setExpanded(false)} />}
    </>
  );
}
