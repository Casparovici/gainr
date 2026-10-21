import { msg } from "../i18n";

export type GardenPlantType = "plant" | "tree" | "shrub" | "other";

export const GARDEN_PLANT_TYPES: GardenPlantType[] = ["plant", "tree", "shrub", "other"];

export const GARDEN_PLANT_TYPE_LABELS: Record<GardenPlantType, string> = {
  plant: msg("Plant"),
  tree: msg("Boom"),
  shrub: msg("Struik"),
  other: msg("Overig"),
};

export type GardenActionType = "water" | "prune" | "trim" | "fertilize" | "harvest" | "pest_control" | "other";

export const GARDEN_ACTION_TYPES: GardenActionType[] = ["water", "prune", "trim", "fertilize", "harvest", "pest_control", "other"];

export const GARDEN_ACTION_LABELS: Record<GardenActionType, string> = {
  water: msg("Water geven"),
  prune: msg("Snoeien"),
  trim: msg("Bijsnoeien"),
  fertilize: msg("Bemesten"),
  harvest: msg("Oogsten"),
  pest_control: msg("Ongediertebestrijding"),
  other: msg("Overig"),
};

export type GardenScheduleFrequency = "daily" | "weekly" | "monthly" | "yearly";

export const GARDEN_SCHEDULE_FREQUENCIES: GardenScheduleFrequency[] = ["daily", "weekly", "monthly", "yearly"];

export const GARDEN_FREQUENCY_UNIT_LABELS: Record<GardenScheduleFrequency, string> = {
  daily: msg("dag(en)"),
  weekly: msg("week(en)"),
  monthly: msg("maand(en)"),
  yearly: msg("jaar/jaren"),
};

export type GardenPlantStatus = "thriving" | "struggling" | "dead";

export const GARDEN_PLANT_STATUSES: GardenPlantStatus[] = ["thriving", "struggling", "dead"];

export const GARDEN_PLANT_STATUS_LABELS: Record<GardenPlantStatus, string> = {
  thriving: msg("Gezond"),
  struggling: msg("Worstelt"),
  dead: msg("Dood"),
};

// emerald/amber/red, the same traffic-light meaning listr's inventory status dots use.
export const GARDEN_PLANT_STATUS_DOT_CLASS: Record<GardenPlantStatus, string> = {
  thriving: "bg-emerald-500",
  struggling: "bg-amber-500",
  dead: "bg-red-500",
};

export type GardenZoneShape = "rect" | "circle";

export const GARDEN_ZONE_SHAPE_LABELS: Record<GardenZoneShape, string> = {
  rect: msg("Rechthoek"),
  circle: msg("Cirkel"),
};

export type GardenPlantIcon = "sprout" | "tree_deciduous" | "tree_pine" | "trees" | "leaf" | "leafy_green" | "flower" | "flower2";

export const GARDEN_PLANT_ICONS: GardenPlantIcon[] = [
  "sprout",
  "tree_deciduous",
  "tree_pine",
  "trees",
  "leaf",
  "leafy_green",
  "flower",
  "flower2",
];

export const GARDEN_PLANT_ICON_LABELS: Record<GardenPlantIcon, string> = {
  sprout: msg("Kiem"),
  tree_deciduous: msg("Loofboom"),
  tree_pine: msg("Naaldboom"),
  trees: msg("Bomen"),
  leaf: msg("Blad"),
  leafy_green: msg("Groen blad"),
  flower: msg("Bloem"),
  flower2: msg("Bloem (rond)"),
};

export interface GardenArea {
  id: number;
  name: string;
  sort_order: number;
  plant_count: number;
  overdue_count: number;
}

export interface GardenZone {
  id: number;
  area_id: number;
  name: string;
  shape: GardenZoneShape;
  x: string;
  y: string;
  width: string;
  height: string;
  color: string;
  sort_order: number;
}

export interface GardenActionSummary {
  /** Which schedule this occurrence comes from; null for a past log (`last_action`). */
  schedule_id: number | null;
  action_type: GardenActionType;
  custom_label: string | null;
  date: string;
  is_overdue: boolean;
}

export interface GardenPlantMarker {
  id: number;
  name: string;
  species: string | null;
  type: GardenPlantType;
  x: string | null;
  y: string | null;
  marker_shape: GardenZoneShape;
  marker_width: string;
  marker_height: string;
  icon: GardenPlantIcon | null;
  status: GardenPlantStatus;
  last_action: GardenActionSummary | null;
  next_action: GardenActionSummary | null;
}

export interface GardenAreaDetail {
  area: GardenArea;
  zones: GardenZone[];
  plants: GardenPlantMarker[];
}

export interface GardenPlant {
  id: number;
  area_id: number;
  name: string;
  species: string | null;
  type: GardenPlantType;
  planted_date: string | null;
  notes: string | null;
  x: string | null;
  y: string | null;
  marker_shape: GardenZoneShape;
  marker_width: string;
  marker_height: string;
  icon: GardenPlantIcon | null;
  status: GardenPlantStatus;
  is_archived: boolean;
}

export interface GardenPlantListRow {
  id: number;
  area_id: number;
  area_name: string;
  name: string;
  species: string | null;
  type: GardenPlantType;
  status: GardenPlantStatus;
  is_archived: boolean;
  next_action: GardenActionSummary | null;
  is_overdue: boolean;
  /** Every active schedule's next occurrence, soonest first; `next_action` is its first entry. */
  scheduled_actions: GardenActionSummary[];
}

export interface GardenCareLog {
  id: number;
  plant_id: number;
  action_type: GardenActionType;
  custom_label: string | null;
  performed_on: string;
  notes: string | null;
  has_photo: boolean;
}

export interface GardenCareSchedule {
  id: number;
  plant_id: number;
  action_type: GardenActionType;
  custom_label: string | null;
  interval_value: number;
  frequency: GardenScheduleFrequency;
  is_active: boolean;
  /** The first occurrence, if one was picked; null means one interval after the schedule was made. */
  start_date: string | null;
  notes: string | null;
  next_due: string;
  is_overdue: boolean;
}

export interface GardenPlantDetail {
  plant: GardenPlant;
  care_logs: GardenCareLog[];
  care_schedules: GardenCareSchedule[];
}
