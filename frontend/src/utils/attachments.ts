import type { AttachmentSource } from "../api/types";
import { t } from "../i18n";

/** The file types the backend accepts for a transaction's attachments (it checks the bytes too). */
export const ATTACHMENT_ACCEPT = "application/pdf,image/png,image/jpeg,image/webp";

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toLocaleString("nl-NL", { maximumFractionDigits: 1 })} MB`;
}

/** The backend's reason for refusing an upload ("That file is larger than 10 MB."), pulled out of
 * the `status statusText: {"detail": "…"}` message the API client throws; a generic line when the
 * failure wasn't a refusal (network down, an error page). */
export function attachmentErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : "";
  const start = message.indexOf("{");
  if (start !== -1) {
    try {
      const detail: unknown = JSON.parse(message.slice(start)).detail;
      if (typeof detail === "string" && detail) return detail;
    } catch {
      // Not JSON: fall through to the generic line.
    }
  }
  return t("The upload failed.");
}

/** A transaction saved first and its files uploaded after: say which files didn't make it, since
 * the form has already closed on the saved transaction. */
export function warnFailedAttachments(failed: string[]): void {
  if (failed.length === 0) return;
  const files = failed.join("\n");
  window.alert(
    failed.length === 1
      ? t("The transaction was saved, but this file wasn't attached:\n\n{files}\n\nOpen the transaction to try again.", { files })
      : t("The transaction was saved, but these files weren't attached:\n\n{files}\n\nOpen the transaction to try again.", { files }),
  );
}

/** Uploads each file in turn and returns the ones that were refused, as "name — reason": one
 * refused file doesn't stop the rest. */
export async function uploadAll(source: AttachmentSource, transactionId: number, files: File[]): Promise<string[]> {
  const refused: string[] = [];
  for (const file of files) {
    try {
      await source.upload(transactionId, file);
    } catch (error) {
      refused.push(`${file.name} — ${attachmentErrorMessage(error)}`);
    }
  }
  return refused;
}
