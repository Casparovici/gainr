import { Check, Minus, Plus, X } from "lucide-react";
import { useEffect, useReducer, useState } from "react";

import type { TrainrExerciseDemo, TrainrWorkout, TrainrWorkoutInput } from "../../api/trainrTypes";
import { todayIsoDate } from "../../utils/format";
import { entrySummary, formatDuration, formatKg } from "../../utils/trainr";
import {
  DEFAULT_REST_SECONDS,
  WEIGHT_STEP_KG,
  adjustReps,
  adjustWeight,
  buildSteps,
  doneCount,
  entriesFromResults,
  firstPending,
  pendingResult,
  secondsLeft,
  type RunnerStep,
  type StepResult,
} from "../../utils/trainrRunner";
import { primaryButtonClass, secondaryButtonClass } from "../ui/kit";
import ExerciseDemo from "./ExerciseDemo";
import { t as tr } from "../../i18n";

const REST_EXTENSION_SECONDS = 15;
const TICK_MS = 250;
// Per device: whoever knows the exercises by heart hides the demos once, not every session.
const DEMOS_HIDDEN_KEY = "trainr.runner.demosHidden";

function readDemosHidden(): boolean {
  try {
    return localStorage.getItem(DEMOS_HIDDEN_KEY) === "1";
  } catch {
    return false;
  }
}

function writeDemosHidden(hidden: boolean) {
  try {
    if (hidden) localStorage.setItem(DEMOS_HIDDEN_KEY, "1");
    else localStorage.removeItem(DEMOS_HIDDEN_KEY);
  } catch {
    // Storage blocked: the choice just lasts for this session.
  }
}

type Phase =
  | { kind: "work" }
  | { kind: "hold"; startedAt: number; endsAt: number }
  | { kind: "rest"; endsAt: number }
  | { kind: "summary" };

interface RunnerState {
  steps: RunnerStep[];
  results: StepResult[];
  phase: Phase;
  startedAt: number;
  /** When the current set began (the session start, the end of the last rest, or a skip): a counted
   * set's time is measured from here, so rests never count towards an exercise. */
  workStartedAt: number;
  finishedAt: number | null;
  /** Set when a timer ran out by itself, so the UI can buzz once; a manual skip leaves it alone. */
  expiredAt: number | null;
}

type Action =
  | { type: "adjust"; field: "reps" | "weight"; delta: number }
  | { type: "startHold"; now: number }
  | { type: "complete"; now: number }
  | { type: "tick"; now: number }
  | { type: "addRest"; seconds: number }
  | { type: "skipRest"; now: number }
  | { type: "skipSet"; now: number }
  | { type: "skipExercise"; now: number }
  | { type: "checkOffExercise"; now: number }
  | { type: "finishEarly"; now: number }
  | { type: "resume"; now: number };

function init(workout: TrainrWorkout): RunnerState {
  const steps = buildSteps(workout);
  return {
    steps,
    results: steps.map(pendingResult),
    phase: { kind: "work" },
    startedAt: Date.now(),
    workStartedAt: Date.now(),
    finishedAt: null,
    expiredAt: null,
  };
}

/** Moves on once a set is settled: straight to the summary when nothing is left, otherwise to
 * the rest (after a finished set) or the next set (after a skip). */
function advance(state: RunnerState, results: StepResult[], now: number, withRest: boolean): RunnerState {
  if (firstPending(results) === null) return { ...state, results, phase: { kind: "summary" }, finishedAt: now };
  return {
    ...state,
    results,
    phase: withRest ? { kind: "rest", endsAt: now + DEFAULT_REST_SECONDS * 1000 } : { kind: "work" },
    workStartedAt: now,
  };
}

/** Marks the current set done; a hold records the time actually held. */
function completeCurrent(state: RunnerState, now: number): StepResult[] {
  const index = firstPending(state.results);
  if (index === null) return state.results;
  const step = state.steps[index];
  // A hold stopped early records the time actually held; one that ran out records its target.
  const held = state.phase.kind === "hold" ? Math.round((now - state.phase.startedAt) / 1000) : null;
  const seconds = step.kind === "hold" && held !== null && step.targetSeconds ? Math.min(held, step.targetSeconds) : null;
  const active = step.kind === "hold" ? null : Math.max(0, Math.round((now - state.workStartedAt) / 1000));
  return state.results.map((r, i) => (i === index ? { ...r, status: "done", seconds: seconds ?? r.seconds, activeSeconds: active } : r));
}

function settleRestOfExercise(state: RunnerState, status: "done" | "skipped"): StepResult[] {
  const index = firstPending(state.results);
  if (index === null) return state.results;
  const entryIndex = state.steps[index].entryIndex;
  return state.results.map((r, i) => (r.status === "pending" && state.steps[i].entryIndex === entryIndex ? { ...r, status } : r));
}

function reducer(state: RunnerState, action: Action): RunnerState {
  switch (action.type) {
    case "adjust": {
      const index = firstPending(state.results);
      if (index === null) return state;
      return {
        ...state,
        results: state.results.map((r, i) =>
          i !== index
            ? r
            : action.field === "reps"
              ? { ...r, reps: adjustReps(r.reps, action.delta) }
              : { ...r, weightKg: adjustWeight(r.weightKg, action.delta) },
        ),
      };
    }
    case "startHold": {
      const index = firstPending(state.results);
      const seconds = index === null ? null : state.steps[index].targetSeconds;
      if (!seconds) return state;
      return { ...state, phase: { kind: "hold", startedAt: action.now, endsAt: action.now + seconds * 1000 } };
    }
    case "complete":
      return advance(state, completeCurrent(state, action.now), action.now, true);
    case "tick": {
      if (state.phase.kind === "hold" && action.now >= state.phase.endsAt) {
        return { ...advance(state, completeCurrent(state, action.now), action.now, true), expiredAt: action.now };
      }
      if (state.phase.kind === "rest" && action.now >= state.phase.endsAt) {
        return { ...state, phase: { kind: "work" }, workStartedAt: state.phase.endsAt, expiredAt: action.now };
      }
      return state;
    }
    case "addRest":
      return state.phase.kind === "rest" ? { ...state, phase: { kind: "rest", endsAt: state.phase.endsAt + action.seconds * 1000 } } : state;
    case "skipRest":
      return state.phase.kind === "rest" ? { ...state, phase: { kind: "work" }, workStartedAt: action.now } : state;
    case "skipSet": {
      const index = firstPending(state.results);
      if (index === null) return state;
      return advance(state, state.results.map((r, i) => (i === index ? { ...r, status: "skipped" } : r)), action.now, false);
    }
    case "skipExercise":
      return advance(state, settleRestOfExercise(state, "skipped"), action.now, false);
    case "checkOffExercise": {
      // The set in progress keeps its measured time; the ones ticked off with it have none.
      const withCurrent = { ...state, results: completeCurrent(state, action.now) };
      return advance(state, settleRestOfExercise(withCurrent, "done"), action.now, true);
    }
    case "finishEarly":
      return { ...state, phase: { kind: "summary" }, finishedAt: action.now };
    case "resume":
      return firstPending(state.results) === null ? state : { ...state, phase: { kind: "work" }, workStartedAt: action.now, finishedAt: null };
  }
}

function Stepper({
  label,
  value,
  onMinus,
  onPlus,
}: {
  label: string;
  value: string;
  onMinus: () => void;
  onPlus: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-xs font-medium uppercase tracking-wide text-ui-muted">{label}</span>
      <div className="flex items-center gap-3">
        <button type="button" onClick={onMinus} aria-label={tr("{label} omlaag", { label })} className="flex h-12 w-12 items-center justify-center rounded-full border border-ui-border bg-ui-surface text-ui-ink">
          <Minus className="h-5 w-5" />
        </button>
        <span className="min-w-[4.5rem] text-center text-3xl font-bold tabular-nums text-ui-ink">{value}</span>
        <button type="button" onClick={onPlus} aria-label={tr("{label} omhoog", { label })} className="flex h-12 w-12 items-center justify-center rounded-full border border-ui-border bg-ui-surface text-ui-ink">
          <Plus className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}

function nextUp(steps: RunnerStep[], index: number): string {
  const next = steps[index + 1];
  return next
    ? tr("Hierna: {exercise} · set {setNumber}/{setCount}", { exercise: next.exerciseName, setNumber: next.setNumber, setCount: next.setCount })
    : tr("Laatste set");
}

/** Guided execution of a planned gym session: one set at a time with its target, a countdown for
 * timed holds and for the rest between sets, a tick-off per set (or per exercise), and the actual
 * reps and weight written back to the workout when it's finished. The planned numbers are the
 * starting point, so a session that goes to plan is a tap per set. An exercise with a linked demo
 * shows it while you do the set, and the next one's during the rest before it (ADR 0040). */
export default function WorkoutRunner({
  workout,
  demos,
  isSaving,
  error,
  onClose,
  onFinish,
}: {
  workout: TrainrWorkout;
  /** By exercise id; an exercise missing here (unlinked, or the list still loading) shows none. */
  demos?: ReadonlyMap<number, TrainrExerciseDemo>;
  isSaving: boolean;
  error?: string | null;
  onClose: () => void;
  onFinish: (input: TrainrWorkoutInput) => void;
}) {
  const [state, dispatch] = useReducer(reducer, workout, init);
  const [now, setNow] = useState(state.startedAt);
  const [demosHidden, setDemosHidden] = useState(readDemosHidden);

  const running = state.phase.kind !== "summary";
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      const t = Date.now();
      setNow(t);
      dispatch({ type: "tick", now: t });
    }, TICK_MS);
    return () => clearInterval(id);
  }, [running]);

  // A timer that ran out by itself buzzes once, where the device can; elsewhere it's silent.
  useEffect(() => {
    if (state.expiredAt !== null) navigator.vibrate?.(200);
  }, [state.expiredAt]);

  // Keep the screen awake between sets -- a phone that locks mid-session loses the countdown view.
  useEffect(() => {
    let lock: WakeLockSentinel | null = null;
    let cancelled = false;
    navigator.wakeLock
      ?.request("screen")
      .then((sentinel) => {
        if (cancelled) void sentinel.release();
        else lock = sentinel;
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      void lock?.release();
    };
  }, []);

  const { steps, results, phase } = state;
  const index = firstPending(results);
  const step = index === null ? null : steps[index];
  const result = index === null ? null : results[index];
  const settled = results.filter((r) => r.status !== "pending").length;
  const done = doneCount(results);
  const elapsed = Math.max(0, Math.floor(((state.finishedAt ?? now) - state.startedAt) / 1000));
  const entryName = (entryIndex: number) => workout.entries[entryIndex].exercise_name;
  const demo = step ? demos?.get(step.exerciseId) : undefined;

  function toggleDemos() {
    writeDemosHidden(!demosHidden);
    setDemosHidden(!demosHidden);
  }

  const demoToggle = demo && (
    <button type="button" onClick={toggleDemos} className="text-xs font-semibold text-ui-brand-strong">
      {demosHidden ? tr("Voorbeeld tonen") : tr("Voorbeeld verbergen")}
    </button>
  );

  function close() {
    if (settled === 0 || confirm(tr("Stoppen zonder op te slaan? Wat je al hebt afgevinkt gaat verloren en de workout blijft gepland."))) onClose();
  }

  function finish() {
    const entries = entriesFromResults(workout, steps, results);
    onFinish({
      activity_type: workout.activity_type,
      date: todayIsoDate(),
      is_completed: true,
      duration_seconds: Math.max(elapsed, 1),
      distance_km: null,
      max_speed_kmh: null,
      calories_kcal: null,
      avg_heart_rate_bpm: null,
      max_heart_rate_bpm: null,
      notes: workout.notes,
      entries,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ui-bg" role="dialog" aria-modal="true" aria-label={tr("Workout uitvoeren")}>
      <header className="flex items-center justify-between gap-2 border-b border-ui-border bg-ui-surface px-4 py-3">
        <button type="button" onClick={close} aria-label={tr("Stoppen")} className="flex h-10 w-10 items-center justify-center rounded-full text-ui-muted hover:text-ui-ink">
          <X className="h-5 w-5" />
        </button>
        <div className="flex flex-col items-center">
          <span className="text-sm font-semibold text-ui-ink">
            {tr("{done} van {total} sets", { done: settled, total: steps.length })}
          </span>
          <span role="timer" aria-label={tr("Verstreken tijd")} className="text-xs tabular-nums text-ui-muted">
            {formatDuration(elapsed) || "0:00"}
          </span>
        </div>
        {phase.kind !== "summary" ? (
          <button type="button" onClick={() => dispatch({ type: "finishEarly", now: Date.now() })} disabled={done === 0} className="px-2 text-sm font-semibold text-ui-brand-strong disabled:opacity-40">{tr("Afronden")}</button>
        ) : (
          <span className="w-16" />
        )}
      </header>
      <div className="h-1 bg-ui-tile" aria-hidden>
        <div className="h-full bg-ui-brand transition-all" style={{ width: `${steps.length === 0 ? 0 : (settled / steps.length) * 100}%` }} />
      </div>

      <main className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4 py-6">
        {steps.length === 0 && (
          <p className="text-center text-sm text-ui-muted">{tr("Deze workout heeft nog geen oefeningen. Voeg ze eerst toe in de planner.")}</p>
        )}

        {phase.kind === "rest" && step && index !== null && (
          <section className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
            <span className="text-sm font-semibold uppercase tracking-wide text-ui-muted">{tr("Rust")}</span>
            <span role="timer" aria-label={tr("Rust over")} className="text-7xl font-bold tabular-nums text-ui-ink">
              {formatDuration(secondsLeft(phase.endsAt, now)) || "0:00"}
            </span>
            <p className="text-base text-ui-ink-soft">{tr("Volgende:")}{" "}<strong>{step.exerciseName}</strong>{" "}{tr("· set {setNumber}/{setCount}", { setNumber: step.setNumber, setCount: step.setCount })}</p>
            {demo && !demosHidden && <ExerciseDemo key={demo.id} demo={demo} showSteps={false} className="max-w-[16rem]" />}
            <div className="flex gap-2">
              <button type="button" onClick={() => dispatch({ type: "addRest", seconds: REST_EXTENSION_SECONDS })} className={secondaryButtonClass}>
                {tr("+{n} s", { n: REST_EXTENSION_SECONDS })}
              </button>
              <button type="button" onClick={() => dispatch({ type: "skipRest", now: Date.now() })} className={primaryButtonClass}>{tr("Rust overslaan")}</button>
            </div>
          </section>
        )}

        {(phase.kind === "work" || phase.kind === "hold") && step && result && index !== null && (
          <section className="flex flex-col items-center gap-5 text-center">
            <div>
              <h2 className="text-2xl font-bold text-ui-ink">{step.exerciseName}</h2>
              <p className="mt-1 text-sm text-ui-muted">{tr("Set {setNumber} van {setCount}", { setNumber: step.setNumber, setCount: step.setCount })}{step.kind !== "hold" && (
                  <>
                    {" · "}
                    <span role="timer" aria-label={tr("Duur van deze set")} className="tabular-nums">
                      {formatDuration(Math.max(0, Math.floor((now - state.workStartedAt) / 1000))) || "0:00"}
                    </span>
                  </>
                )}
              </p>
            </div>

            {demo && !demosHidden && <ExerciseDemo key={demo.id} demo={demo} className="max-w-xs" />}
            {demoToggle}

            {step.kind === "hold" ? (
              <>
                <span role="timer" aria-label={tr("Tijd over")} className="text-7xl font-bold tabular-nums text-ui-ink">
                  {formatDuration(phase.kind === "hold" ? secondsLeft(phase.endsAt, now) : step.targetSeconds) || "0:00"}
                </span>
                {phase.kind === "work" ? (
                  <button type="button" onClick={() => dispatch({ type: "startHold", now: Date.now() })} className={`${primaryButtonClass} h-14 w-full max-w-xs text-lg`}>{tr("Start")}</button>
                ) : (
                  <button type="button" onClick={() => dispatch({ type: "complete", now: Date.now() })} className={`${primaryButtonClass} h-14 w-full max-w-xs text-lg`}>{tr("Klaar")}</button>
                )}
              </>
            ) : (
              <>
                {step.kind === "reps" && (
                  <div className="flex flex-wrap justify-center gap-6">
                    <Stepper
                      label={tr("Herhalingen")}
                      value={String(result.reps ?? 0)}
                      onMinus={() => dispatch({ type: "adjust", field: "reps", delta: -1 })}
                      onPlus={() => dispatch({ type: "adjust", field: "reps", delta: 1 })}
                    />
                    {step.targetWeightKg !== null && (
                      <Stepper
                        label={tr("Gewicht")}
                        value={formatKg(String(result.weightKg ?? 0))}
                        onMinus={() => dispatch({ type: "adjust", field: "weight", delta: -WEIGHT_STEP_KG })}
                        onPlus={() => dispatch({ type: "adjust", field: "weight", delta: WEIGHT_STEP_KG })}
                      />
                    )}
                  </div>
                )}
                <button type="button" onClick={() => dispatch({ type: "complete", now: Date.now() })} className={`${primaryButtonClass} h-14 w-full max-w-xs text-lg`}>
                  <Check className="h-5 w-5" strokeWidth={3} />{tr("Set klaar")}</button>
              </>
            )}

            <p className="text-sm text-ui-muted">{nextUp(steps, index)}</p>

            <div className="flex flex-wrap justify-center gap-2">
              <button type="button" onClick={() => dispatch({ type: "skipSet", now: Date.now() })} className={secondaryButtonClass}>{tr("Set overslaan")}</button>
              <button type="button" onClick={() => dispatch({ type: "checkOffExercise", now: Date.now() })} className={secondaryButtonClass}>{tr("Oefening afvinken")}</button>
              <button
                type="button"
                onClick={() => {
                  if (confirm(tr("{exercise} overslaan? De resterende sets tellen niet mee.", { exercise: step.exerciseName }))) dispatch({ type: "skipExercise", now: Date.now() });
                }}
                className={secondaryButtonClass}
              >{tr("Oefening overslaan")}</button>
            </div>
          </section>
        )}

        {phase.kind === "summary" && (
          <section className="flex flex-col gap-4">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-ui-ink">{done === 0 ? tr("Niets afgevinkt") : tr("Goed gedaan")}</h2>
              <p className="mt-1 text-sm text-ui-muted">
                {tr("{done} van {total} sets · {time}", { done, total: steps.length, time: formatDuration(elapsed) || "0:00" })}
              </p>
            </div>
            <ul className="flex flex-col gap-2">
              {entriesFromResults(workout, steps, results).map((e, i) => (
                <li key={i} className="flex items-center justify-between gap-3 rounded-xl border border-ui-border bg-ui-surface px-4 py-3 text-sm">
                  <span className="truncate font-semibold text-ui-ink">{workout.entries.find((w) => w.exercise_id === e.exercise_id)?.exercise_name}</span>
                  <span className="shrink-0 text-ui-muted">{entrySummary({ sets: e.sets, reps: e.reps, weight_kg: e.weight_kg, duration_seconds: e.duration_seconds })}</span>
                </li>
              ))}
            </ul>
            {error && <p className="text-center text-sm text-red-600">{error}</p>}
            <div className="flex flex-col gap-2">
              <button type="button" onClick={finish} disabled={isSaving || done === 0} className={`${primaryButtonClass} w-full`}>
                {isSaving ? tr("Opslaan…") : tr("Opslaan als gedaan")}
              </button>
              {index !== null && (
                <button type="button" onClick={() => dispatch({ type: "resume", now: Date.now() })} disabled={isSaving} className={`${secondaryButtonClass} w-full`}>{tr("Verder met de workout")}</button>
              )}
            </div>
          </section>
        )}
      </main>

      {steps.length > 0 && phase.kind !== "summary" && (
        <footer className="border-t border-ui-border bg-ui-surface px-4 py-3">
          <ul className="flex gap-2 overflow-x-auto" aria-label={tr("Oefeningen")}>
            {workout.entries.map((_, entryIndex) => {
              const mine = steps.map((s, i) => ({ s, r: results[i] })).filter(({ s }) => s.entryIndex === entryIndex);
              const finished = mine.every(({ r }) => r.status !== "pending");
              const current = step?.entryIndex === entryIndex;
              return (
                <li
                  key={entryIndex}
                  className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold ${
                    current ? "border-ui-brand bg-ui-brand-soft text-ui-brand-strong" : finished ? "border-ui-border text-ui-muted" : "border-ui-border text-ui-ink-soft"
                  }`}
                >
                  {finished && <Check className="h-3.5 w-3.5" strokeWidth={3} aria-label={tr("klaar")} />}
                  {entryName(entryIndex)} · {mine.filter(({ r }) => r.status === "done").length}/{mine.length}
                </li>
              );
            })}
          </ul>
        </footer>
      )}
    </div>
  );
}
