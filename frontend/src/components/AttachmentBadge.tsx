import { Paperclip } from "lucide-react";
import { tp } from "../i18n";

/** A small paperclip beside a transaction that has files attached; nothing when it has none. */
export default function AttachmentBadge({ count, variant = "gainr" }: { count: number; variant?: "gainr" | "gripr" }) {
  if (count === 0) return null;
  const label = tp(count, "{n} attachment", "{n} attachments");

  return (
    <span className={`ml-1.5 inline-flex items-center align-middle ${variant === "gripr" ? "text-on-surface-variant" : "text-slate-400"}`} title={label} aria-label={label}>
      <Paperclip className="h-3.5 w-3.5" strokeWidth={2} />
    </span>
  );
}
