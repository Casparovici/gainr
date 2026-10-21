import { RefreshCw } from "lucide-react";
import { t } from "../../i18n";

const TONES = {
  gripr: "text-on-surface-variant hover:bg-on-surface/10 hover:text-on-surface",
  gainr: "text-slate-500 hover:bg-slate-900/5 hover:text-slate-800",
} as const;

/** Every sync action in the app: an icon, not a word. The circular arrows spin while it runs;
 * `label` names it for screen readers and the tooltip ("Sync now"). */
export default function SyncButton({
  label = t("Sync now"),
  pendingLabel,
  pending,
  disabled,
  onClick,
  tone = "gripr",
}: {
  label?: string;
  /** Shown instead of `label` as the tooltip while it runs. */
  pendingLabel?: string;
  pending: boolean;
  disabled?: boolean;
  onClick: () => void;
  tone?: keyof typeof TONES;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending || disabled}
      aria-label={label}
      title={pending ? (pendingLabel ?? t("Syncing…")) : label}
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl disabled:opacity-50 ${TONES[tone]}`}
    >
      <RefreshCw className={`h-4 w-4 ${pending ? "animate-spin" : ""}`} aria-hidden />
    </button>
  );
}
