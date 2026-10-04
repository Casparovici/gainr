import ModalOverlay from "../ModalOverlay";

/** Material's AlertDialog -- title, supporting text, two text buttons right-aligned -- in place
 * of the browser's own `confirm()`, which can't be styled or themed and looks like nothing else
 * in the app. See `useConfirmDialog` for the hook that renders this from a promise-based call. */
export default function GriprConfirmDialog({
  title,
  description,
  confirmLabel = "Delete",
  destructive = true,
  onConfirm,
  onCancel,
}: {
  title: string;
  description: string;
  confirmLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-sm rounded-[28px] bg-surface p-6 shadow-xl">
      <h2 className="text-lg font-medium text-on-surface">{title}</h2>
      <p className="mt-2 text-sm text-on-surface-variant">{description}</p>
      <div className="mt-6 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-full px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onConfirm}
          className={`rounded-full px-4 py-2 text-sm font-medium ${
            destructive ? "text-error hover:bg-error/10" : "text-primary hover:bg-primary/10"
          }`}
        >
          {confirmLabel}
        </button>
      </div>
    </ModalOverlay>
  );
}
