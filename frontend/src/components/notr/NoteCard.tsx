import { Pin } from "lucide-react";
import { Link } from "react-router-dom";

import type { NotrNote } from "../../api/notrTypes";
import { t } from "../../i18n";
import { excerpt, firstImage, firstLine } from "../../utils/markdownEditing";
import { LabelChips } from "../LabelPicker";
import { LinkChips, noteLinks } from "./LinkChips";
import { noteDate } from "./noteDate";

const cardClass =
  "flex w-full min-w-0 flex-col gap-2 rounded-2xl border border-ui-border bg-ui-surface p-4 text-left transition-colors hover:border-ui-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ui-brand";

/** The body without its first line of words, for an untitled note whose first line is its heading. */
function afterFirstLine(body: string): string {
  const lines = body.split("\n");
  const at = lines.findIndex((l) => l.trim() !== "" && !/^!\[[^\]]*\]\([^)]*\)$/.test(l.trim()));
  return at < 0 ? "" : lines.slice(at + 1).join("\n");
}

/** One note in a list: its title (or first line), an excerpt, the first picture as a thumbnail,
 * the day, labels, links and a pin mark when pinned. The whole card is the tap target: a link to
 * the note with `to`, or a button with `onOpen` where the note opens in place. */
export default function NoteCard({ note, to, onOpen }: { note: NotrNote; to?: string; onOpen?: () => void }) {
  const heading = note.title.trim() || firstLine(note.body) || t("Untitled note");
  const text = excerpt(note.title.trim() ? note.body : afterFirstLine(note.body));
  const image = firstImage(note.body);
  const links = noteLinks(note);

  const content = (
    <>
      <div className="flex min-w-0 items-start gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex items-start gap-1.5">
            <h3 className="m-0 line-clamp-2 min-w-0 flex-1 font-display text-lg font-bold leading-snug tracking-[-0.01em] text-ui-ink [overflow-wrap:anywhere]">
              {heading}
            </h3>
            {note.pinned && <Pin size={16} aria-label={t("Pinned")} className="mt-1 shrink-0 fill-current text-ui-brand-strong" />}
          </div>
          {text && <p className="m-0 line-clamp-3 text-sm text-ui-ink-soft [overflow-wrap:anywhere]">{text}</p>}
        </div>
        {image && (
          <img
            src={image}
            alt=""
            loading="lazy"
            className="h-16 w-16 shrink-0 rounded-xl border border-ui-line object-cover"
          />
        )}
      </div>
      <LabelChips labels={note.labels} />
      <LinkChips links={links} />
      <span className="text-xs text-ui-muted">{noteDate(note.created_at)}</span>
    </>
  );

  if (to) {
    return (
      <Link to={to} className={cardClass}>
        {content}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onOpen} className={cardClass}>
      {content}
    </button>
  );
}
