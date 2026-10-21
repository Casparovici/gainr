import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { trainrApi } from "../../api/trainrClient";
import type { TrainrWorkout } from "../../api/trainrTypes";
import MobileFab from "../../components/MobileFab";
import WorkoutChip from "../../components/trainr/WorkoutChip";
import { canStart, useWorkoutEditor } from "../../components/trainr/useWorkoutEditor";
import {
  IconChevronLeft,
  IconChevronRight,
  IconPlus,
  ModuleTopRow,
  PageTitle,
  iconButtonClass,
  primaryButtonClass,
} from "../../components/ui/kit";
import {
  WEEKDAY_LABELS,
  addDays,
  addMonths,
  endOfMonth,
  fromIso,
  range,
  startOfMonth,
  startOfWeek,
  toIso,
} from "../../utils/weekCalendar";
import { dateLocale, t } from "../../i18n";

/** trainr's planner: listr's Weekplanner shape (week/month, a day row per date on a phone), but a
 * day holds any number of workouts. Tapping a day plans one; ticking one off moves it into the
 * history. */
export default function TrainrPlanner() {
  const today = toIso(new Date());
  const [viewMode, setViewMode] = useState<"week" | "month">("week");
  const [cursor, setCursor] = useState(today);
  const editor = useWorkoutEditor();

  const weekStart = startOfWeek(cursor);
  const monthStart = startOfMonth(cursor);
  const gridStart = viewMode === "week" ? weekStart : startOfWeek(monthStart);
  const gridEnd = viewMode === "week" ? addDays(weekStart, 6) : addDays(startOfWeek(endOfMonth(cursor)), 6);
  const days = range(gridStart, gridEnd);

  const workoutsQuery = useQuery({
    queryKey: ["trainr-workouts", "planner", gridStart, gridEnd],
    queryFn: () => trainrApi.listWorkouts(gridStart, gridEnd),
  });

  const byDate = new Map<string, TrainrWorkout[]>();
  for (const w of workoutsQuery.data ?? []) byDate.set(w.date, [...(byDate.get(w.date) ?? []), w]);

  const scopeStart = viewMode === "week" ? weekStart : monthStart;
  const scopeEnd = viewMode === "week" ? addDays(weekStart, 6) : endOfMonth(cursor);
  const inScope = (workoutsQuery.data ?? []).filter((w) => w.date >= scopeStart && w.date <= scopeEnd);
  const doneCount = inScope.filter((w) => w.is_completed).length;
  const plannedCount = inScope.length - doneCount;
  const subtitle =
    viewMode === "week"
      ? t("{done} gedaan · {planned} gepland deze week", { done: doneCount, planned: plannedCount })
      : t("{done} gedaan · {planned} gepland deze maand", { done: doneCount, planned: plannedCount });

  const label =
    viewMode === "week"
      ? `${fromIso(weekStart).toLocaleDateString(dateLocale("nl-NL"), { day: "numeric", month: "short" })} – ${fromIso(
          addDays(weekStart, 6),
        ).toLocaleDateString(dateLocale("nl-NL"), { day: "numeric", month: "short", year: "numeric" })}`
      : fromIso(monthStart).toLocaleDateString(dateLocale("nl-NL"), { month: "long", year: "numeric" });

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow>
        <div className="flex h-11 items-stretch gap-1 rounded-xl border border-ui-border bg-ui-surface p-1">
          {(["week", "month"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              aria-pressed={viewMode === mode}
              className={`rounded-lg px-3 text-sm font-semibold transition-colors ${
                viewMode === mode ? "bg-ui-brand-soft text-ui-brand-strong" : "text-ui-muted hover:text-ui-ink"
              }`}
            >
              {mode === "week" ? t("Week") : t("Maand")}
            </button>
          ))}
        </div>
      </ModuleTopRow>
      <div className="flex items-end justify-between gap-3">
        <PageTitle subtitle={subtitle}>{t("Planner")}</PageTitle>
        <button onClick={() => editor.open(today)} className={`${primaryButtonClass} hidden sm:inline-flex`}>
          <IconPlus size={18} />{t("Workout")}</button>
      </div>

      <div className="flex items-center justify-between gap-2">
        <button
          onClick={() => setCursor(viewMode === "week" ? addDays(cursor, -7) : addMonths(cursor, -1))}
          className={iconButtonClass}
          aria-label={t("Vorige")}
        >
          <IconChevronLeft size={20} />
        </button>
        <span className="text-center text-[15px] font-semibold capitalize text-ui-ink">{label}</span>
        <button
          onClick={() => setCursor(viewMode === "week" ? addDays(cursor, 7) : addMonths(cursor, 1))}
          className={iconButtonClass}
          aria-label={t("Volgende")}
        >
          <IconChevronRight size={20} />
        </button>
      </div>

      {workoutsQuery.isError ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">{t("Kon de workouts niet laden.")}{" "}
          <button onClick={() => workoutsQuery.refetch()} className="font-medium text-slate-900 underline">{t("Opnieuw proberen")}</button>
        </div>
      ) : (
        // Below `sm` every day is a full-width row; month view's days from adjacent months only
        // keep the grid aligned, so they're dropped from that stacked list (as in the Weekplanner).
        <div className={`grid grid-cols-1 gap-2 sm:grid-cols-7 ${workoutsQuery.isLoading ? "opacity-60" : ""}`} aria-busy={workoutsQuery.isLoading}>
          {viewMode === "month" &&
            WEEKDAY_LABELS.map((weekday) => (
              <div key={weekday} className="hidden text-center text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted sm:block">
                {t(weekday)}
              </div>
            ))}
          {days.map((dateIso) => {
            const workouts = byDate.get(dateIso) ?? [];
            const isOutsideMonth = viewMode === "month" && (dateIso < monthStart || dateIso > endOfMonth(cursor));
            const isToday = dateIso === today;
            const d = fromIso(dateIso);
            return (
              <div
                key={dateIso}
                onClick={() => editor.open(dateIso)}
                className={`min-h-[56px] cursor-pointer items-center gap-3 rounded-2xl border px-4 py-2 text-left transition-colors hover:border-ui-line sm:min-h-[96px] sm:flex-col sm:items-stretch sm:gap-1.5 sm:px-2.5 ${
                  isOutsideMonth ? "hidden border-ui-border bg-ui-tile sm:flex" : "flex border-ui-border bg-ui-surface"
                } ${isToday ? "border-ui-brand ring-1 ring-ui-brand" : ""}`}
              >
                <span
                  className={`w-24 shrink-0 text-sm font-semibold sm:w-auto sm:text-xs ${
                    isOutsideMonth ? "text-ui-faint" : isToday ? "text-ui-brand-strong" : "text-ui-muted"
                  }`}
                >
                  <span className="sm:hidden">{d.toLocaleDateString(dateLocale("nl-NL"), { weekday: "short", day: "numeric", month: "short" })}</span>
                  <span className="hidden sm:inline">
                    {viewMode === "week" ? d.toLocaleDateString(dateLocale("nl-NL"), { weekday: "short", day: "numeric" }) : d.getDate()}
                  </span>
                </span>
                {workouts.length > 0 ? (
                  <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-none">
                    {workouts.map((w) => (
                      <WorkoutChip
                        key={w.id}
                        workout={w}
                        onOpen={() => editor.open(w.date, w)}
                        onToggle={() => editor.toggleCompleted(w)}
                        onStart={canStart(w) ? () => editor.start(w) : undefined}
                      />
                    ))}
                  </div>
                ) : (
                  !isOutsideMonth && <span className="flex-1 text-sm text-ui-faint sm:flex-none sm:text-xs">{t("+ plannen")}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
      {editor.toggleError && <p className="text-sm text-red-600">{t("Afvinken is mislukt — probeer het opnieuw.")}</p>}

      <MobileFab label={t("Workout")} onClick={() => editor.open(today)} />
      {editor.dialog}
      {editor.runner}
    </div>
  );
}
