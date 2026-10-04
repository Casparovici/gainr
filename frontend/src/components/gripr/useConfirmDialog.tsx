import { useState } from "react";

import GriprConfirmDialog from "./GriprConfirmDialog";

type PendingConfirm = {
  title: string;
  description: string;
  confirmLabel?: string;
  destructive?: boolean;
  resolve: (value: boolean) => void;
};

/** Promise-based replacement for `window.confirm()`, rendering Material's AlertDialog instead of
 * the browser's own unstyled one. `await confirm({...})` resolves to whether the user confirmed;
 * render `dialog` once, anywhere in the component's JSX (it's `null` until a confirmation is
 * pending). */
export function useConfirmDialog() {
  const [pending, setPending] = useState<PendingConfirm | null>(null);

  function confirm(options: { title: string; description: string; confirmLabel?: string; destructive?: boolean }) {
    return new Promise<boolean>((resolve) => setPending({ ...options, resolve }));
  }

  const dialog = pending ? (
    <GriprConfirmDialog
      title={pending.title}
      description={pending.description}
      confirmLabel={pending.confirmLabel}
      destructive={pending.destructive}
      onConfirm={() => {
        pending.resolve(true);
        setPending(null);
      }}
      onCancel={() => {
        pending.resolve(false);
        setPending(null);
      }}
    />
  ) : null;

  return { confirm, dialog };
}
