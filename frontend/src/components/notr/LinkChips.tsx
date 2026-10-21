import { ChefHat, Sprout, TrendingUp, X, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import type { NotrNote } from "../../api/notrTypes";
import { positionPath } from "../../config/modules";
import { t } from "../../i18n";

export type LinkKind = "asset" | "plant" | "recipe";

/** One thing a note is about, as a chip shows it. */
export interface NoteLink {
  kind: LinkKind;
  id: number;
  label: string;
}

const ICONS: Record<LinkKind, LucideIcon> = { asset: TrendingUp, plant: Sprout, recipe: ChefHat };

/** Where a link leads. A plant has no page of its own to deep-link to yet, so it goes to the
 * plants list. */
export function linkPath(link: NoteLink): string {
  if (link.kind === "asset") return positionPath(link.id);
  if (link.kind === "plant") return "/gardnr/plants";
  return `/listr/recept/${link.id}`;
}

/** The positions, plants and recipes of a note, in that order. */
export function noteLinks(note: Pick<NotrNote, "assets" | "plants" | "recipes">): NoteLink[] {
  return [
    ...note.assets.map((a): NoteLink => ({ kind: "asset", id: a.id, label: a.ticker })),
    ...note.plants.map((p): NoteLink => ({ kind: "plant", id: p.id, label: p.name })),
    ...note.recipes.map((r): NoteLink => ({ kind: "recipe", id: r.id, label: r.title })),
  ];
}

const chipClass =
  "inline-flex min-w-0 max-w-full items-center gap-1 rounded-full bg-ui-brand-soft px-2.5 py-0.5 text-xs font-semibold text-ui-brand-strong";

/** A note's links as small chips. `asLinks` makes each one go to its target (the read view); in a
 * card, where the whole card is already a link, they are plain text. */
export function LinkChips({ links, asLinks = false }: { links: NoteLink[]; asLinks?: boolean }) {
  if (links.length === 0) return null;
  return (
    <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
      {links.map((link) => {
        const Icon = ICONS[link.kind];
        const content = (
          <>
            <Icon size={12} aria-hidden className="shrink-0" />
            <span className="truncate">{link.label}</span>
          </>
        );
        return (
          <li key={`${link.kind}-${link.id}`} className="min-w-0 max-w-full">
            {asLinks ? (
              <Link to={linkPath(link)} className={`${chipClass} hover:underline`}>
                {content}
              </Link>
            ) : (
              <span className={chipClass}>{content}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** The editor's version: each chip has a button that takes the link off the note. */
export function RemovableLinkChips({ links, onRemove }: { links: NoteLink[]; onRemove: (link: NoteLink) => void }) {
  if (links.length === 0) return null;
  return (
    <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
      {links.map((link) => {
        const Icon = ICONS[link.kind];
        return (
          <li key={`${link.kind}-${link.id}`} className={`${chipClass} h-8 pl-3 pr-1 text-sm`}>
            <Icon size={14} aria-hidden className="shrink-0" />
            <span className="truncate">{link.label}</span>
            <button
              type="button"
              onClick={() => onRemove(link)}
              aria-label={t("Remove {name}", { name: link.label })}
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full hover:bg-ui-brand/15"
            >
              <X size={14} aria-hidden />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
