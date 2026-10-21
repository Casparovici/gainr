import { ChevronLeft, ChevronRight, Settings } from "lucide-react";
import { useState } from "react";

import { currentPeriodStart, periodBounds, shiftPeriod } from "../../utils/griprPeriod";
import GriprSettingsDialog from "./GriprSettingsDialog";
import { dateLocale, t } from "../../i18n";

export function formatPeriodLabel(periodStart: string, startDay: number): string {
  if (startDay === 1) {
    // The common case, unchanged from before this setting existed.
    return new Date(periodStart + "T00:00:00").toLocaleDateString(dateLocale("en-IE"), { month: "long", year: "numeric" });
  }
  const { end } = periodBounds(periodStart, startDay);
  const day = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString(dateLocale("en-IE"), { day: "numeric", month: "short" });
  const year = new Date(end + "T00:00:00").toLocaleDateString(dateLocale("en-IE"), { year: "numeric" });
  return `${day(periodStart)} – ${day(end)} ${year}`;
}

/** Steps a period back/forward one at a time — same paging interaction as the calendar-month
 * switcher it replaces, generalized to any configured period-start-day (see utils/griprPeriod.ts
 * and docs/adr/0004-gripr-period-boundary.md). The gear next to it opens gripr's settings, where
 * the period-start-day lives, so it stays reachable from every page that shows a period. */
export default function PeriodSwitcher({
  periodStart,
  startDay,
  onChange,
}: {
  periodStart: string;
  startDay: number;
  onChange: (periodStart: string) => void;
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="relative flex items-center gap-0.5">
      <button
        type="button"
        onClick={() => onChange(shiftPeriod(periodStart, -1))}
        aria-label={t("Previous period")}
        className="flex h-10 w-10 items-center justify-center rounded-xl text-on-surface-variant hover:bg-on-surface/10 hover:text-on-surface"
      >
        <ChevronLeft className="h-5 w-5" />
      </button>
      <span className="min-w-[9rem] whitespace-nowrap text-center text-[15px] font-semibold text-on-surface">
        {formatPeriodLabel(periodStart, startDay)}
      </span>
      <button
        type="button"
        onClick={() => onChange(shiftPeriod(periodStart, 1))}
        aria-label={t("Next period")}
        className="flex h-10 w-10 items-center justify-center rounded-xl text-on-surface-variant hover:bg-on-surface/10 hover:text-on-surface"
      >
        <ChevronRight className="h-5 w-5" />
      </button>
      <button
        type="button"
        onClick={() => setSettingsOpen(true)}
        aria-label={t("Settings")}
        title={t("Settings: when a period starts, and your banks")}
        // From tablet width up the shared header carries gripr's gear (App.tsx).
        className="ml-1 rounded-full p-1.5 sm:hidden text-on-surface-variant hover:bg-on-surface/10 hover:text-on-surface"
      >
        <Settings className="h-4 w-4" />
      </button>

      {settingsOpen && (
        <GriprSettingsDialog
          onClose={() => setSettingsOpen(false)}
          // The period on screen may not exist under the new start day -- land on the one
          // containing today instead of translating the old one.
          onPeriodSaved={(day) => onChange(currentPeriodStart(day))}
        />
      )}
    </div>
  );
}
