import type { MouseEvent, ReactNode } from "react";

/** The overlay half of every centred dialog in the app — a full-screen dim backdrop that
 * closes the dialog on click, with the card itself stopping that click from bubbling so
 * interacting with the dialog's own content never closes it. */
export default function ModalOverlay({
  onClose,
  cardClassName,
  children,
}: {
  onClose: () => void;
  cardClassName: string;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div className={cardClassName} onClick={(e: MouseEvent) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}
