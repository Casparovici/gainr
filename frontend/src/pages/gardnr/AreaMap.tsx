import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState, useLayoutEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { gardnrApi } from "../../api/gardnrClient";
import type { GardenActionSummary, GardenPlantMarker, GardenZone, GardenAreaDetail } from "../../api/gardnrTypes";
import NewPlantDialog, { type NewPlantInput } from "../../components/gardnr/NewPlantDialog";
import PlantDetailPanel from "../../components/gardnr/PlantDetailPanel";
import { PLANT_ICON_COMPONENTS, resolvePlantIcon } from "../../components/gardnr/plantIcons";
import {
  AreaStatusChips,
  DEFAULT_ZONE_COLOR,
  EditBar,
  GardnrTopRow,
  IconAlert,
  IconCheck,
  IconChevronLeft,
  IconDroplet,
  IconPencil,
  IconSprout,
  IconSquare,
  IconTag,
  IconTrash,
  PageTitle,
  ZONE_PALETTE,
  inputClass,
  plantDueState,
  primaryButtonClass,
  secondaryButtonClass,
  taskCounts,
  zoneAt,
  zoneFill,
  zoneRadius,
} from "../../components/gardnr/ui";
import { actionLabel, dueText, gardnrDate, todayLocalISO } from "../../utils/gardnr";
import { msg, t as tr } from "../../i18n";

// A finger jitters more than a mouse, so a touch has to travel further before a tap becomes a move.
const DRAG_THRESHOLD_PX = { mouse: 4, touch: 10 };
// The design's marker is a 44px circle -- also a comfortable finger target -- and a selected one
// grows to 52px. A marker given a larger size on a wide map keeps its percent size.
const MARKER_PX = 44;
const SELECTED_MARKER_PX = 52;
const SHOW_NAMES_KEY = "gardnr.showNames";
// Same bounds the old number fields enforced: a bed can span the whole map, a plant marker can't.
const ZONE_SIZE_RANGE = { min: 2, max: 100 };
const MARKER_SIZE_RANGE = { min: 2, max: 30 };
const NEW_ZONE = { name: msg("Nieuw vak"), shape: "rect" as const, color: DEFAULT_ZONE_COLOR, x: "35", y: "35", width: "30", height: "20" };

function clampPercent(v: number): number {
  return Math.min(100, Math.max(0, v));
}

function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}

// Real touchscreens don't fire mouse events, so every drag-start site fires both onMouseDown and
// onTouchStart with the same handler -- this pulls the one thing they differ on (where the
// client coordinates live) into one place. touchend has no `touches` (the finger already
// lifted), hence the changedTouches fallback.
function pointerPosition(e: React.MouseEvent | React.TouchEvent): { clientX: number; clientY: number } | null {
  if ("touches" in e) {
    const t = e.touches[0] ?? e.changedTouches[0];
    return t ? { clientX: t.clientX, clientY: t.clientY } : null;
  }
  return { clientX: e.clientX, clientY: e.clientY };
}

// A tap on a touchscreen also fires an emulated mouseenter, which would leave a desktop-style
// hover card stuck open on a phone -- so the hover card only exists where hovering does.
function canHover(): boolean {
  return typeof window !== "undefined" && (window.matchMedia?.("(hover: hover)").matches ?? false);
}

function readShowNames(): boolean {
  try {
    return localStorage.getItem(SHOW_NAMES_KEY) === "1";
  } catch {
    return false;
  }
}

function writeShowNames(value: boolean) {
  try {
    localStorage.setItem(SHOW_NAMES_KEY, value ? "1" : "0");
  } catch {
    // A per-viewer convenience only; the toggle still works for this visit.
  }
}

function actionLine(summary: GardenActionSummary): string {
  return actionLabel(summary.action_type, summary.custom_label);
}

// -- Plant sheet (view mode, below the map) --------------------------------------------------------

/** The selected plant, as the design's sheet: what it is and where, its next and last care
 * action as two tiles, and the next action as the one big button. */
function PlantSheet({ plant, zoneName, areaId, onOpenDetails }: { plant: GardenPlantMarker; zoneName: string | null; areaId: number; onOpenDetails: () => void }) {
  const queryClient = useQueryClient();
  const ref = useRef<HTMLElement>(null);
  const Icon = PLANT_ICON_COMPONENTS[resolvePlantIcon(plant.icon, plant.type)];
  const next = plant.next_action;
  const due = plantDueState(plant);

  useEffect(() => {
    ref.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [plant.id]);

  const doneMutation = useMutation({
    mutationFn: (action: GardenActionSummary) =>
      gardnrApi.createLog(plant.id, { action_type: action.action_type, custom_label: action.custom_label, performed_on: todayLocalISO(), notes: null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["gardnr-area", areaId] });
      queryClient.invalidateQueries({ queryKey: ["gardnr-plants"] });
      queryClient.invalidateQueries({ queryKey: ["gardnr-plant", plant.id] });
    },
  });

  const nextTile =
    due === "late"
      ? { box: "bg-ui-late-soft", label: "text-ui-late", value: "text-ui-late-ink" }
      : due === "today"
        ? { box: "bg-ui-today-soft", label: "text-ui-today", value: "text-ui-today" }
        : { box: "bg-ui-tile", label: "text-ui-muted", value: "text-ui-ink" };
  const subtitle = [plant.species, zoneName].filter(Boolean).join(" · ");

  return (
    <section
      ref={ref}
      aria-label={plant.name}
      className="flex flex-col gap-3.5 rounded-[20px] border border-ui-border bg-ui-surface p-4 shadow-[0_8px_24px_rgba(27,26,31,0.06)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-ui-brand-soft text-ui-brand">
            <Icon className="h-[22px] w-[22px]" strokeWidth={2} />
          </span>
          <div className="flex min-w-0 flex-col gap-px">
            <span className="truncate font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">{plant.name}</span>
            {subtitle && <span className="truncate text-[13px] italic text-ui-muted">{subtitle}</span>}
          </div>
        </div>
        <button type="button" onClick={onOpenDetails} className="flex min-h-11 shrink-0 items-center text-sm font-semibold text-ui-brand-strong hover:text-ui-brand">{tr("Details")}</button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className={`flex flex-col gap-0.5 rounded-xl px-3 py-2.5 ${nextTile.box}`}>
          <span className={`text-xs font-semibold ${nextTile.label}`}>{next ? actionLine(next) : tr("Volgende")}</span>
          <span className={`text-sm font-semibold ${nextTile.value}`}>{next ? dueText(next.date).text : tr("geen schema")}</span>
        </div>
        <div className="flex flex-col gap-0.5 rounded-xl bg-ui-tile px-3 py-2.5">
          <span className="text-xs font-semibold text-ui-muted">{tr("Laatst gedaan")}</span>
          <span className="text-sm font-semibold text-ui-ink">
            {plant.last_action ? `${actionLine(plant.last_action)} · ${gardnrDate(plant.last_action.date)}` : tr("nog niets")}
          </span>
        </div>
      </div>

      {doneMutation.isSuccess && <p className="m-0 text-[13px] text-ui-brand-strong">{actionLine(doneMutation.variables)}{" "}{tr("geregistreerd voor vandaag.")}</p>}
      {doneMutation.isError && <p className="m-0 text-[13px] text-ui-late">{tr("Registreren is mislukt — probeer het opnieuw.")}</p>}

      {next && (
        <button
          type="button"
          onClick={() => doneMutation.mutate(next)}
          disabled={doneMutation.isPending}
          // Only a due action gets the solid green button; one that isn't due yet can still be
          // logged early, but shouldn't look like the thing to tap.
          className={due ? primaryButtonClass : `${secondaryButtonClass} h-12`}
        >
          {next.action_type === "water" ? <IconDroplet size={18} /> : <IconCheck size={18} />}
          {actionLine(next)}{" "}{tr("gedaan")}</button>
      )}
    </section>
  );
}

// -- Hover card (desktop only) --------------------------------------------------------------------

function PlantHoverCard({ plant, x, y }: { plant: GardenPlantMarker; x: number; y: number }) {
  // Kept inside the canvas (which clips its overflow): pulled in from the side edges, and flipped
  // below the marker when there's no room above it.
  const left = Math.min(85, Math.max(15, x));
  const below = y < 30;
  const next = plant.next_action;
  return (
    <div
      className="pointer-events-none absolute z-20 w-52 rounded-xl border border-ui-border bg-ui-surface p-2.5 text-xs shadow-lg"
      style={{
        left: `${left}%`,
        top: below ? `calc(${y}% + 2rem)` : `calc(${y}% - 2rem)`,
        transform: below ? "translateX(-50%)" : "translate(-50%, -100%)",
      }}
    >
      <div className="truncate text-sm font-semibold text-ui-ink">{plant.name}</div>
      {plant.species && <div className="italic text-ui-muted">{plant.species}</div>}
      <div className={`mt-1 ${plantDueState(plant) === "late" ? "font-semibold text-ui-late" : "text-ui-ink-soft"}`}>
        {next ? `${actionLine(next)} · ${dueText(next.date).text}` : tr("geen schema")}
      </div>
    </div>
  );
}

// -- Resize handle ------------------------------------------------------------------------------

/** The square on the selected shape's bottom-right corner in edit mode. Dragging it (mouse or
 * finger) resizes instead of moving; its transparent padding makes a bigger target than the
 * visible 18px square. */
function ResizeHandle({ label, onStart }: { label: string; onStart: (e: React.MouseEvent | React.TouchEvent) => void }) {
  return (
    <div
      role="presentation"
      data-testid={`resize-${label}`}
      title={tr("Sleep om het formaat te wijzigen")}
      onMouseDown={onStart}
      onTouchStart={onStart}
      onClick={(e) => e.stopPropagation()}
      className="absolute -bottom-[18px] -right-[18px] z-10 flex h-9 w-9 cursor-nwse-resize touch-none items-center justify-center"
    >
      <span className="h-[18px] w-[18px] rounded border-2 border-ui-brand-strong bg-white" />
    </div>
  );
}

// -- Plant marker -----------------------------------------------------------------------------

function PlantMarker({
  plant,
  x,
  y,
  width,
  height,
  editing,
  selected,
  showName,
  onSelect,
  onDragStart,
  onResizeStart,
  onHover,
}: {
  plant: GardenPlantMarker;
  x: number;
  y: number;
  width: number;
  height: number;
  editing: boolean;
  selected: boolean;
  showName: boolean;
  onSelect: () => void;
  onDragStart: (e: React.MouseEvent | React.TouchEvent) => void;
  /** Only passed while this marker can be resized (edit mode, selected, no add tool active). */
  onResizeStart?: (e: React.MouseEvent | React.TouchEvent) => void;
  onHover: (hovering: boolean) => void;
}) {
  const Icon = PLANT_ICON_COMPONENTS[resolvePlantIcon(plant.icon, plant.type)];
  const due = plantDueState(plant);
  const circle = plant.marker_shape === "circle";
  const minPx = selected && !editing ? SELECTED_MARKER_PX : MARKER_PX;
  return (
    <button
      type="button"
      // View mode: a plain tap/click target, so the page scrolls normally under a finger.
      // Edit mode: a drag handle (touch-none keeps the page from scrolling mid-drag).
      onClick={editing ? undefined : onSelect}
      onMouseDown={editing ? onDragStart : undefined}
      onTouchStart={editing ? onDragStart : undefined}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      className={`absolute flex -translate-x-1/2 -translate-y-1/2 items-center justify-center bg-white p-0 text-ui-brand ${
        editing ? "cursor-grab touch-none" : "cursor-pointer"
      } ${selected ? "z-10" : ""}`}
      style={{
        left: `${x}%`,
        top: `${y}%`,
        // Circles size off the width alone so they stay round on a 4:3 map (a percent height is
        // a percent of the shorter side, which used to squash them into ovals).
        width: `max(${minPx}px, ${width}%)`,
        height: circle ? undefined : `max(${minPx}px, ${height}%)`,
        aspectRatio: circle ? "1" : undefined,
        borderRadius: circle ? "9999px" : "12px",
        boxShadow: selected
          ? "0 0 0 4px rgb(var(--ui-brand-rgb)), 0 4px 12px rgba(27,26,31,0.18)"
          : "0 2px 6px rgba(27,26,31,0.16)",
      }}
      aria-label={plant.name}
      aria-pressed={editing ? undefined : selected}
    >
      <Icon className="h-[22px] w-[22px]" strokeWidth={2} />
      {due && (
        <span
          className={`absolute -right-1 -top-1 flex h-[18px] w-[18px] items-center justify-center rounded-full border-2 border-white text-white ${
            due === "late" ? "bg-ui-late" : "bg-ui-today-dot"
          }`}
          aria-label={due === "late" ? tr("te laat") : tr("vandaag")}
        >
          {due === "late" ? <IconAlert size={10} strokeWidth={3.5} /> : <IconDroplet size={10} strokeWidth={3} />}
        </span>
      )}
      {showName && (
        <span className="pointer-events-none absolute left-1/2 top-full mt-1 -translate-x-1/2 whitespace-nowrap rounded-full bg-white/[0.92] px-[7px] py-0.5 text-[11px] font-semibold text-[#1B1A1F]">
          {plant.name}
        </span>
      )}
      {onResizeStart && <ResizeHandle label={`plant-${plant.id}`} onStart={onResizeStart} />}
    </button>
  );
}

// -- Edit mode: selected zone / plant ------------------------------------------------------------

/** The selected zone's editor, below the map: its name, delete, and the design's six colours. */
function ZoneEditor({ zone, onDeleted }: { zone: GardenZone; onDeleted: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(zone.name);
  useEffect(() => setName(zone.name), [zone.id, zone.name]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["gardnr-area", zone.area_id] });
  const updateMutation = useMutation({
    mutationFn: (input: Partial<Pick<GardenZone, "name" | "color">>) => gardnrApi.updateZone(zone.id, input),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: () => gardnrApi.deleteZone(zone.id),
    onSuccess: () => {
      invalidate();
      onDeleted();
    },
  });

  const saveName = () => {
    const trimmed = name.trim();
    if (trimmed && trimmed !== zone.name) updateMutation.mutate({ name: trimmed });
    else setName(zone.name);
  };

  return (
    <section aria-label={tr("Vak bewerken")} className="flex flex-col gap-3 rounded-[20px] border border-ui-border bg-ui-surface px-4 py-3.5">
      <div className="flex items-end gap-2">
        <label className="flex flex-grow flex-col gap-1 text-xs font-semibold text-ui-muted">{tr("Naam van het vak")}<input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={saveName}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
            className={inputClass}
          />
        </label>
        <button
          type="button"
          aria-label={tr("Vak verwijderen")}
          onClick={() => {
            if (confirm(tr("Vak \"{name}\" verwijderen? Planten erop blijven staan.", { name: zone.name }))) deleteMutation.mutate();
          }}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-ui-late-line bg-ui-surface text-ui-late"
        >
          <IconTrash size={18} />
        </button>
      </div>
      <div className="flex flex-wrap gap-2.5">
        {ZONE_PALETTE.map((swatch) => {
          const selected = zone.color.toLowerCase() === swatch.color.toLowerCase();
          return (
            <button
              key={swatch.color}
              type="button"
              aria-label={tr("Kleur {color}", { color: tr(swatch.label) })}
              aria-pressed={selected}
              onClick={() => updateMutation.mutate({ color: swatch.color })}
              className={`h-9 w-9 rounded-full p-0 ${selected ? "border-[3px] border-ui-brand-strong" : "border border-ui-line"}`}
              style={{ backgroundColor: swatch.color }}
            />
          );
        })}
      </div>
      {(updateMutation.isError || deleteMutation.isError) && <p className="m-0 text-sm text-ui-late">{tr("Opslaan is mislukt — probeer het opnieuw.")}</p>}
    </section>
  );
}

/** The selected plant in edit mode: a pointer to its size handle and its full details. */
function PlantEditor({ plant, onOpenDetails }: { plant: GardenPlantMarker; onOpenDetails: () => void }) {
  return (
    <section aria-label={tr("Plant bewerken")} className="flex items-center justify-between gap-3 rounded-[20px] border border-ui-border bg-ui-surface px-4 py-3.5">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-[15px] font-bold text-ui-ink">{plant.name}</span>
        <span className="text-[13px] text-ui-muted">{tr("Sleep het hoekje om de marker groter of kleiner te maken.")}</span>
      </div>
      <button type="button" onClick={onOpenDetails} className={`${secondaryButtonClass} shrink-0`}>{tr("Details")}</button>
    </section>
  );
}

// -- Main canvas ----------------------------------------------------------------------------

// "place-plant" puts an existing, not-yet-placed plant (added from Planten) on the map.
type EditTool = "none" | "add-plant" | "place-plant";
type Selection = { kind: "zone" | "plant"; id: number } | null;

export default function GardnrAreaMap() {
  const { id } = useParams<{ id: string }>();
  const areaId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const canvasRef = useRef<HTMLDivElement>(null);

  // View mode is the default: tapping never moves anything, the page scrolls over the map, and a
  // tap on a plant opens its sheet. Rearranging the garden is a deliberate switch into edit mode.
  const [editing, setEditing] = useState(false);
  const [tool, setTool] = useState<EditTool>("none");
  const [showNames, setShowNames] = useState(readShowNames);
  // Edit mode: which zone or plant is selected (its editor shows below the map, and only it gets
  // a resize handle). View mode: which plant's sheet is open.
  const [selection, setSelection] = useState<Selection>(null);
  const [peekPlantId, setPeekPlantId] = useState<number | null>(null);
  const [hoveredPlantId, setHoveredPlantId] = useState<number | null>(null);
  const [detailPlantId, setDetailPlantId] = useState<number | null>(null);
  const [newPlantAt, setNewPlantAt] = useState<{ x: number; y: number } | null>(null);
  const [placingPlantId, setPlacingPlantId] = useState<number | null>(null);
  // One gesture state for both moving and resizing. While moving, x/y follow the pointer; while
  // resizing they stay put (a zone's top-left corner, a marker's centre) and w/h follow instead.
  const [drag, setDrag] = useState<{
    kind: "zone" | "plant";
    mode: "move" | "resize";
    id: number;
    x: number;
    y: number;
    w: number;
    h: number;
    moved: boolean;
  } | null>(null);
  const dragStartRef = useRef<{ px: number; py: number; threshold: number } | null>(null);
  // Mirrors `drag` for the touch listeners below -- they're attached once (native, non-passive,
  // so touchmove can preventDefault to stop the page scrolling mid-drag) rather than re-attached
  // on every position update, so they read the current drag through this ref instead of a
  // closed-over `drag` value that would otherwise go stale the moment the listener was bound.
  const dragRef = useRef<typeof drag>(null);
  useLayoutEffect(() => {
    dragRef.current = drag;
  }, [drag]);

  const areaQuery = useQuery({ queryKey: ["gardnr-area", areaId], queryFn: () => gardnrApi.getAreaDetail(areaId), enabled: !!areaId });
  const plantsQuery = useQuery({ queryKey: ["gardnr-plants", false], queryFn: () => gardnrApi.listPlants(false) });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["gardnr-area", areaId] });

  const createZoneMutation = useMutation({
    mutationFn: () => gardnrApi.createZone(areaId, { ...NEW_ZONE, name: tr(NEW_ZONE.name) }),
    onSuccess: (zone) => {
      invalidate();
      // Straight into its editor, name field first -- "Nieuw vak" is only a placeholder.
      setSelection({ kind: "zone", id: zone.id });
    },
  });
  const moveZoneMutation = useMutation({
    mutationFn: ({ id: zoneId, input }: { id: number; input: Partial<Pick<GardenZone, "x" | "y" | "width" | "height">> }) => gardnrApi.updateZone(zoneId, input),
    onError: invalidate,
  });
  const movePlantMutation = useMutation({
    mutationFn: ({ id: plantId, input }: { id: number; input: { x?: string; y?: string; marker_width?: string; marker_height?: string } }) =>
      gardnrApi.updatePlant(plantId, input),
    onError: invalidate,
  });
  const createPlantMutation = useMutation({
    mutationFn: (input: NewPlantInput) =>
      gardnrApi.createPlant({
        area_id: areaId,
        name: input.name,
        type: input.type,
        species: input.species || undefined,
        x: newPlantAt ? newPlantAt.x.toFixed(2) : undefined,
        y: newPlantAt ? newPlantAt.y.toFixed(2) : undefined,
      }),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["gardnr-plants"] });
      setNewPlantAt(null);
      setTool("none");
    },
  });

  function canvasPercent(clientX: number, clientY: number): { x: number; y: number } {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { x: clampPercent(((clientX - rect.left) / rect.width) * 100), y: clampPercent(((clientY - rect.top) / rect.height) * 100) };
  }

  function selectTool(next: EditTool, plantId: number | null = null) {
    setTool(next);
    setPlacingPlantId(plantId);
  }

  function handlePlacementTap(e: React.MouseEvent) {
    const pos = canvasPercent(e.clientX, e.clientY);
    if (tool === "place-plant" && placingPlantId !== null) {
      const input = { x: pos.x.toFixed(2), y: pos.y.toFixed(2) };
      movePlantMutation.mutate({ id: placingPlantId, input });
      queryClient.setQueryData(["gardnr-area", areaId], (old: GardenAreaDetail | undefined) =>
        old ? { ...old, plants: old.plants.map((p) => (p.id === placingPlantId ? { ...p, ...input } : p)) } : old,
      );
      selectTool("none");
      return;
    }
    setNewPlantAt(pos);
  }

  function setEditMode(on: boolean) {
    setEditing(on);
    selectTool("none");
    setSelection(null);
    setPeekPlantId(null);
    setHoveredPlantId(null);
  }

  function toggleShowNames() {
    setShowNames((v) => {
      writeShowNames(!v);
      return !v;
    });
  }

  function startDrag(
    kind: "zone" | "plant",
    mode: "move" | "resize",
    shape: { id: number; x: number; y: number; w: number; h: number },
    e: React.MouseEvent | React.TouchEvent,
  ) {
    if (!editing || tool !== "none") return;
    e.stopPropagation();
    // Keeps a mouse drag from selecting the zone labels' text as it sweeps across them.
    if (!("touches" in e)) e.preventDefault();
    const point = pointerPosition(e);
    if (!point) return;
    const threshold = "touches" in e ? DRAG_THRESHOLD_PX.touch : DRAG_THRESHOLD_PX.mouse;
    dragStartRef.current = { px: point.clientX, py: point.clientY, threshold };
    setDrag({ kind, mode, ...shape, moved: false });
  }

  // Both read/write through dragRef rather than the closed-over `drag` state, since the touch
  // listeners below bind these once and would otherwise keep seeing the drag's starting
  // position forever (see the dragRef comment above).
  const handleMove = useCallback((clientX: number, clientY: number) => {
    const current = dragRef.current;
    const start = dragStartRef.current;
    if (!current || !start || !canvasRef.current) return;
    const movedPx = Math.hypot(clientX - start.px, clientY - start.py);
    if (!current.moved && movedPx <= start.threshold) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const pos = { x: clampPercent(((clientX - rect.left) / rect.width) * 100), y: clampPercent(((clientY - rect.top) / rect.height) * 100) };
    setDrag((d) => {
      if (!d) return d;
      if (d.mode === "move") return { ...d, x: pos.x, y: pos.y, moved: true };
      if (d.kind === "zone") {
        // Anchored at its top-left corner, and never allowed to run off the map's far edge.
        return {
          ...d,
          w: clamp(pos.x - d.x, ZONE_SIZE_RANGE.min, Math.max(ZONE_SIZE_RANGE.min, 100 - d.x)),
          h: clamp(pos.y - d.y, ZONE_SIZE_RANGE.min, Math.max(ZONE_SIZE_RANGE.min, 100 - d.y)),
          moved: true,
        };
      }
      // A marker is centred on its point, so the corner sits half a size away in each direction.
      return {
        ...d,
        w: clamp(Math.abs(pos.x - d.x) * 2, MARKER_SIZE_RANGE.min, MARKER_SIZE_RANGE.max),
        h: clamp(Math.abs(pos.y - d.y) * 2, MARKER_SIZE_RANGE.min, MARKER_SIZE_RANGE.max),
        moved: true,
      };
    });
  }, []);

  const handleEnd = useCallback(() => {
    const current = dragRef.current;
    if (!current) return;
    if (current.moved) {
      const x = current.x.toFixed(2);
      const y = current.y.toFixed(2);
      const w = current.w.toFixed(2);
      const h = current.h.toFixed(2);
      const circleMarker = current.kind === "plant" && areaQuery.data?.plants.find((p) => p.id === current.id)?.marker_shape === "circle";
      const zoneInput = current.mode === "move" ? { x, y } : { width: w, height: h };
      // A circle marker's size is its width alone (it renders square), so keep its height in step.
      const plantInput = current.mode === "move" ? { x, y } : { marker_width: w, marker_height: circleMarker ? w : h };
      if (current.kind === "zone") moveZoneMutation.mutate({ id: current.id, input: zoneInput });
      else movePlantMutation.mutate({ id: current.id, input: plantInput });
      // Optimistic local update so the shape doesn't snap back before the invalidated query refetches.
      queryClient.setQueryData(["gardnr-area", areaId], (old: GardenAreaDetail | undefined) => {
        if (!old) return old;
        if (current.kind === "zone") {
          return { ...old, zones: old.zones.map((z) => (z.id === current.id ? { ...z, ...zoneInput } : z)) };
        }
        return { ...old, plants: old.plants.map((p) => (p.id === current.id ? { ...p, ...plantInput } : p)) };
      });
      // Whatever was just moved is what you're working on.
      setSelection({ kind: current.kind, id: current.id });
    } else if (current.mode === "move") {
      // A tap (not a drag): select it -- its editor appears below the map, and a second tap on an
      // already-selected plant opens its full details.
      setSelection((sel) => {
        if (current.kind === "plant" && sel?.kind === "plant" && sel.id === current.id) setDetailPlantId(current.id);
        return { kind: current.kind, id: current.id };
      });
    }
    setDrag(null);
    dragStartRef.current = null;
  }, [areaId, areaQuery.data, moveZoneMutation, movePlantMutation, queryClient]);

  // touchmove must be non-passive to preventDefault (block the page scrolling under a finger
  // that's dragging a marker) -- React attaches its own onTouchMove/onTouchStart as passive by
  // default, so that has to be a real DOM listener instead of a JSX prop. Attached once per
  // canvas (not re-attached per drag) since handleMove/handleEnd read the live drag through
  // dragRef; `hasData` re-runs it once the canvas actually exists after the first load.
  const hasData = !!areaQuery.data;
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    function onTouchMove(e: TouchEvent) {
      if (!dragRef.current) return;
      e.preventDefault();
      const t = e.touches[0];
      if (t) handleMove(t.clientX, t.clientY);
    }
    function onTouchEnd() {
      if (dragRef.current) handleEnd();
    }
    canvas.addEventListener("touchmove", onTouchMove, { passive: false });
    canvas.addEventListener("touchend", onTouchEnd);
    canvas.addEventListener("touchcancel", onTouchEnd);
    return () => {
      canvas.removeEventListener("touchmove", onTouchMove);
      canvas.removeEventListener("touchend", onTouchEnd);
      canvas.removeEventListener("touchcancel", onTouchEnd);
    };
  }, [handleMove, handleEnd, hasData, editing]);

  if (areaQuery.isError) {
    return (
      <div className="rounded-[20px] border border-ui-border bg-ui-surface p-6 text-center text-sm text-ui-muted">{tr("Deze tuin kon niet worden geladen.")}{" "}
        <button onClick={() => areaQuery.refetch()} className="font-semibold text-ui-brand-strong underline">{tr("Opnieuw proberen")}</button>{" "}{tr("of")}{" "}
        <button onClick={() => navigate("/gardnr")} className="font-semibold text-ui-brand-strong underline">{tr("terug naar Tuinen")}</button>
        .
      </div>
    );
  }
  if (!areaQuery.data) {
    return <div className="rounded-[20px] border border-ui-border bg-ui-surface p-6 text-center text-ui-muted">{tr("Laden…")}</div>;
  }

  const { area, zones, plants } = areaQuery.data;
  const counts = taskCounts(plantsQuery.data ?? []).byArea.get(areaId) ?? { late: 0, today: 0 };
  const unplaced = plants.filter((p) => p.x === null || p.y === null);
  const placingPlant = unplaced.find((p) => p.id === placingPlantId);
  const selectedZone = editing && selection?.kind === "zone" ? zones.find((z) => z.id === selection.id) : undefined;
  const selectedPlant = editing && selection?.kind === "plant" ? plants.find((p) => p.id === selection.id) : undefined;
  const peekPlant = !editing ? plants.find((p) => p.id === peekPlantId) : undefined;
  const hoveredPlant = !editing && !drag ? plants.find((p) => p.id === hoveredPlantId) : undefined;
  const peekZone = peekPlant && peekPlant.x !== null && peekPlant.y !== null ? zoneAt(zones, Number(peekPlant.x), Number(peekPlant.y)) : undefined;
  const editHint =
    tool === "add-plant"
      ? tr("Tik op de kaart waar de nieuwe plant moet komen — ook midden in een vak.")
      : placingPlant
        ? tr("Tik op de kaart waar {name} staat.", { name: placingPlant.name })
        : tr("Sleep vakken en planten naar hun plek. Het hoekje rechtsonder maakt een vak groter of kleiner.");

  const map = (
    <div
      ref={canvasRef}
      onClick={(e) => {
        if (e.target !== canvasRef.current) return;
        // A tap on bare map closes the plant sheet (view) or clears the selection (edit).
        if (editing) setSelection(null);
        else setPeekPlantId(null);
      }}
      onMouseMove={(e) => handleMove(e.clientX, e.clientY)}
      onMouseUp={handleEnd}
      onMouseLeave={() => drag && setDrag(null)}
      className="relative aspect-[4/3] w-full overflow-hidden rounded-[20px] bg-ui-field"
      // Edit mode lays a 16px dot grid over the ground, as in the design.
      style={editing ? { backgroundImage: "radial-gradient(rgb(var(--ui-field-dot-rgb)) 1px, transparent 1px)", backgroundSize: "16px 16px" } : undefined}
    >
      {zones.map((zone) => {
        const dragging = drag?.kind === "zone" && drag.id === zone.id ? drag : null;
        const shown = { x: dragging?.x ?? Number(zone.x), y: dragging?.y ?? Number(zone.y), w: dragging?.w ?? Number(zone.width), h: dragging?.h ?? Number(zone.height) };
        const draggable = editing && tool === "none";
        const isSelected = selectedZone?.id === zone.id;
        const origin = { id: zone.id, x: Number(zone.x), y: Number(zone.y), w: Number(zone.width), h: Number(zone.height) };
        return (
          <div
            key={zone.id}
            onMouseDown={draggable ? (e) => startDrag("zone", "move", origin, e) : undefined}
            onTouchStart={draggable ? (e) => startDrag("zone", "move", origin, e) : undefined}
            // Outside edit mode a zone is pure decoration: taps fall through to the canvas and
            // a finger on a bed scrolls the page like anywhere else.
            className={`absolute select-none ${draggable ? "cursor-grab touch-none" : "pointer-events-none"} ${
              isSelected ? "border-2 border-dashed border-ui-brand-strong" : ""
            }`}
            style={{
              left: `${shown.x}%`,
              top: `${shown.y}%`,
              width: `${shown.w}%`,
              height: `${shown.h}%`,
              background: zoneFill(zone.color),
              borderRadius: zoneRadius(zone, 14),
            }}
          >
            <span className="absolute left-2.5 top-2 text-[11px] font-semibold uppercase tracking-[0.04em] text-ui-zone-ink">{zone.name}</span>
            {draggable && isSelected && <ResizeHandle label={`zone-${zone.id}`} onStart={(e) => startDrag("zone", "resize", origin, e)} />}
          </div>
        );
      })}

      {plants.map((plant) => {
        if (plant.x === null || plant.y === null) return null;
        const dragging = drag?.kind === "plant" && drag.id === plant.id ? drag : null;
        const origin = { id: plant.id, x: Number(plant.x), y: Number(plant.y), w: Number(plant.marker_width), h: Number(plant.marker_height) };
        const isSelected = editing ? selectedPlant?.id === plant.id : peekPlant?.id === plant.id;
        return (
          <PlantMarker
            key={plant.id}
            plant={plant}
            x={dragging?.x ?? origin.x}
            y={dragging?.y ?? origin.y}
            width={dragging?.w ?? origin.w}
            height={dragging?.h ?? origin.h}
            editing={editing}
            selected={isSelected}
            // Names always show while editing (you're arranging by name), and on request otherwise.
            showName={editing || showNames}
            // Tapping the plant whose sheet is already open goes straight to its full details.
            onSelect={() => (peekPlantId === plant.id ? setDetailPlantId(plant.id) : setPeekPlantId(plant.id))}
            onDragStart={(e) => startDrag("plant", "move", origin, e)}
            onResizeStart={editing && tool === "none" && isSelected ? (e) => startDrag("plant", "resize", origin, e) : undefined}
            onHover={(hovering) => {
              if (hovering && canHover()) setHoveredPlantId(plant.id);
              else setHoveredPlantId((hid) => (hid === plant.id ? null : hid));
            }}
          />
        );
      })}

      {hoveredPlant && hoveredPlant.id !== peekPlant?.id && hoveredPlant.x !== null && hoveredPlant.y !== null && (
        <PlantHoverCard plant={hoveredPlant} x={Number(hoveredPlant.x)} y={Number(hoveredPlant.y)} />
      )}

      {editing && (tool === "add-plant" || tool === "place-plant") && (
        // Catches the placement tap anywhere on the map, zones and markers included -- a plant
        // usually belongs *in* a bed, which a canvas-only click target used to refuse.
        <div data-testid="plant-placement-layer" onClick={handlePlacementTap} className="absolute inset-0 z-20 cursor-crosshair" />
      )}

      {zones.length === 0 && plants.length === 0 && !editing && (
        <div className="absolute inset-0 flex items-center justify-center p-4 text-center text-sm text-ui-muted">{tr("Lege kaart — tik op Bewerken om een vak of plant toe te voegen.")}</div>
      )}
    </div>
  );

  const errors = (
    <>
      {createZoneMutation.isError && <p className="m-0 text-sm text-ui-late">{tr("Vak aanmaken is mislukt — probeer het opnieuw.")}</p>}
      {(moveZoneMutation.isError || movePlantMutation.isError) && (
        <p className="m-0 text-sm text-ui-late">{tr("Opslaan is mislukt — de vorige positie en grootte zijn teruggezet.")}</p>
      )}
    </>
  );

  const dialogs = (
    <>
      {newPlantAt && (
        <NewPlantDialog
          onCancel={() => setNewPlantAt(null)}
          isSubmitting={createPlantMutation.isPending}
          isError={createPlantMutation.isError}
          onSubmit={(input) => createPlantMutation.mutate(input)}
        />
      )}
      <PlantDetailPanel plantId={detailPlantId} onClose={() => setDetailPlantId(null)} />
    </>
  );

  if (editing) {
    const toolButton = (active: boolean) => `${secondaryButtonClass} w-full ${active ? "border-ui-brand-strong bg-ui-brand-soft text-ui-brand-strong" : ""}`;
    return (
      <div className="flex flex-col gap-3 pb-2">
        <EditBar title={area.name} onDone={() => setEditMode(false)} />
        <p className="m-0 pt-1 text-[13px] text-ui-ink-soft">{editHint}</p>
        {map}
        {errors}
        <div className="grid grid-cols-2 gap-2">
          <button type="button" onClick={() => createZoneMutation.mutate()} disabled={createZoneMutation.isPending} className={toolButton(false)}>
            <IconSquare size={18} />{tr("+ Vak")}</button>
          <button type="button" onClick={() => selectTool(tool === "add-plant" ? "none" : "add-plant")} aria-pressed={tool === "add-plant"} className={toolButton(tool === "add-plant")}>
            <IconSprout size={18} />{tr("+ Plant")}</button>
        </div>
        {selectedZone && <ZoneEditor key={selectedZone.id} zone={selectedZone} onDeleted={() => setSelection(null)} />}
        {selectedPlant && <PlantEditor plant={selectedPlant} onOpenDetails={() => setDetailPlantId(selectedPlant.id)} />}
        {unplaced.length > 0 && (
          <section aria-label={tr("Nog niet op de kaart")} className="flex flex-col gap-2.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[15px] font-bold text-ui-ink">{tr("Nog niet op de kaart")}</span>
              <span className="text-[13px] text-ui-muted">{tr("Tik een plant, dan de plek")}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {unplaced.map((p) => {
                const Icon = PLANT_ICON_COMPONENTS[resolvePlantIcon(p.icon, p.type)];
                const placing = placingPlantId === p.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    aria-pressed={placing}
                    onClick={() => (placing ? selectTool("none") : selectTool("place-plant", p.id))}
                    className={`${secondaryButtonClass} border-dashed ${placing ? "border-solid border-ui-brand-strong bg-ui-brand-soft text-ui-brand-strong" : ""}`}
                  >
                    <Icon className="h-[18px] w-[18px] text-ui-brand" strokeWidth={2} />
                    {p.name}
                  </button>
                );
              })}
            </div>
          </section>
        )}
        {dialogs}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3.5 pb-2">
      <GardnrTopRow
        left={
          <Link to="/gardnr" aria-label={tr("Terug naar Tuinen")} className={`${secondaryButtonClass} pl-2 pr-3 no-underline`}>
            <IconChevronLeft size={20} />{tr("Tuinen")}</Link>
        }
      >
        <button type="button" onClick={() => setEditMode(true)} className={secondaryButtonClass}>
          <IconPencil size={18} />{tr("Bewerken")}</button>
      </GardnrTopRow>

      <div className="flex items-end justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <PageTitle size="md">{area.name}</PageTitle>
          <div className="flex flex-wrap gap-1.5">
            <AreaStatusChips late={counts.late} today={counts.today} />
          </div>
        </div>
        <button
          type="button"
          onClick={toggleShowNames}
          aria-pressed={showNames}
          title={tr("Namen op de kaart tonen")}
          className={`inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold ${
            showNames ? "border-ui-brand-strong bg-ui-brand-soft text-ui-brand-strong" : "border-ui-border bg-ui-surface text-ui-ink-soft"
          }`}
        >
          <IconTag size={16} />{tr("Namen")}</button>
      </div>

      {map}
      {errors}

      {peekPlant && (
        <PlantSheet
          key={peekPlant.id}
          plant={peekPlant}
          zoneName={peekZone?.name ?? null}
          areaId={areaId}
          onOpenDetails={() => setDetailPlantId(peekPlant.id)}
        />
      )}
      {!peekPlant && plants.length > unplaced.length && (
        <p className="m-0 text-[13px] text-ui-muted">{tr("Tik op een plant voor wat er moet gebeuren; nog een keer tikken opent alle gegevens.")}</p>
      )}
      {unplaced.length > 0 && (
        <p className="m-0 text-[13px] text-ui-ink-soft">
          {unplaced.length === 1
            ? tr("{name} staat nog niet op de kaart — plaats ze via Bewerken.", { name: unplaced[0].name })
            : tr("{n} planten staan nog niet op de kaart — plaats ze via Bewerken.", { n: unplaced.length })}
        </p>
      )}
      {dialogs}
    </div>
  );
}
