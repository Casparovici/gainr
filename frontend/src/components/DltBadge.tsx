import type { DltJudgment } from "../api/types";
import { msg, t } from "../i18n";

// Same badge shape gripr uses for its expense/income/transfer pills, reused here so the two
// halves of the app read as one visual language rather than inventing a second rating style.
const DLT_BADGE: Record<DltJudgment | "none", { label: string; className: string }> = {
  attractive: { label: msg("Attractive"), className: "bg-emerald-50 text-emerald-700" },
  neutral: { label: msg("Neutral"), className: "bg-slate-100 text-slate-600" },
  critical: { label: msg("Critical"), className: "bg-red-50 text-red-700" },
  none: { label: msg("No rating"), className: "bg-slate-100 text-slate-500" },
};

/** DLT's call on a holding. `unrated` decides how a holding DLT hasn't rated shows: as Neutral
 * (the positions table, where it reads as "no reason to act") or as "No rating" where the
 * difference matters, like the rebalance helper, which leaves unrated holdings out. */
export default function DltBadge({ judgment, unrated = "neutral" }: { judgment: DltJudgment | null; unrated?: "neutral" | "none" }) {
  const badge = DLT_BADGE[judgment ?? (unrated === "none" ? "none" : "neutral")];
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}>{t(badge.label)}</span>
;
}
