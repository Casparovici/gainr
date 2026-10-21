import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Paperclip, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import type { AttachmentSource } from "../api/types";
import { ATTACHMENT_ACCEPT, formatFileSize, uploadAll } from "../utils/attachments";
import { t as tr } from "../i18n";

/** gainr and gripr style their forms with different colour tokens; the same section, in each one's. */
const THEMES = {
  gainr: {
    label: "text-slate-500",
    muted: "text-slate-400",
    row: "bg-slate-50",
    text: "text-slate-800",
    button: "border-slate-300 text-slate-700 hover:bg-slate-50",
    danger: "text-red-500 hover:text-red-700",
    error: "text-red-600",
    drop: "text-slate-400 hover:text-slate-700",
  },
  gripr: {
    label: "text-on-surface-variant",
    muted: "text-on-surface-variant",
    row: "bg-surface-container",
    text: "text-on-surface",
    button: "border-outline text-primary hover:bg-primary/10",
    danger: "text-error hover:opacity-80",
    error: "text-error",
    drop: "text-on-surface-variant hover:text-on-surface",
  },
} as const;

/** Files (invoices, contract notes) on a transaction. On a saved transaction they upload and delete
 * straight away; on a new one the picked files wait in `pending` and the parent uploads them once
 * the transaction exists. */
export default function TransactionAttachments({
  variant = "gainr",
  source,
  transactionId,
  pending,
  onPendingChange,
}: {
  variant?: keyof typeof THEMES;
  /** gainr's or gripr's attachment endpoints. */
  source: AttachmentSource;
  transactionId: number | null;
  pending: File[];
  onPendingChange: (files: File[]) => void;
}) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const attachmentsQuery = useQuery({
    queryKey: ["transaction-attachments", source.key, transactionId],
    queryFn: () => source.list(transactionId!),
    enabled: transactionId !== null,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["transaction-attachments", source.key, transactionId] });
    for (const queryKey of source.invalidates) queryClient.invalidateQueries({ queryKey });
  };
  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => uploadAll(source, transactionId!, files),
    onSuccess: (refused) => {
      setUploadError(refused.length ? refused.join("\n") : null);
      refresh();
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (attachmentId: number) => source.remove(transactionId!, attachmentId),
    onSuccess: refresh,
  });

  const pick = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (input.current) input.current.value = ""; // so picking the same file again still fires
    if (files.length === 0) return;
    if (transactionId === null) onPendingChange([...pending, ...files]);
    else uploadMutation.mutate(files);
  };

  const t = THEMES[variant];
  const saved = attachmentsQuery.data ?? [];
  const nothingYet = transactionId === null ? pending.length === 0 : attachmentsQuery.isSuccess && saved.length === 0;

  return (
    <div className="flex flex-col gap-1.5 text-sm">
      <div className="flex items-center justify-between">
        <span className={`text-xs font-medium uppercase tracking-wide ${t.label}`}>{tr("Attachments")}</span>
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={uploadMutation.isPending}
          className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium disabled:opacity-50 ${t.button}`}
        >
          <Paperclip className="h-3.5 w-3.5" strokeWidth={2} />
          {uploadMutation.isPending ? tr("Uploading…") : tr("Attach file")}
        </button>
        <input
          ref={input}
          type="file"
          multiple
          accept={ATTACHMENT_ACCEPT}
          className="hidden"
          aria-label={tr("Choose files to attach")}
          onChange={(e) => pick(e.target.files)}
        />
      </div>

      {transactionId !== null && attachmentsQuery.isLoading && <span className={`text-xs ${t.muted}`}>{tr("Loading attachments…")}</span>}
      {transactionId !== null && attachmentsQuery.isError && (
        <span className={`text-xs ${t.error}`}>{tr("Couldn't load this transaction's attachments.")}</span>
      )}
      {nothingYet && <span className={`text-xs ${t.muted}`}>{tr("No attachments yet — PDF, PNG, JPEG or WebP, up to 10 MB each.")}</span>}

      <ul className="flex flex-col gap-1">
        {saved.map((a) => (
          <li key={a.id} className={`flex items-center justify-between gap-2 rounded-md px-2 py-1 ${t.row}`}>
            <a
              href={source.url(a.transaction_id, a.id)}
              target="_blank"
              rel="noopener noreferrer"
              className={`min-w-0 truncate hover:underline ${t.text}`}
            >
              {a.filename} <span className={`text-xs ${t.muted}`}>· {formatFileSize(a.size_bytes)}</span>
            </a>
            <button
              type="button"
              onClick={() => {
                if (confirm(tr("Delete {file}? The file is removed from this transaction.", { file: a.filename }))) deleteMutation.mutate(a.id);
              }}
              disabled={deleteMutation.isPending}
              className={`shrink-0 disabled:opacity-50 ${t.danger}`}
              title={tr("Delete attachment")}
              aria-label={tr("Delete {file}", { file: a.filename })}
            >
              <Trash2 className="h-4 w-4" strokeWidth={2} />
            </button>
          </li>
        ))}
        {pending.map((file, index) => (
          <li key={`${file.name}-${index}`} className={`flex items-center justify-between gap-2 rounded-md px-2 py-1 ${t.row}`}>
            <span className={`min-w-0 truncate ${t.text}`}>
              {file.name} <span className={`text-xs ${t.muted}`}>· {formatFileSize(file.size)}{" "}{tr("· attached when you save")}</span>
            </span>
            <button
              type="button"
              onClick={() => onPendingChange(pending.filter((_, i) => i !== index))}
              className={`shrink-0 text-xs ${t.drop}`}
              title={tr("Don't attach")}
              aria-label={tr("Don't attach {file}", { file: file.name })}

            >
              ✕
            </button>
          </li>
        ))}
      </ul>

      {uploadError && <span className={`whitespace-pre-line text-xs ${t.error}`}>{tr("Not attached:")}{" "}{uploadError}</span>}
      {deleteMutation.isError && <span className={`text-xs ${t.error}`}>{tr("Couldn't delete that attachment — try again.")}</span>}
    </div>
  );
}
