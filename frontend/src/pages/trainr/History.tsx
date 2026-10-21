import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { trainrApi } from "../../api/trainrClient";
import {
  TRAINR_ACTIVITY_LABELS,
  TRAINR_DISTANCE_ACTIVITIES,
  TRAINR_MATCH_ACTIVITIES,
  type TrainrActivitySummary,
  type TrainrActivityType,
  type TrainrWorkout,
} from "../../api/trainrTypes";
import { ActivityIcon } from "../../components/trainr/activity";
import ActivitySelect from "../../components/trainr/ActivitySelect";
import { useWorkoutEditor } from "../../components/trainr/useWorkoutEditor";
import { IconChevronLeft, IconChevronRight, ModuleTopRow, PageTitle, iconButtonClass } from "../../components/ui/kit";
import {
  entrySummary,
  formatDuration,
  formatBpm,
  formatDurationLong,
  formatKcal,
  formatKg,
  formatKm,
  formatPace,
  formatSpeed,
  formatWeekLabel,
  workoutHeadline,
} from "../../utils/trainr";
import { addDays, addMonths, endOfMonth, fromIso, startOfMonth, startOfWeek, toIso } from "../../utils/weekCalendar";
import { dateLocale, msg, t, tp } from "../../i18n";

type Period = "week" | "month" | "year";

const PERIOD_LABELS: Record<Period, string> = { week: msg("Week"), month: msg("Maand"), year: msg("Jaar") };

function periodRange(period: Period, cursor: string): [string, string] {
  if (period === "week") return [startOfWeek(cursor), addDays(startOfWeek(cursor), 6)];
  if (period === "month") return [startOfMonth(cursor), endOfMonth(cursor)];
  const year = fromIso(cursor).getFullYear();
  return [`${year}-01-01`, `${year}-12-31`];
}

function SummaryTile({ summary }: { summary: TrainrActivitySummary }) {
  const lines = TRAINR_DISTANCE_ACTIVITIES.has(summary.activity_type)
    ? [formatKm(summary.total_distance_km), summary.avg_speed_kmh ? t("gem. {value}", { value: formatSpeed(summary.avg_speed_kmh) }) : null]
    : TRAINR_MATCH_ACTIVITIES.has(summary.activity_type)
      ? [
          summary.total_calories_kcal ? formatKcal(summary.total_calories_kcal) : null,
          summary.avg_heart_rate_bpm ? t("gem. {value}", { value: formatBpm(summary.avg_heart_rate_bpm) }) : null,
        ]
      : [summary.total_volume_kg ? t("{weight} volume", { weight: formatKg(summary.total_volume_kg) }) : null];
  return (
    <div className="flex flex-col gap-1 rounded-[20px] border border-ui-border bg-ui-surface p-4">
      <div className="flex items-center gap-1.5 text-sm font-semibold text-ui-muted">
        <ActivityIcon type={summary.activity_type} className="h-4 w-4 text-ui-brand" />
        {t(TRAINR_ACTIVITY_LABELS[summary.activity_type])}
      </div>
      <div className="font-display text-2xl font-bold tracking-[-0.02em] text-ui-ink">{summary.workouts}×</div>
      <div className="text-sm text-ui-ink-soft">
        {[summary.total_duration_seconds ? formatDurationLong(summary.total_duration_seconds) : null, ...lines].filter(Boolean).join(" · ")}
      </div>
    </div>
  );
}

function WorkoutDetails({ workout }: { workout: TrainrWorkout }) {
  if (TRAINR_DISTANCE_ACTIVITIES.has(workout.activity_type)) {
    const parts = [
      workout.duration_seconds ? formatDuration(workout.duration_seconds) : null,
      workout.avg_speed_kmh ? t("gem. {value}", { value: formatSpeed(workout.avg_speed_kmh) }) : null,
      workout.activity_type === "running" && workout.pace_seconds_per_km ? formatPace(workout.pace_seconds_per_km) : null,
      workout.max_speed_kmh ? t("top {value}", { value: formatSpeed(workout.max_speed_kmh) }) : null,
    ].filter(Boolean);
    return parts.length ? <p className="m-0 text-sm text-ui-ink-soft">{parts.join(" · ")}</p> : null;
  }
  if (TRAINR_MATCH_ACTIVITIES.has(workout.activity_type)) {
    const parts = [
      workout.duration_seconds ? formatDuration(workout.duration_seconds) : null,
      workout.calories_kcal ? formatKcal(workout.calories_kcal) : null,
      workout.avg_heart_rate_bpm ? t("gem. {value}", { value: formatBpm(workout.avg_heart_rate_bpm) }) : null,
      workout.max_heart_rate_bpm ? t("max {value}", { value: formatBpm(workout.max_heart_rate_bpm) }) : null,
    ].filter(Boolean);
    return parts.length ? <p className="m-0 text-sm text-ui-ink-soft">{parts.join(" · ")}</p> : null;
  }
  const totals = [
    workout.duration_seconds ? formatDuration(workout.duration_seconds) : null,
    workout.volume_kg ? t("{weight} volume", { weight: formatKg(workout.volume_kg) }) : null,
  ].filter(Boolean);
  return (
    <div className="flex flex-col gap-0.5">
      {workout.entries.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-0.5 p-0 text-sm">
          {workout.entries.map((e) => (
            <li key={e.id} className="flex justify-between gap-3">
              <span className="truncate text-ui-ink">{e.exercise_name}</span>
              <span className="shrink-0 tabular-nums text-ui-ink-soft">{entrySummary(e)}</span>
            </li>
          ))}
        </ul>
      )}
      {totals.length > 0 && <p className="m-0 text-sm text-ui-muted">{totals.join(" · ")}</p>}
    </div>
  );
}

/** One period back or forward from the cursor. */
function stepCursor(period: Period, cursor: string, direction: 1 | -1): string {
  if (period === "week") return addDays(cursor, 7 * direction);
  return addMonths(cursor, (period === "month" ? 1 : 12) * direction);
}

/** Done workouts per week, month or year: totals per activity on top, then each session, newest first. */
export default function TrainrHistory() {
  const [period, setPeriod] = useState<Period>("month");
  const [cursor, setCursor] = useState(toIso(new Date()));
  const [activity, setActivity] = useState<TrainrActivityType | "all">("all");
  const editor = useWorkoutEditor();
  const [from, to] = periodRange(period, cursor);

  const workoutsQuery = useQuery({
    queryKey: ["trainr-workouts", "history", from, to, activity],
    queryFn: () => trainrApi.listWorkouts(from, to, { completed: true, activityType: activity === "all" ? undefined : activity }),
  });
  const summaryQuery = useQuery({ queryKey: ["trainr-summary", from, to], queryFn: () => trainrApi.getSummary(from, to) });

  const workouts = [...(workoutsQuery.data ?? [])].reverse();
  const label =
    period === "week"
      ? formatWeekLabel(from)
      : period === "month"
        ? fromIso(from).toLocaleDateString(dateLocale("nl-NL"), { month: "long", year: "numeric" })
        : String(fromIso(from).getFullYear());
  const summary = summaryQuery.data;

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow>
        <div className="flex h-11 items-stretch gap-1 rounded-xl border border-ui-border bg-ui-surface p-1">
          {(["week", "month", "year"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              aria-pressed={period === p}
              className={`rounded-lg px-3 text-sm font-semibold transition-colors ${
                period === p ? "bg-ui-brand-soft text-ui-brand-strong" : "text-ui-muted hover:text-ui-ink"
              }`}
            >
              {t(PERIOD_LABELS[p])}
            </button>
          ))}
        </div>
      </ModuleTopRow>
      <PageTitle
        subtitle={
          summary
            ? `${tp(summary.workouts, "{n} workout", "{n} workouts")}${
                summary.total_duration_seconds ? ` · ${formatDurationLong(summary.total_duration_seconds)}` : ""
              }`
            : undefined
        }
      >{t("Historie")}</PageTitle>

      <div className="flex items-center justify-between gap-2">
        <button onClick={() => setCursor(stepCursor(period, cursor, -1))} className={iconButtonClass} aria-label={t("Vorige")}>
          <IconChevronLeft size={20} />
        </button>
        <span className="text-center text-[15px] font-semibold capitalize text-ui-ink">{label}</span>
        <button onClick={() => setCursor(stepCursor(period, cursor, 1))} className={iconButtonClass} aria-label={t("Volgende")}>
          <IconChevronRight size={20} />
        </button>
      </div>

      {summary && summary.by_activity.length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {summary.by_activity.map((s) => (
            <SummaryTile key={s.activity_type} summary={s} />
          ))}
        </div>
      )}

      <ActivitySelect value={activity} onChange={setActivity} allLabel={t("Alle activiteiten")} label={t("Filter op activiteit")} />

      {workoutsQuery.isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-400">{t("Laden…")}</div>
      ) : workoutsQuery.isError ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">{t("Kon de historie niet laden.")}{" "}
          <button onClick={() => workoutsQuery.refetch()} className="font-medium text-slate-900 underline">{t("Opnieuw proberen")}</button>
        </div>
      ) : workouts.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-400">
          {period === "week"
            ? t("Nog geen gedane workouts in deze week — vink er een af in de Planner.")
            : period === "month"
              ? t("Nog geen gedane workouts in deze maand — vink er een af in de Planner.")
              : t("Nog geen gedane workouts in deze periode — vink er een af in de Planner.")}
        </div>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {workouts.map((w) => (
            <li key={w.id}>
              <button
                onClick={() => editor.open(w.date, w)}
                className="flex w-full flex-col gap-1.5 rounded-2xl border border-ui-border bg-ui-surface px-4 py-3 text-left hover:border-ui-line"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2 font-semibold text-ui-ink">
                    <ActivityIcon type={w.activity_type} className="h-[18px] w-[18px] shrink-0 text-ui-brand" />
                    <span className="truncate">{workoutHeadline(w)}</span>
                  </span>
                  <span className="shrink-0 text-sm text-ui-muted">
                    {fromIso(w.date).toLocaleDateString(dateLocale("nl-NL"), { weekday: "short", day: "numeric", month: "short" })}
                  </span>
                </div>
                <WorkoutDetails workout={w} />
                {w.notes && <p className="m-0 text-sm italic text-ui-muted">{w.notes}</p>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {editor.dialog}
    </div>
  );
}
