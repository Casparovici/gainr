import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { trainrApi } from "../../api/trainrClient";
import {
  TRAINR_ACTIVITY_LABELS,
  TRAINR_DISTANCE_ACTIVITIES,
  TRAINR_MUSCLE_GROUP_LABELS,
  type TrainrActivityType,
  type TrainrExerciseProgress,
  type TrainrOverview,
  type TrainrPeriodKey,
  type TrainrPeriodTile,
  type TrainrRecord,
  type TrainrSeriesPoint,
} from "../../api/trainrTypes";
import ActivitySelect from "../../components/trainr/ActivitySelect";
import { ModuleTopRow, PageTitle } from "../../components/ui/kit";
import { toNumber } from "../../utils/format";
import {
  formatCountDelta,
  formatDuration,
  formatDurationLong,
  formatBpm,
  formatKcal,
  formatKg,
  formatKm,
  formatKmDelta,
  formatKmRounded,
  formatPace,
  formatSpeed,
} from "../../utils/trainr";
import { fromIso } from "../../utils/weekCalendar";
import { dateLocale, msg, t as tr, tp } from "../../i18n";

// Cycling first: the overview opens on what's done most, until the reader picks another.
const ACTIVITY_ORDER: TrainrActivityType[] = ["cycling", "running", "home_gym", "football", "padel"];
const STORAGE_KEY = "trainr.overview.activity";

const PERIOD_LABELS: Record<TrainrPeriodKey, string> = { week: msg("Deze week"), month: msg("Deze maand"), year: msg("Dit jaar"), all: msg("Totaal") };
const PREVIOUS_LABELS: Record<TrainrPeriodKey, string> = { week: msg("vorige week"), month: msg("vorige maand"), year: msg("vorig jaar"), all: "" };

function isActivity(value: string | null): value is TrainrActivityType {
  return value !== null && (ACTIVITY_ORDER as string[]).includes(value);
}

function readStoredActivity(): TrainrActivityType {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isActivity(stored)) return stored;
  } catch {
    // Storage blocked (private window): fall back to the default.
  }
  return "cycling";
}

function Card({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="rounded-[20px] border border-ui-border bg-ui-surface p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function ChartTooltip<Row>({
  active,
  payload,
  render,
}: {
  active?: boolean;
  payload?: { payload: Row }[];
  render: (row: Row) => { title: string; lines: string[] };
}) {
  if (!active || !payload?.length) return null;
  const { title, lines } = render(payload[0].payload);
  return (
    <div className="rounded-lg border border-ui-border bg-ui-surface px-3 py-2 text-xs shadow-sm">
      <div className="mb-0.5 font-semibold capitalize text-ui-ink">{title}</div>
      {lines.map((line) => (
        <div key={line} className="text-ui-ink-soft">
          {line}
        </div>
      ))}
    </div>
  );
}

const axisTick = { fontSize: 12 };

// -- period tiles ------------------------------------------------------------------------------

function PeriodTile({ tile, isDistance, since }: { tile: TrainrPeriodTile; isDistance: boolean; since: string | null }) {
  const { current, previous } = tile;
  const hero = isDistance ? formatKmRounded(current.distance_km) : `${current.workouts}×`;
  const details = [
    isDistance ? `${current.workouts}×` : current.volume_kg ? tr("{weight} volume", { weight: formatKg(current.volume_kg) }) : null,
    current.duration_seconds ? formatDurationLong(current.duration_seconds) : null,
    current.calories_kcal ? formatKcal(current.calories_kcal) : null,
    current.avg_heart_rate_bpm ? tr("gem. {value}", { value: formatBpm(current.avg_heart_rate_bpm) }) : null,
  ].filter(Boolean);
  const delta = previous
    ? tr("{change} t.o.v. {previous}", {
        change: isDistance ? formatKmDelta(current.distance_km, previous.distance_km) : formatCountDelta(current.workouts, previous.workouts),
        previous: tr(PREVIOUS_LABELS[tile.key]),
      })
    : since
      ? tr("sinds {year}", { year: since })
      : null;
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-[20px] border border-ui-border bg-ui-surface p-4">
      <span className="text-sm font-semibold text-ui-muted">{tr(PERIOD_LABELS[tile.key])}</span>
      <span className="truncate font-display text-[28px] font-bold leading-tight tracking-[-0.02em] text-ui-ink">{hero}</span>
      <span className="text-sm text-ui-ink-soft">{current.workouts === 0 ? tr("Nog niets") : details.join(" · ")}</span>
      {delta && <span className="text-xs text-ui-muted">{delta}</span>}
    </div>
  );
}

// -- series charts -------------------------------------------------------------------------------

type Grain = "month" | "year";

function periodLabel(point: TrainrSeriesPoint, grain: Grain, long = false): string {
  const d = fromIso(point.period_start);
  if (grain === "year") return String(d.getFullYear());
  return long
    ? d.toLocaleDateString(dateLocale("nl-NL"), { month: "long", year: "numeric" })
    : d.toLocaleDateString(dateLocale("nl-NL"), { month: "short" }).replace(".", "");
}

function seriesLines(p: TrainrSeriesPoint, isDistance: boolean): string[] {
  const lines = [`${p.workouts}×`];
  if (isDistance && p.distance_km) lines.unshift(formatKm(p.distance_km));
  if (!isDistance && p.volume_kg) lines.push(tr("{weight} volume", { weight: formatKg(p.volume_kg) }));
  if (p.duration_seconds) lines.push(formatDurationLong(p.duration_seconds));
  if (p.calories_kcal) lines.push(formatKcal(p.calories_kcal));
  if (p.avg_heart_rate_bpm) lines.push(tr("gem. {value}", { value: formatBpm(p.avg_heart_rate_bpm) }));
  return lines;
}

function AmountChart({ points, grain, isDistance }: { points: TrainrSeriesPoint[]; grain: Grain; isDistance: boolean }) {
  const rows = points.map((p) => ({
    ...p,
    label: periodLabel(p, grain),
    value: isDistance ? (toNumber(p.distance_km) ?? 0) : p.workouts,
  }));
  return (
    <div className="kit-bars h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="label" tick={axisTick} tickLine={false} interval="preserveStartEnd" minTickGap={8} />
          <YAxis
            tick={axisTick}
            axisLine={false}
            tickLine={false}
            width={48}
            allowDecimals={false}
            tickFormatter={(v: number) => (isDistance ? `${v.toLocaleString("nl-NL", { notation: "compact" })}` : String(v))}
          />
          <Tooltip
            content={
              <ChartTooltip<(typeof rows)[number]> render={(r) => ({ title: periodLabel(r, grain, true), lines: seriesLines(r, isDistance) })} />
            }
          />
          <Bar dataKey="value" name={isDistance ? tr("Afstand") : tr("Sessies")} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function TrendChart({ points, grain, running }: { points: TrainrSeriesPoint[]; grain: Grain; running: boolean }) {
  const rows = points.map((p) => ({
    ...p,
    label: periodLabel(p, grain),
    value: running ? p.pace_seconds_per_km : toNumber(p.avg_speed_kmh),
  }));
  if (rows.filter((r) => r.value !== null).length < 2) {
    return (
      <p className="m-0 py-10 text-center text-sm text-ui-muted">
        {grain === "month" ? tr("Te weinig maanden met afstand én tijd voor een lijn — bekijk het per jaar.") : tr("Te weinig jaren met afstand én tijd voor een lijn.")}
      </p>
    );
  }
  return (
    <div className="kit-line h-48">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="label" tick={axisTick} tickLine={false} interval="preserveStartEnd" minTickGap={8} />
          {/* Pace: lower is faster, so the axis is flipped and "up" still means better. */}
          <YAxis
            tick={axisTick}
            axisLine={false}
            tickLine={false}
            width={48}
            reversed={running}
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => (running ? formatDuration(Math.round(v)) : v.toLocaleString("nl-NL", { maximumFractionDigits: 0 }))}
          />
          <Tooltip
            content={
              <ChartTooltip<(typeof rows)[number]>
                render={(r) => ({
                  title: periodLabel(r, grain, true),
                  lines: [running ? formatPace(r.pace_seconds_per_km) : formatSpeed(r.avg_speed_kmh), `${r.workouts}×`],
                })}
              />
            }
          />
          <Line type="linear" dataKey="value" strokeWidth={2} dot={{ r: 4, strokeWidth: 2 }} activeDot={{ r: 5, strokeWidth: 2 }} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// -- records -------------------------------------------------------------------------------------

function recordText(r: TrainrRecord): { label: string; value: string; detail?: string } {
  switch (r.kind) {
    case "longest_distance":
      return { label: tr("Langste afstand"), value: formatKm(r.value) };
    case "longest_duration":
      return { label: tr("Langste duur"), value: formatDurationLong(Number(r.value)) };
    case "fastest_avg_speed":
      return { label: tr("Snelste gemiddelde (vanaf 20 km)"), value: formatSpeed(r.value) };
    case "best_pace":
      return { label: tr("Snelste tempo (vanaf 3 km)"), value: formatPace(Number(r.value)) };
    case "heaviest_lift":
      return { label: tr("Zwaarste gewicht"), value: formatKg(r.value), detail: r.detail ?? undefined };
    case "biggest_volume":
      return { label: tr("Grootste volume in één sessie"), value: formatKg(r.value) };
    case "most_calories":
      return { label: tr("Meeste calorieën"), value: formatKcal(Number(r.value)) };
    case "highest_heart_rate":
      return { label: tr("Hoogste hartslag"), value: formatBpm(Number(r.value)) };
  }
}

function Records({ records }: { records: TrainrRecord[] }) {
  return (
    <ul className="m-0 flex list-none flex-col p-0">
      {records.map((r) => {
        const { label, value, detail } = recordText(r);
        const day = fromIso(r.date).toLocaleDateString(dateLocale("nl-NL"), { day: "numeric", month: "short", year: "numeric" });
        return (
          <li key={r.kind} className="flex min-h-[48px] items-center justify-between gap-3 border-b border-ui-border py-2 last:border-0">
            <div className="flex min-w-0 flex-col">
              <span className="truncate text-[15px] text-ui-ink">{label}</span>
              <span className="truncate text-xs text-ui-muted">{detail ? `${detail} · ${day}` : day}</span>
            </div>
            <span className="shrink-0 font-semibold tabular-nums text-ui-ink">{value}</span>
          </li>
        );
      })}
    </ul>
  );
}

// -- home gym ------------------------------------------------------------------------------------

function MuscleGroupChart({ overview }: { overview: TrainrOverview }) {
  const rows = overview.muscle_groups.map((m) => ({ ...m, label: tr(TRAINR_MUSCLE_GROUP_LABELS[m.muscle_group]) }));
  return (
    <div className="kit-bars" style={{ height: Math.max(120, rows.length * 36) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid horizontal={false} />
          <XAxis type="number" tick={axisTick} tickLine={false} allowDecimals={false} />
          <YAxis type="category" dataKey="label" tick={axisTick} axisLine={false} tickLine={false} width={84} />
          <Tooltip
            content={
              <ChartTooltip<(typeof rows)[number]>
                render={(r) => ({ title: r.label, lines: [tr("{n} sets", { n: r.sets }), ...(r.volume_kg ? [tr("{weight} volume", { weight: formatKg(r.volume_kg) })] : [])] })}
              />
            }
          />
          <Bar dataKey="sets" name={tr("Sets")} radius={[0, 4, 4, 0]} maxBarSize={24} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ExerciseProgressCard({ exercises }: { exercises: TrainrExerciseProgress[] }) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const exercise = exercises.find((e) => e.exercise_id === selectedId) ?? exercises[0];
  const rows = exercise.points.map((p) => ({
    ...p,
    label: fromIso(p.date).toLocaleDateString(dateLocale("nl-NL"), { day: "numeric", month: "short" }),
    value: toNumber(p.max_weight_kg),
  }));
  const weighted = rows.filter((r) => r.value !== null).length;
  return (
    <Card
      title={tr("Progressie per oefening")}
      action={
        <select
          value={exercise.exercise_id}
          onChange={(e) => setSelectedId(Number(e.target.value))}
          aria-label={tr("Oefening")}
          className="h-9 w-full rounded-xl border border-ui-line bg-ui-surface px-2 text-sm text-ui-ink sm:w-auto sm:max-w-[60%]"
        >
          {exercises.map((e) => (
            <option key={e.exercise_id} value={e.exercise_id}>
              {e.name} ({e.sessions}×)
            </option>
          ))}
        </select>
      }
    >
      <p className="m-0 mb-2 text-sm text-ui-ink-soft">
        {tp(exercise.sessions, "{n} sessie", "{n} sessies")}
        {exercise.best_weight_kg ? ` · ${tr("beste {weight}", { weight: formatKg(exercise.best_weight_kg) })}` : ""}
      </p>
      {weighted < 2 ? (
        <p className="m-0 py-8 text-center text-sm text-ui-muted">{tr("Log deze oefening vaker met een gewicht om je progressie te zien.")}</p>
      ) : (
        <div className="kit-line h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="label" tick={axisTick} tickLine={false} interval="preserveStartEnd" minTickGap={16} />
              <YAxis tick={axisTick} axisLine={false} tickLine={false} width={40} domain={["auto", "auto"]} />
              <Tooltip
                content={
                  <ChartTooltip<(typeof rows)[number]>
                    render={(r) => ({
                      title: fromIso(r.date).toLocaleDateString(dateLocale("nl-NL"), { day: "numeric", month: "long", year: "numeric" }),
                      lines: [
                        tr("Zwaarste: {weight}", { weight: formatKg(r.max_weight_kg) }),
                        ...(r.volume_kg ? [tr("Volume: {weight}", { weight: formatKg(r.volume_kg) })] : []),
                      ],
                    })}
                  />
                }
              />
              <Line type="linear" dataKey="value" strokeWidth={2} dot={{ r: 4, strokeWidth: 2 }} activeDot={{ r: 5, strokeWidth: 2 }} connectNulls isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

// -- page ----------------------------------------------------------------------------------------

/** One dashboard per activity: km (or sessions) this week/month/year/ever against the same point
 * last time, the trend per month or year, and records; home gym adds the muscle-group split and
 * weight progress per exercise. Every figure comes from GET /trainr/overview. */
export default function TrainrOverviewPage() {
  // The activity lives in the URL (?activiteit=running), so a dashboard can be linked to and the
  // back button works; the last one picked is remembered for a bare /trainr/overzicht.
  const [searchParams, setSearchParams] = useSearchParams();
  const fromUrl = searchParams.get("activiteit");
  const [stored] = useState(readStoredActivity);
  const activity = isActivity(fromUrl) ? fromUrl : stored;
  const [grain, setGrain] = useState<Grain>("month");
  const setActivity = (a: TrainrActivityType) => {
    setSearchParams({ activiteit: a }, { replace: true });
    try {
      localStorage.setItem(STORAGE_KEY, a);
    } catch {
      // Not remembered; the choice still applies now.
    }
  };

  const query = useQuery({ queryKey: ["trainr-overview", activity], queryFn: () => trainrApi.getOverview(activity) });
  const overview = query.data;
  const isDistance = TRAINR_DISTANCE_ACTIVITIES.has(activity);
  const allTime = overview?.tiles.find((t) => t.key === "all");
  const isEmpty = overview !== undefined && (allTime?.current.workouts ?? 0) === 0;
  const points = overview ? (grain === "month" ? overview.monthly : overview.yearly) : [];
  const since = overview?.yearly.length ? String(fromIso(overview.yearly[0].period_start).getFullYear()) : null;
  const amountTitle = isDistance
    ? grain === "month" ? tr("Afstand per maand") : tr("Afstand per jaar")
    : grain === "month" ? tr("Sessies per maand") : tr("Sessies per jaar");
  const trendTitle =
    activity === "running"
      ? grain === "month" ? tr("Gemiddeld tempo per maand") : tr("Gemiddeld tempo per jaar")
      : grain === "month" ? tr("Gemiddelde snelheid per maand") : tr("Gemiddelde snelheid per jaar");

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow />
      <PageTitle>{tr("Overzicht")}</PageTitle>

      <ActivitySelect value={activity} onChange={setActivity} options={ACTIVITY_ORDER} />

      {query.isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-400">{tr("Laden…")}</div>
      ) : query.isError || !overview ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">{tr("Kon het overzicht niet laden.")}{" "}
          <button onClick={() => query.refetch()} className="font-medium text-slate-900 underline">{tr("Opnieuw proberen")}</button>
        </div>
      ) : isEmpty ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-400">{tr("Nog geen gedane {activity}-workouts — log of vink er een af in de Planner.", { activity: tr(TRAINR_ACTIVITY_LABELS[activity]).toLowerCase() })}</div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {overview.tiles.map((tile) => (
              <PeriodTile key={tile.key} tile={tile} isDistance={isDistance} since={since} />
            ))}
          </div>

          <Card
            title={amountTitle}
            action={
              <div className="flex h-9 items-stretch gap-1 rounded-xl border border-ui-border bg-ui-surface p-0.5">
                {(["month", "year"] as const).map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setGrain(g)}
                    aria-pressed={grain === g}
                    className={`whitespace-nowrap rounded-lg px-2.5 text-xs font-semibold ${grain === g ? "bg-ui-brand-soft text-ui-brand-strong" : "text-ui-muted"}`}
                  >
                    {g === "month" ? tr("Maanden") : tr("Jaren")}
                  </button>
                ))}
              </div>
            }
          >
            <AmountChart points={points} grain={grain} isDistance={isDistance} />
          </Card>

          {isDistance && (
            <Card title={trendTitle}>
              <TrendChart points={points} grain={grain} running={activity === "running"} />
            </Card>
          )}

          {!isDistance && overview.exercises.length > 0 && <ExerciseProgressCard key={activity} exercises={overview.exercises} />}

          {!isDistance && overview.muscle_groups.length > 0 && (
            <Card title={tr("Sets per spiergroep")}>
              <MuscleGroupChart overview={overview} />
            </Card>
          )}

          {overview.records.length > 0 && (
            <Card title={tr("Records")}>
              <Records records={overview.records} />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
