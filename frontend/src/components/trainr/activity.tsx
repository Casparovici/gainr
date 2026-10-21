import { Bike, Dumbbell, Footprints, Goal, Volleyball, type LucideIcon } from "lucide-react";

import type { TrainrActivityType } from "../../api/trainrTypes";

export const ACTIVITY_ICONS: Record<TrainrActivityType, LucideIcon> = {
  home_gym: Dumbbell,
  running: Footprints,
  cycling: Bike,
  football: Goal,
  padel: Volleyball,
};

export function ActivityIcon({ type, className = "h-4 w-4" }: { type: TrainrActivityType; className?: string }) {
  const Icon = ACTIVITY_ICONS[type];
  return <Icon className={className} strokeWidth={2} aria-hidden />;
}
