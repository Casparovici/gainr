import { Play } from "lucide-react";

import type { TrainrWorkout } from "../../api/trainrTypes";
import { workoutHeadline } from "../../utils/trainr";
import { IconCheck } from "../ui/kit";
import { ActivityIcon } from "./activity";
import { t } from "../../i18n";

/** One workout in a planner day: tap the label to open it, tap the circle to tick it off (or
 * back to planned), tap the play button (when it can be run) to do it step by step. All of them
 * stop the click from reaching the day cell, which would start a new workout. */
export default function WorkoutChip({
  workout,
  onOpen,
  onToggle,
  onStart,
}: {
  workout: TrainrWorkout;
  onOpen: () => void;
  onToggle: () => void;
  onStart?: () => void;
}) {
  const headline = workoutHeadline(workout);
  const toggleLabel = workout.is_completed ? t("{workout}: gedaan", { workout: headline }) : t("{workout}: markeer als gedaan", { workout: headline });
  return (
    <div className="flex min-w-0 items-center justify-between gap-1">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onOpen();
        }}
        className={`flex min-w-0 items-center gap-1.5 text-left text-[15px] font-semibold hover:underline sm:text-xs ${
          workout.is_completed ? "text-ui-ink" : "text-ui-ink-soft"
        }`}
        title={headline}
      >
        <ActivityIcon type={workout.activity_type} className="h-4 w-4 shrink-0 text-ui-brand sm:h-3.5 sm:w-3.5" />
        <span className="truncate">{headline}</span>
      </button>
      <div className="flex shrink-0 items-center gap-1">
        {onStart && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onStart();
            }}
            title={t("Start workout")}
            aria-label={t("{workout}: start", { workout: headline })}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ui-brand-soft text-ui-brand-strong sm:h-6 sm:w-6"
          >
            <Play className="h-3.5 w-3.5" fill="currentColor" aria-hidden />
          </button>
        )}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onToggle();
          }}
          title={workout.is_completed ? t("Gedaan") : t("Markeer als gedaan")}
          aria-label={toggleLabel}
          aria-pressed={workout.is_completed}
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border sm:h-6 sm:w-6 ${
            workout.is_completed ? "border-ui-brand bg-ui-brand text-white" : "border-ui-line text-ui-faint hover:text-ui-muted"
          }`}
        >
          <IconCheck size={14} strokeWidth={3} />
        </button>
      </div>
    </div>
  );
}
