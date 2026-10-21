import { useEffect, useState } from "react";

import type { TrainrExerciseDemo } from "../../api/trainrTypes";
import { t } from "../../i18n";

/** How long each photo shows: about the pace of one controlled rep, half down, half up. */
export const DEMO_FRAME_MS = 1000;

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** An exercise's how-to (ADR 0040): its start and end photo flipping like a short GIF, and the
 * steps folded underneath. Tapping the photo steps to the other position by hand; with reduced
 * motion that's the only way it changes. Both photos load up front, so the flip never blinks. */
export default function ExerciseDemo({
  demo,
  className = "",
  showSteps = true,
}: {
  demo: TrainrExerciseDemo;
  className?: string;
  showSteps?: boolean;
}) {
  const frames = demo.image_urls;
  const [frame, setFrame] = useState(0);
  const [loaded, setLoaded] = useState(0);
  const [failed, setFailed] = useState(false);

  const ready = loaded >= frames.length;
  useEffect(() => {
    if (!ready || frames.length < 2 || prefersReducedMotion()) return;
    const id = setInterval(() => setFrame((f) => (f + 1) % frames.length), DEMO_FRAME_MS);
    return () => clearInterval(id);
  }, [ready, frames.length]);

  return (
    <div className={`flex w-full flex-col gap-2 ${className}`}>
      <button
        type="button"
        onClick={() => setFrame((f) => (f + 1) % frames.length)}
        aria-label={t("Voorbeeld: {name}", { name: demo.name })}
        className="relative aspect-[3/2] w-full overflow-hidden rounded-xl border border-ui-border bg-white"
      >
        {!failed &&
          frames.map((url, i) => (
            <img
              key={url}
              src={url}
              alt={i === frame ? (i === 0 ? t("{name}, beginpositie", { name: demo.name }) : t("{name}, eindpositie", { name: demo.name })) : ""}
              onLoad={() => setLoaded((n) => n + 1)}
              onError={() => setFailed(true)}
              className={`absolute inset-0 h-full w-full object-contain ${i === frame ? "opacity-100" : "opacity-0"}`}
            />
          ))}
        {!ready && !failed && (
          <span className="absolute inset-0 flex items-center justify-center text-sm text-ui-muted">{t("Voorbeeld laden…")}</span>
        )}
        {failed && (
          <span className="absolute inset-0 flex items-center justify-center px-4 text-sm text-ui-muted">{t("Het voorbeeld kon niet laden — geen internet?")}</span>
        )}
      </button>
      {showSteps && demo.instructions.length > 0 && (
        <details className="text-left text-sm text-ui-ink-soft">
          <summary className="cursor-pointer font-semibold text-ui-ink">{t("Uitleg (Engels)")}</summary>
          <ol className="m-0 mt-2 flex list-decimal flex-col gap-1 pl-5">
            {demo.instructions.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
