import { useEffect, useId, useState, type ReactNode } from "react";

import { InfoButton } from "./ui/InfoTip";

const STORAGE_PREFIX = "gainr.collapsed.";

/** Whether a section was left open last time, falling back to `defaultOpen`.
 *
 * Exported so a caller can line up its *initial* state with the card's on the very first
 * render — Home uses it to decide whether to fetch the performance series at all, and
 * learning that a beat later (from onOpenChange) would already have fired the request. */
export function readCollapsibleState(storageKey: string, defaultOpen = true): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + storageKey);
    return raw === null ? defaultOpen : raw === "open";
  } catch {
    // Private windows and blocked site data throw on access — the section just falls back to
    // its default state rather than failing to render.
    return defaultOpen;
  }
}

/** A card whose body can be folded away, remembering the choice across reloads.
 *
 * `meta` stays visible when collapsed, so folding the performance chart still leaves the
 * headline number it was illustrating on screen. */
export default function CollapsibleCard({
  storageKey,
  title,
  meta,
  defaultOpen = true,
  bodyClassName = "px-4 pb-4",
  cardClassName = "rounded-lg border border-slate-200 bg-white",
  onOpenChange,
  info,
  infoLabel,
  children,
}: {
  storageKey: string;
  title: ReactNode;
  meta?: ReactNode;
  /** What the section is for, folded behind an ⓘ next to the title rather than always on screen. */
  info?: ReactNode;
  /** Names the section for the ⓘ button ("About …") when `title` isn't plain text. */
  infoLabel?: string;
  defaultOpen?: boolean;
  bodyClassName?: string;
  /** Overrides the card's own shape/colour -- gripr's Material redesign passes its own
   * token-based classes here rather than this default, which every other caller keeps. */
  cardClassName?: string;
  onOpenChange?: (open: boolean) => void;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(() => readCollapsibleState(storageKey, defaultOpen));
  const [infoOpen, setInfoOpen] = useState(false);
  const infoId = useId();

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_PREFIX + storageKey, open ? "open" : "closed");
    } catch {
      // Nothing to do — the section still works, it just won't be remembered.
    }
    onOpenChange?.(open);
    // onOpenChange is typically an inline arrow, so depending on it would re-run this on
    // every render of the parent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey, open]);

  return (
    <div className={cardClassName}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex min-w-[9rem] flex-1 items-center gap-2 text-left text-sm font-medium text-slate-700"
        >
          <span aria-hidden className="text-xs text-slate-400">
            {open ? "▼" : "►"}
          </span>
          <span className="collapsible-title min-w-0 truncate">{title}</span>
        </button>
        {info && (
          <InfoButton
            label={infoLabel ?? (typeof title === "string" ? title : storageKey)}
            open={infoOpen}
            onToggle={() => setInfoOpen((v) => !v)}
            controls={infoId}
            className="text-slate-400 hover:text-slate-600"
          />
        )}
        {/* The title keeps a minimum width, so a wide `meta` wraps below it instead of squeezing it out. */}
        {meta && <div className="min-w-0 max-w-full">{meta}</div>}
      </div>
      {info && (
        <p id={infoId} hidden={!infoOpen} className="px-4 pb-3 text-sm text-slate-600">
          {info}
        </p>
      )}

      {open && <div className={bodyClassName}>{children}</div>}
    </div>
  );
}
