import { useEffect } from "react";
import { t } from "../i18n";

/** A short-lived confirmation with an "undo" action, for one-tap actions that save immediately
 * (no form, no confirm) and so need a cheap way back from a mis-tap. Sits above MobileBottomNav on
 * a phone, bottom-centre on desktop, and dismisses itself after `durationMs`. */
export default function UndoToast({
  message,
  undoLabel = t("Ongedaan maken"),
  onUndo,
  onDismiss,
  durationMs = 8000,
}: {
  message: string;
  undoLabel?: string;
  onUndo: () => void;
  onDismiss: () => void;
  durationMs?: number;
}) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, durationMs);
    return () => window.clearTimeout(timer);
  }, [message, durationMs, onDismiss]);

  return (
    <div
      role="status"
      className="fixed inset-x-4 bottom-24 z-40 mx-auto flex max-w-md items-center justify-between gap-3 rounded-2xl bg-ui-edit-bar px-4 py-3 text-sm text-white shadow-lg sm:bottom-6"
    >
      <span className="min-w-0">{message}</span>
      <button type="button" onClick={onUndo} className="-my-2 shrink-0 py-2 font-medium text-emerald-300 hover:text-emerald-200">
        {undoLabel}
      </button>
    </div>
  );
}
