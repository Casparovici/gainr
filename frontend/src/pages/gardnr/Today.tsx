import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useCallback, useState } from "react";

import { gardnrApi } from "../../api/gardnrClient";
import { GardnrTopRow, PageTitle } from "../../components/gardnr/ui";
import type { GardenActionSummary, GardenCareLog, GardenPlantListRow } from "../../api/gardnrTypes";
import UndoToast from "../../components/UndoToast";
import PlantDetailPanel from "../../components/gardnr/PlantDetailPanel";
import { actionLabel, dueBucket, dueText, SOON_DAYS, todayLocalISO } from "../../utils/gardnr";
import { msg, t } from "../../i18n";

type Bucket = "late" | "today" | "soon";

interface DueItem {
  key: string;
  plant: GardenPlantListRow;
  action: GardenActionSummary;
}

const SECTIONS: { bucket: Bucket; title: string }[] = [
  { bucket: "late", title: msg("Te laat") },
  { bucket: "today", title: msg("Vandaag") },
  // "{days}" is filled in where the title is shown.
  { bucket: "soon", title: msg("Binnenkort ({days} dagen)") },
];

/** Every scheduled action (not just each plant's soonest) that's late, due today or due within a
 * week, bucketed by urgency and ordered by date within each bucket. */
function bucketActions(plants: GardenPlantListRow[], today: string): Record<Bucket, DueItem[]> {
  const buckets: Record<Bucket, DueItem[]> = { late: [], today: [], soon: [] };
  for (const plant of plants) {
    for (const action of plant.scheduled_actions) {
      const bucket = dueBucket(action.date, today);
      if (bucket) buckets[bucket].push({ key: `${plant.id}-${action.schedule_id}`, plant, action });
    }
  }
  for (const items of Object.values(buckets)) {
    items.sort((a, b) => a.action.date.localeCompare(b.action.date) || a.plant.name.localeCompare(b.plant.name));
  }
  return buckets;
}

export default function GardnrToday() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [lastDone, setLastDone] = useState<{ log: GardenCareLog; item: DueItem } | null>(null);

  const plantsQuery = useQuery({ queryKey: ["gardnr-plants", false], queryFn: () => gardnrApi.listPlants(false) });

  const invalidate = (item: DueItem) => {
    queryClient.invalidateQueries({ queryKey: ["gardnr-plants"] });
    queryClient.invalidateQueries({ queryKey: ["gardnr-plant", item.plant.id] });
    queryClient.invalidateQueries({ queryKey: ["gardnr-area", item.plant.area_id] });
  };

  const logDoneMutation = useMutation({
    mutationFn: (item: DueItem) =>
      gardnrApi.createLog(item.plant.id, {
        action_type: item.action.action_type,
        custom_label: item.action.custom_label,
        performed_on: todayLocalISO(),
        notes: null,
      }),
    onSuccess: (log, item) => {
      invalidate(item);
      setLastDone({ log, item });
    },
  });

  const undoMutation = useMutation({
    mutationFn: (done: { log: GardenCareLog; item: DueItem }) => gardnrApi.deleteLog(done.log.id),
    onSuccess: (_data, done) => invalidate(done.item),
  });

  const dismissToast = useCallback(() => setLastDone(null), []);

  const today = todayLocalISO();
  const buckets = bucketActions(plantsQuery.data ?? [], today);
  const nothingDue = buckets.late.length === 0 && buckets.today.length === 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Not drawn in the redesign itself, but it shares its shell: the switcher row on a phone
          and the design's display heading. */}
      <GardnrTopRow />
      <PageTitle>{t("Vandaag")}</PageTitle>

      {plantsQuery.isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-400">{t("Laden…")}</div>
      ) : plantsQuery.isError ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">{t("Kon niet laden wat er vandaag te doen is.")}{" "}
          <button onClick={() => plantsQuery.refetch()} className="font-medium text-slate-900 underline">{t("Opnieuw proberen")}</button>
        </div>
      ) : (
        <>
          {nothingDue && (
            <div className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-400">{t("Niets te doen vandaag — elke tuin is bij.")}</div>
          )}
          {SECTIONS.map(({ bucket, title }) =>
            buckets[bucket].length === 0 ? null : (
              <section key={bucket} aria-label={t(title, { days: SOON_DAYS })} className="rounded-lg border border-slate-200 bg-white">
                <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2.5">
                  <h2 className={`text-sm font-medium ${bucket === "soon" ? "text-slate-500" : "text-slate-700"}`}>{t(title, { days: SOON_DAYS })}</h2>
                  <span className="ml-auto text-xs text-slate-400">{buckets[bucket].length}</span>
                </div>
                <ul className="divide-y divide-slate-50">
                  {buckets[bucket].map((item) => {
                    const due = dueText(item.action.date, today);
                    const pending = logDoneMutation.isPending && logDoneMutation.variables?.key === item.key;
                    return (
                      <li key={item.key} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                        <button type="button" onClick={() => setSelectedId(item.plant.id)} className="min-w-0 py-1 text-left hover:underline">
                          <span className="font-medium text-slate-900">{item.plant.name}</span>{" "}
                          <span className={due.isDue ? "text-red-600" : "text-slate-600"}>
                            {actionLabel(item.action.action_type, item.action.custom_label)}
                            {bucket !== "today" && ` · ${due.text}`}
                          </span>
                          <span className="block text-xs text-slate-400">{item.plant.area_name}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => logDoneMutation.mutate(item)}
                          // Only the row being logged waits; the rest of the list stays tappable.
                          disabled={pending}
                          className={`flex shrink-0 items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 ${
                            bucket === "soon" ? "border border-slate-300 text-slate-700 hover:bg-slate-50" : "bg-slate-900 text-white hover:bg-slate-800"
                          }`}
                        >
                          <CheckCircle2 className="h-4 w-4" strokeWidth={2} />
                          {bucket === "soon" ? t("Nu al gedaan") : t("Gedaan")}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ),
          )}
        </>
      )}

      {(logDoneMutation.isError || undoMutation.isError) && (
        <p className="text-sm text-red-600">{undoMutation.isError ? t("Ongedaan maken is mislukt — probeer het opnieuw.") : t("Registreren is mislukt — probeer het opnieuw.")}</p>
      )}

      {lastDone && (
        <UndoToast
          message={t("{action} geregistreerd voor {plant}.", {
            action: actionLabel(lastDone.item.action.action_type, lastDone.item.action.custom_label),
            plant: lastDone.item.plant.name,
          })}
          onUndo={() => {
            undoMutation.mutate(lastDone);
            setLastDone(null);
          }}
          onDismiss={dismissToast}
        />
      )}

      <PlantDetailPanel plantId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
