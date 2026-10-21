import { useEffect, useId, useRef, type ReactNode } from "react";
import { t } from "../../i18n";

/** The app's sheet: slides up from the bottom on a phone, where it sits in the thumb zone, and is
 * a centred dialog from tablet width up. What opens from a tapped row (a transaction, a list
 * item) and from a filter or module button lives in one of these, so a row needs no buttons of
 * its own. Closes on the backdrop, on Escape, and on the close button; focus moves into it. */
export default function Sheet({
  title,
  onClose,
  children,
  footer,
}: {
  /** Names the sheet for screen readers, and heads it unless the content brings its own heading. */
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Actions pinned under the content (Edit, Delete …). */
  footer?: ReactNode;
}) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  // Focus moves in once, on opening -- not again on a re-render, which would pull it back out of
  // a field inside the sheet. The Escape listener follows `onClose`, usually an inline arrow.
  useEffect(() => {
    panel.current?.focus();
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/45 sm:items-center sm:p-4" onClick={onClose}>
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[88vh] w-full flex-col overflow-hidden rounded-t-3xl bg-ui-surface text-ui-ink shadow-2xl outline-none sm:max-w-md sm:rounded-3xl"
      >
        <div aria-hidden className="mx-auto mt-2.5 h-1.5 w-10 shrink-0 rounded-full bg-ui-line sm:hidden" />
        <div className="flex items-center justify-between gap-3 px-5 pb-1 pt-3">
          <h2 id={titleId} className="m-0 font-display text-lg font-bold tracking-[-0.01em]">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("Close")}
            className="-mr-2 flex h-11 w-11 items-center justify-center rounded-xl text-2xl leading-none text-ui-muted hover:bg-ui-tile hover:text-ui-ink"
          >
            ×
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-4">{children}</div>
        {footer && <div className="flex flex-col gap-2 border-t border-ui-line/60 px-5 pb-6 pt-3 sm:pb-4">{footer}</div>}
      </div>
    </div>
  );
}
