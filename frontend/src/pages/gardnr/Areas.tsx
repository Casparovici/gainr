import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { gardnrApi } from "../../api/gardnrClient";
import type { GardenArea, GardenAreaDetail } from "../../api/gardnrTypes";
import {
  AreaStatusChips,
  EditBar,
  GardnrTopRow,
  IconAlert,
  IconChevronDown,
  IconChevronRight,
  IconChevronUp,
  IconDroplet,
  IconGrip,
  IconPencil,
  IconPlus,
  IconTrash,
  MiniMap,
  PageTitle,
  dangerButtonClass,
  dashedButtonClass,
  iconButtonClass,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
  taskCounts,
  type TaskCounts,
} from "../../components/gardnr/ui";
import { t, tp } from "../../i18n";

/** "2 taken te laat — en 2 voor vandaag, in 2 tuinen", linking to Vandaag. Terracotta when
 * something is overdue, amber when it's only today's work; absent when nothing is due. */
function DueBanner({ total, gardens }: { total: TaskCounts; gardens: number }) {
  if (total.late === 0 && total.today === 0) return null;
  const late = total.late > 0;
  const inGardens = tp(gardens, "in {n} tuin", "in {n} tuinen");
  return (
    <Link
      to="/gardnr/vandaag"
      className={`flex items-center gap-3 rounded-2xl px-4 py-3.5 no-underline ${late ? "bg-ui-late-soft text-ui-late" : "bg-ui-today-soft text-ui-today"}`}
    >
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white ${late ? "bg-ui-late" : "bg-ui-today-dot"}`}>
        {late ? <IconAlert size={18} strokeWidth={3} /> : <IconDroplet size={18} strokeWidth={2.4} />}
      </span>
      <span className="flex min-w-0 flex-grow flex-col gap-px">
        <span className="text-[15px] font-bold">
          {late ? tp(total.late, "{n} taak te laat", "{n} taken te laat") : tp(total.today, "{n} taak voor vandaag", "{n} taken voor vandaag")}
        </span>
        <span className={`text-[13px] ${late ? "text-ui-late-ink" : "text-ui-today"}`}>
          {late && total.today > 0 ? t("en {today} voor vandaag, {inGardens}", { today: total.today, inGardens }) : inGardens}
        </span>
      </span>
      <span className="flex shrink-0 items-center gap-0.5 text-sm font-semibold">{t("Vandaag")}<IconChevronRight size={16} />
      </span>
    </Link>
  );
}

function AreaCard({ area, detail, counts }: { area: GardenArea; detail: GardenAreaDetail | undefined; counts: TaskCounts }) {
  return (
    <Link
      to={`/gardnr/areas/${area.id}`}
      className="flex items-center gap-3.5 rounded-[20px] border border-ui-border bg-ui-surface p-3 text-ui-ink no-underline transition-colors hover:border-ui-line"
    >
      <MiniMap detail={detail} width={96} height={108} />
      <div className="flex min-w-0 flex-grow flex-col gap-2">
        <div className="flex flex-col gap-0.5">
          <span className="truncate font-display text-xl font-bold tracking-[-0.02em]">{area.name}</span>
          <span className="text-sm text-ui-muted">{tp(area.plant_count, "{n} plant", "{n} planten")}</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <AreaStatusChips late={counts.late} today={counts.today} />
        </div>
      </div>
      <span className="shrink-0 text-ui-muted">
        <IconChevronRight size={20} />
      </span>
    </Link>
  );
}

/** Edit mode: drag by the grip (or move with the arrows, which work with a finger), rename in
 * place, or delete. */
function EditableAreaCard({
  area,
  detail,
  isFirst,
  isLast,
  onRename,
  onMove,
  onDelete,
  dragProps,
  isDragTarget,
}: {
  area: GardenArea;
  detail: GardenAreaDetail | undefined;
  isFirst: boolean;
  isLast: boolean;
  onRename: (name: string) => void;
  onMove: (direction: -1 | 1) => void;
  onDelete: () => void;
  dragProps: React.HTMLAttributes<HTMLDivElement> & { draggable: boolean };
  isDragTarget: boolean;
}) {
  const [name, setName] = useState(area.name);
  const save = () => {
    const trimmed = name.trim();
    if (trimmed && trimmed !== area.name) onRename(trimmed);
    else setName(area.name);
  };
  return (
    <div
      {...dragProps}
      className={`flex flex-col gap-2.5 rounded-[20px] border bg-ui-surface p-3 ${isDragTarget ? "border-ui-brand" : "border-ui-border"}`}
    >
      <div className="flex items-center gap-2.5">
        <span aria-hidden className="shrink-0 cursor-grab text-ui-faint" title={t("Sleep om te verplaatsen")}>
          <IconGrip size={20} />
        </span>
        <MiniMap detail={detail} width={56} height={62} />
        <label className="flex flex-grow flex-col gap-0.5 text-xs text-ui-muted">
          {tp(area.plant_count, "{n} plant", "{n} planten")}
          <input
            type="text"
            value={name}
            aria-label={t("Naam")}
            onChange={(e) => setName(e.target.value)}
            onBlur={save}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
              if (e.key === "Escape") {
                setName(area.name);
                e.currentTarget.blur();
              }
            }}
            className={`${inputClass} font-semibold`}
          />
        </label>
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={() => onMove(-1)} disabled={isFirst} aria-label={t("{name} eerder zetten", { name: area.name })} className={iconButtonClass}>
          <IconChevronUp size={20} />
        </button>
        <button type="button" onClick={() => onMove(1)} disabled={isLast} aria-label={t("{name} later zetten", { name: area.name })} className={iconButtonClass}>
          <IconChevronDown size={20} />
        </button>
        <button type="button" onClick={onDelete} aria-label={t("{name} verwijderen", { name: area.name })} className={dangerButtonClass}>
          <IconTrash size={18} />{t("Verwijderen")}</button>
      </div>
    </div>
  );
}

function NewAreaForm({ onCancel, onSubmit, isPending }: { onCancel: () => void; onSubmit: (name: string) => void; isPending: boolean }) {
  const [name, setName] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) onSubmit(name.trim());
      }}
      className="flex flex-col gap-3 rounded-[20px] border border-ui-border bg-ui-surface p-3"
    >
      <label className="flex flex-col gap-1 text-xs font-semibold text-ui-muted">{t("Naam van de tuin")}<input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder={t("bijv. Voortuin")} className={inputClass} />
      </label>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className={secondaryButtonClass}>{t("Annuleren")}</button>
        <button type="submit" disabled={!name.trim() || isPending} className={`${primaryButtonClass} h-11`}>
          {isPending ? t("Toevoegen…") : t("Toevoegen")}
        </button>
      </div>
    </form>
  );
}

function Placeholder({ children }: { children: React.ReactNode }) {
  return <div className="rounded-[20px] border border-ui-border bg-ui-surface p-6 text-center text-sm text-ui-muted">{children}</div>;
}

export default function GardnrAreas() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [draggedId, setDraggedId] = useState<number | null>(null);
  const [dragOverId, setDragOverId] = useState<number | null>(null);

  const areasKey = ["gardnr-areas"];
  const areasQuery = useQuery({ queryKey: areasKey, queryFn: gardnrApi.listAreas });
  const plantsQuery = useQuery({ queryKey: ["gardnr-plants", false], queryFn: () => gardnrApi.listPlants(false) });
  const areas = areasQuery.data ?? [];
  // Each garden's own map, for its card's thumbnail -- the same query the map page reads, so
  // opening a garden afterwards is instant.
  const detailQueries = useQueries({
    queries: areas.map((a) => ({ queryKey: ["gardnr-area", a.id], queryFn: () => gardnrApi.getAreaDetail(a.id) })),
  });
  const detailById = new Map(areas.map((a, i) => [a.id, detailQueries[i]?.data]));

  const { byArea, total } = taskCounts(plantsQuery.data ?? []);
  const countsOf = (areaId: number): TaskCounts => byArea.get(areaId) ?? { late: 0, today: 0 };
  const gardensWithWork = areas.filter((a) => {
    const c = countsOf(a.id);
    return c.late > 0 || c.today > 0;
  }).length;
  const plantTotal = areas.reduce((sum, a) => sum + a.plant_count, 0);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: areasKey });

  const createMutation = useMutation({
    mutationFn: (name: string) => gardnrApi.createArea(name),
    onSuccess: () => {
      invalidate();
      setCreating(false);
    },
  });
  const reorderMutation = useMutation({
    mutationFn: (areaIds: number[]) => gardnrApi.reorderAreas(areaIds),
    onError: invalidate,
  });
  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => gardnrApi.updateArea(id, { name }),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => gardnrApi.deleteArea(id),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["gardnr-plants"] });
    },
  });

  function confirmDelete(area: GardenArea) {
    const question =
      area.plant_count > 0
        ? tp(
            area.plant_count,
            "\"{name}\" verwijderen? Ook de {n} plant erin, met hun verzorgingslogboek en schema's, worden ook verwijderd.",
            "\"{name}\" verwijderen? Ook de {n} planten erin, met hun verzorgingslogboek en schema's, worden ook verwijderd.",
            { name: area.name },
          )
        : t("\"{name}\" verwijderen? Ook de vakken op de plattegrond worden ook verwijderd.", { name: area.name });
    if (window.confirm(question)) deleteMutation.mutate(area.id);
  }

  /** Moves `sourceId` to `targetIndex` in the current order -- optimistically, then saved. */
  function reorder(sourceId: number, targetIndex: number) {
    if (!areasQuery.data) return;
    const ids = areasQuery.data.map((a) => a.id);
    const fromIdx = ids.indexOf(sourceId);
    if (fromIdx === -1 || targetIndex < 0 || targetIndex >= ids.length || targetIndex === fromIdx) return;
    ids.splice(targetIndex, 0, ids.splice(fromIdx, 1)[0]);
    queryClient.setQueryData<GardenArea[]>(areasKey, (old) => {
      if (!old) return old;
      const byId = new Map(old.map((a) => [a.id, a]));
      return ids.map((id) => byId.get(id)!);
    });
    reorderMutation.mutate(ids);
  }

  function handleDrop(targetId: number) {
    const sourceId = draggedId;
    setDraggedId(null);
    setDragOverId(null);
    if (sourceId === null || sourceId === targetId || !areasQuery.data) return;
    reorder(sourceId, areasQuery.data.findIndex((a) => a.id === targetId));
  }

  const failed = createMutation.isError || renameMutation.isError || deleteMutation.isError || reorderMutation.isError;
  const newArea = creating ? (
    <NewAreaForm onCancel={() => setCreating(false)} onSubmit={(name) => createMutation.mutate(name)} isPending={createMutation.isPending} />
  ) : (
    <button type="button" onClick={() => setCreating(true)} className={dashedButtonClass}>
      <IconPlus size={20} />{t("Nieuwe tuin")}</button>
  );

  if (editing) {
    return (
      <div className="flex flex-col gap-3">
        <EditBar title={t("Tuinen")} onDone={() => setEditing(false)} />
        <p className="m-0 pt-1 text-[13px] text-ui-ink-soft">{t("Hernoem een tuin, zet hem hoger of lager, of houd de greep vast om te slepen.")}</p>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {areas.map((area, i) => (
            <EditableAreaCard
              key={area.id}
              area={area}
              detail={detailById.get(area.id)}
              isFirst={i === 0}
              isLast={i === areas.length - 1}
              onRename={(name) => renameMutation.mutate({ id: area.id, name })}
              onMove={(direction) => reorder(area.id, i + direction)}
              onDelete={() => confirmDelete(area)}
              isDragTarget={dragOverId === area.id && draggedId !== area.id}
              dragProps={{
                draggable: true,
                onDragStart: () => setDraggedId(area.id),
                onDragEnd: () => {
                  setDraggedId(null);
                  setDragOverId(null);
                },
                onDragOver: (e) => {
                  e.preventDefault();
                  if (dragOverId !== area.id) setDragOverId(area.id);
                },
                onDrop: () => handleDrop(area.id),
              }}
            />
          ))}
        </div>
        {newArea}
        {failed && <p className="text-sm text-ui-late">{t("Opslaan is mislukt — probeer het opnieuw.")}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <GardnrTopRow>
        {areas.length > 0 && (
          <button type="button" onClick={() => setEditing(true)} className={secondaryButtonClass}>
            <IconPencil size={18} />{t("Bewerken")}</button>
        )}
      </GardnrTopRow>

      <PageTitle subtitle={areasQuery.data ? `${tp(areas.length, "{n} tuin", "{n} tuinen")} · ${tp(plantTotal, "{n} plant", "{n} planten")}` : undefined}>{t("Tuinen")}</PageTitle>

      <DueBanner total={total} gardens={gardensWithWork} />

      {areasQuery.isLoading ? (
        <Placeholder>{t("Laden…")}</Placeholder>
      ) : areasQuery.isError ? (
        <Placeholder>{t("Tuinen konden niet worden geladen.")}{" "}
          <button onClick={() => areasQuery.refetch()} className="font-semibold text-ui-brand-strong underline">{t("Opnieuw proberen")}</button>
        </Placeholder>
      ) : areas.length === 0 ? (
        <Placeholder>{t("Nog geen tuinen — voeg er een toe om je planten in kaart te brengen.")}</Placeholder>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {areas.map((area) => (
            <AreaCard key={area.id} area={area} detail={detailById.get(area.id)} counts={countsOf(area.id)} />
          ))}
        </div>
      )}

      {newArea}
      {failed && <p className="text-sm text-ui-late">{t("Opslaan is mislukt — probeer het opnieuw.")}</p>}
    </div>
  );
}
