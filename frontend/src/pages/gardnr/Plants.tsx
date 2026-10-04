import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { gardnrApi } from "../../api/gardnrClient";
import { GardnrTopRow, PageTitle, secondaryButtonClass } from "../../components/gardnr/ui";
import {
  GARDEN_PLANT_STATUS_DOT_CLASS,
  GARDEN_PLANT_STATUS_LABELS,
  GARDEN_PLANT_STATUSES,
  GARDEN_PLANT_TYPE_LABELS,
  type GardenPlantListRow,
  type GardenPlantStatus,
} from "../../api/gardnrTypes";
import MobileFab from "../../components/MobileFab";
import NewPlantDialog, { type NewPlantInput } from "../../components/gardnr/NewPlantDialog";
import PlantDetailPanel from "../../components/gardnr/PlantDetailPanel";
import { actionLabel, dueText } from "../../utils/gardnr";

const inputClass =
  "rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

function NextAction({ plant, emptyText = "—" }: { plant: GardenPlantListRow; emptyText?: string }) {
  if (!plant.next_action) return <span className="text-slate-400">{emptyText}</span>;
  const due = dueText(plant.next_action.date);
  return (
    <span className={due.isDue ? "font-medium text-red-600" : "text-slate-600"}>
      {actionLabel(plant.next_action.action_type, plant.next_action.custom_label)} {due.text}
    </span>
  );
}

function StatusDot({ status }: { status: GardenPlantStatus }) {
  return <span className={`h-2 w-2 shrink-0 rounded-full ${GARDEN_PLANT_STATUS_DOT_CLASS[status]}`} title={GARDEN_PLANT_STATUS_LABELS[status]} />;
}

export default function GardnrPlants() {
  const queryClient = useQueryClient();
  const [includeArchived, setIncludeArchived] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [areaFilter, setAreaFilter] = useState<number | "all">("all");
  const [statusFilter, setStatusFilter] = useState<GardenPlantStatus | "all">("all");
  const [adding, setAdding] = useState(false);

  const plantsQuery = useQuery({
    queryKey: ["gardnr-plants", includeArchived],
    queryFn: () => gardnrApi.listPlants(includeArchived),
  });
  const areasQuery = useQuery({ queryKey: ["gardnr-areas"], queryFn: gardnrApi.listAreas });

  const createMutation = useMutation({
    // No x/y: the plant exists without a map position, and the map lists it for placing later.
    mutationFn: (input: NewPlantInput) =>
      gardnrApi.createPlant({ area_id: input.areaId!, name: input.name, type: input.type, species: input.species || undefined }),
    onSuccess: (plant) => {
      queryClient.invalidateQueries({ queryKey: ["gardnr-plants"] });
      queryClient.invalidateQueries({ queryKey: ["gardnr-areas"] });
      queryClient.invalidateQueries({ queryKey: ["gardnr-area", plant.area_id] });
      setAdding(false);
      setSelectedId(plant.id);
    },
  });

  // Filtered client-side: a personal garden is tens of plants, and the list already arrives
  // sorted soonest/most-overdue first, which the filters keep.
  const needle = search.trim().toLowerCase();
  const rows = (plantsQuery.data ?? []).filter(
    (p) =>
      (areaFilter === "all" || p.area_id === areaFilter) &&
      (statusFilter === "all" || p.status === statusFilter) &&
      (!needle || p.name.toLowerCase().includes(needle) || (p.species ?? "").toLowerCase().includes(needle)),
  );
  const filtering = needle !== "" || areaFilter !== "all" || statusFilter !== "all";

  const emptyText = filtering
    ? "Geen planten die hierop passen."
    : "Nog geen planten — voeg er een toe met Nieuwe plant, of vanaf de kaart van een tuin.";

  return (
    <div className="flex flex-col gap-4">
      {/* Not drawn in the redesign itself, but it shares its shell: the switcher row on a phone
          and the design's display heading. */}
      <GardnrTopRow>
        <button type="button" onClick={() => setAdding(true)} className={`${secondaryButtonClass} hidden sm:inline-flex`}>
          Nieuwe plant
        </button>
      </GardnrTopRow>
      <PageTitle>Planten</PageTitle>

      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Zoek op naam of soort"
          aria-label="Zoeken"
          className={`${inputClass} min-w-0 flex-1 basis-full sm:basis-48`}
        />
        <select
          value={areaFilter}
          onChange={(e) => setAreaFilter(e.target.value === "all" ? "all" : Number(e.target.value))}
          aria-label="Tuin"
          className={`${inputClass} flex-1 sm:flex-none`}
        >
          <option value="all">Alle tuinen</option>
          {areasQuery.data?.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as GardenPlantStatus | "all")}
          aria-label="Status"
          className={`${inputClass} flex-1 sm:flex-none`}
        >
          <option value="all">Elke status</option>
          {GARDEN_PLANT_STATUSES.map((s) => (
            <option key={s} value={s}>
              {GARDEN_PLANT_STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 py-2 text-sm text-slate-500">
          <input type="checkbox" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} />
          Toon gearchiveerd
        </label>
      </div>

      {plantsQuery.isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-400">Laden…</div>
      ) : plantsQuery.isError ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">
          Planten konden niet worden geladen.{" "}
          <button onClick={() => plantsQuery.refetch()} className="font-medium text-slate-900 underline">
            Opnieuw proberen
          </button>
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-400">{emptyText}</div>
      ) : (
        <>
          {/* Phone: one tappable card per plant instead of a six-column table to scroll sideways. */}
          {/* Bottom padding so the last card can scroll clear of the floating "Nieuwe plant" button. */}
          <ul className="flex flex-col gap-2 pb-16 sm:hidden" aria-label="Planten">
            {rows.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(p.id)}
                  className={`flex w-full flex-col gap-0.5 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-left text-sm ${p.is_archived ? "opacity-50" : ""}`}
                >
                  <span className="flex items-center gap-1.5">
                    <span className="truncate font-medium text-slate-900">{p.name}</span>
                    {p.status !== "thriving" && <StatusDot status={p.status} />}
                  </span>
                  <span className="truncate text-xs text-slate-500">
                    {[p.species, p.area_name].filter(Boolean).join(" · ")}
                  </span>
                  <span className="text-xs">
                    <NextAction plant={p} emptyText="geen schema" />
                  </span>
                </button>
              </li>
            ))}
          </ul>

          <div className="hidden rounded-lg border border-slate-200 bg-white sm:block">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-4 py-2 font-medium">Naam</th>
                    <th className="px-4 py-2 font-medium">Soort</th>
                    <th className="px-4 py-2 font-medium">Type</th>
                    <th className="px-4 py-2 font-medium">Tuin</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Volgende actie</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr
                      key={p.id}
                      onClick={() => setSelectedId(p.id)}
                      className={`cursor-pointer border-b border-slate-50 last:border-0 hover:bg-slate-50 ${p.is_archived ? "opacity-50" : ""}`}
                    >
                      <td className="px-4 py-2 font-medium text-slate-900">{p.name}</td>
                      <td className="px-4 py-2 text-slate-600">{p.species ?? "—"}</td>
                      <td className="px-4 py-2 text-slate-600">{GARDEN_PLANT_TYPE_LABELS[p.type]}</td>
                      <td className="px-4 py-2 text-slate-600">{p.area_name}</td>
                      <td className="px-4 py-2">
                        <span className="inline-flex items-center gap-1.5 text-slate-600">
                          <StatusDot status={p.status} />
                          {GARDEN_PLANT_STATUS_LABELS[p.status]}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <NextAction plant={p} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {adding && (
        <NewPlantDialog
          areas={areasQuery.data ?? []}
          hint="Hij komt nog niet op de kaart; zet hem er later op via Tuinen → Bewerken."
          onCancel={() => setAdding(false)}
          isSubmitting={createMutation.isPending}
          isError={createMutation.isError}
          onSubmit={(input) => createMutation.mutate(input)}
        />
      )}

      <MobileFab label="Nieuwe plant" onClick={() => setAdding(true)} />

      <PlantDetailPanel plantId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
