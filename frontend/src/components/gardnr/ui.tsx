/* gardnr's own pieces of its redesign (claude.ai design "gardnr · Tuinen", Sept 2026): garden
 * status chips, due-state and task counting, the zone palette, and the mini map on garden cards.
 * The generic page kit (icons, buttons, top row, edit bar) lives in components/ui/kit.tsx and is
 * re-exported here, so gardnr imports everything from one place. */
import type { GardenAreaDetail, GardenPlantListRow, GardenPlantMarker, GardenZone } from "../../api/gardnrTypes";
import { todayLocalISO } from "../../utils/gardnr";
import { StatusChip, type DueState } from "../ui/kit";

export * from "../ui/kit";
export { ModuleTopRow as GardnrTopRow } from "../ui/kit";

// -- Status chips ---------------------------------------------------------------------------------

/** A garden's chips: what's overdue and what's due today, or that it's all on schedule. */
export function AreaStatusChips({ late, today }: { late: number; today: number }) {
  if (late === 0 && today === 0) return <StatusChip kind="ok">Op schema</StatusChip>;
  return (
    <>
      {late > 0 && <StatusChip kind="late">{late} te laat</StatusChip>}
      {today > 0 && <StatusChip kind="today">{today} vandaag</StatusChip>}
    </>
  );
}

// -- Due state ----------------------------------------------------------------------------------

/** Whether a plant's soonest care action is overdue or due today -- what colours its marker's
 * badge and its dot on a mini map. */
export function plantDueState(plant: Pick<GardenPlantMarker, "next_action">, today: string = todayLocalISO()): DueState | null {
  const next = plant.next_action;
  if (!next) return null;
  if (next.is_overdue || next.date < today) return "late";
  if (next.date === today) return "today";
  return null;
}

export interface TaskCounts {
  late: number;
  today: number;
}

/** Overdue and due-today care tasks per garden, and in total -- every scheduled action counts,
 * not just each plant's soonest, so "2 te laat" matches what Vandaag lists. */
export function taskCounts(plants: GardenPlantListRow[], today: string = todayLocalISO()) {
  const byArea = new Map<number, TaskCounts>();
  const total: TaskCounts = { late: 0, today: 0 };
  for (const plant of plants) {
    if (plant.is_archived) continue;
    for (const action of plant.scheduled_actions) {
      const kind = action.is_overdue || action.date < today ? "late" : action.date === today ? "today" : null;
      if (!kind) continue;
      const counts = byArea.get(plant.area_id) ?? { late: 0, today: 0 };
      counts[kind] += 1;
      total[kind] += 1;
      byArea.set(plant.area_id, counts);
    }
  }
  return { byArea, total };
}

// -- Zones ----------------------------------------------------------------------------------------

/** The design's six zone colours, in its order. */
export const ZONE_PALETTE: { color: string; label: string }[] = [
  { color: "#CFE3B8", label: "gazon" },
  { color: "#E6D6BF", label: "border" },
  { color: "#D9C5A2", label: "aarde" },
  { color: "#DAD6CC", label: "tegels" },
  { color: "#BCD8DF", label: "water" },
  { color: "#EBCFD8", label: "bloemen" },
];
export const DEFAULT_ZONE_COLOR = ZONE_PALETTE[0].color;

/** A zone's fill: the design's pastels as-is; any other colour (zones drawn before the redesign,
 * in slate greys) is mostly blended into the map's ground (30% colour) so it doesn't sit on the page as a
 * heavy block. Picking a swatch in edit mode gives it a design colour. */
export function zoneFill(color: string): string {
  const isPalette = ZONE_PALETTE.some((p) => p.color.toLowerCase() === color.toLowerCase());
  return isPalette ? color : `color-mix(in srgb, ${color} 30%, rgb(var(--ui-field-rgb)))`;
}

export function zoneRadius(zone: Pick<GardenZone, "shape">, px: number): string {
  return zone.shape === "circle" ? "50%" : `${px}px`;
}

/** The zone a point (percent coordinates) falls in -- the topmost when zones overlap. */
export function zoneAt(zones: GardenZone[], x: number, y: number): GardenZone | undefined {
  for (let i = zones.length - 1; i >= 0; i--) {
    const z = zones[i];
    const zx = Number(z.x), zy = Number(z.y), zw = Number(z.width), zh = Number(z.height);
    if (z.shape === "circle") {
      const dx = (x - (zx + zw / 2)) / (zw / 2);
      const dy = (y - (zy + zh / 2)) / (zh / 2);
      if (dx * dx + dy * dy <= 1) return z;
    } else if (x >= zx && x <= zx + zw && y >= zy && y <= zy + zh) {
      return z;
    }
  }
  return undefined;
}

// -- Mini map --------------------------------------------------------------------------------------

const DOT_BORDER: Record<DueState | "ok", string> = {
  late: "border-ui-late",
  today: "border-ui-today-dot",
  ok: "border-ui-brand",
};

/** A garden's map in miniature, for the garden cards: its zones and a dot per placed plant,
 * coloured by what's due. The garden's own 4:3 map is fitted into the box (the design's box is
 * slightly taller than 4:3; the ground colour fills the difference), so what you drew keeps its
 * proportions. */
export function MiniMap({ detail, width, height }: { detail: GardenAreaDetail | undefined; width: number; height: number }) {
  const mapW = Math.min(width, (height * 4) / 3);
  const mapH = (mapW * 3) / 4;
  return (
    <div className="relative shrink-0 overflow-hidden rounded-[14px] bg-ui-field" style={{ width, height }} aria-hidden>
      {detail && (
        <div className="absolute" style={{ left: (width - mapW) / 2, top: (height - mapH) / 2, width: mapW, height: mapH }}>
          {detail.zones.map((z) => (
            <div
              key={z.id}
              className="absolute"
              style={{
                left: `${z.x}%`,
                top: `${z.y}%`,
                width: `${z.width}%`,
                height: `${z.height}%`,
                background: zoneFill(z.color),
                borderRadius: zoneRadius(z, 3),
              }}
            />
          ))}
          {detail.plants
            .filter((p) => p.x !== null && p.y !== null)
            .map((p) => (
              <span
                key={p.id}
                className={`absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-white ${DOT_BORDER[plantDueState(p) ?? "ok"]}`}
                style={{ left: `${p.x}%`, top: `${p.y}%` }}
              />
            ))}
        </div>
      )}
    </div>
  );
}
