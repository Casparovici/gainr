import { Minus, Plus } from "lucide-react";

/** A +/- pair around a number -- every adjustment is a server round-trip via `onAdjust(delta)`,
 * never a locally-typed draft value. Count and minimum both use this: typing into a text field
 * and committing on blur turned out to be the fragile part (see docs/adr/0015's third addendum
 * -- a blur-timing race could drop an in-progress edit before it was ever sent), while the
 * count's own +/- buttons, which never held draft state, had been reliably persisting the whole
 * time. */
export default function Stepper({
  value,
  onAdjust,
  decrementLabel,
  incrementLabel,
}: {
  value: number;
  onAdjust: (delta: number) => void;
  decrementLabel: string;
  incrementLabel: string;
}) {
  return (
    <span className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => onAdjust(-1)}
        disabled={value === 0}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-ui-line bg-ui-surface text-ui-ink-soft hover:bg-ui-tile disabled:opacity-30"
        title={decrementLabel}
        aria-label={decrementLabel}
      >
        <Minus className="h-3.5 w-3.5" strokeWidth={2} />
      </button>
      <span className="w-5 text-center text-[15px] font-semibold tabular-nums text-ui-ink">{value}</span>
      <button
        type="button"
        onClick={() => onAdjust(1)}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-ui-line bg-ui-surface text-ui-ink-soft hover:bg-ui-tile"
        title={incrementLabel}
        aria-label={incrementLabel}
      >
        <Plus className="h-3.5 w-3.5" strokeWidth={2} />
      </button>
    </span>
  );
}
