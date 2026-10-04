import { Info } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

/** The ⓘ button that folds a section's explanation in and out -- a native button, so it's
 * reachable by keyboard and announces whether the text is showing. */
export function InfoButton({
  label,
  open,
  onToggle,
  controls,
  className = "text-on-surface-variant hover:text-on-surface",
}: {
  /** What the explanation is about, e.g. "Virtual pot inside" -- read out as "About …". */
  label: string;
  open: boolean;
  onToggle: () => void;
  controls: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-label={`About ${label}`}
      aria-expanded={open}
      aria-controls={controls}
      onClick={onToggle}
      className={`-m-1 inline-flex shrink-0 items-center justify-center rounded-full p-1 ${className}`}
    >
      <Info className="h-4 w-4" strokeWidth={2} aria-hidden />
    </button>
  );
}

/** A title with its explanation behind an ⓘ next to it, instead of a paragraph always on screen.
 * The title row and the explanation are returned as siblings, so they sit in the caller's own
 * column layout; the explanation opens right under the title. */
export default function InfoHeading({
  title,
  label,
  children,
  textClassName = "text-xs text-on-surface-variant",
  buttonClassName,
}: {
  title: ReactNode;
  label: string;
  children: ReactNode;
  textClassName?: string;
  buttonClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <>
      <div className="flex min-w-0 items-center gap-1.5">
        {title}
        <InfoButton label={label} open={open} onToggle={() => setOpen((v) => !v)} controls={id} className={buttonClassName} />
      </div>
      <p id={id} hidden={!open} className={textClassName}>
        {children}
      </p>
    </>
  );
}
