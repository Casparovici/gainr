import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, CheckCircle2, ImagePlus, Pencil, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { gardnrApi } from "../../api/gardnrClient";
import {
  GARDEN_ACTION_LABELS,
  GARDEN_ACTION_TYPES,
  GARDEN_FREQUENCY_UNIT_LABELS,
  GARDEN_PLANT_ICON_LABELS,
  GARDEN_PLANT_ICONS,
  GARDEN_PLANT_STATUS_DOT_CLASS,
  GARDEN_PLANT_STATUS_LABELS,
  GARDEN_PLANT_STATUSES,
  GARDEN_PLANT_TYPE_LABELS,
  GARDEN_PLANT_TYPES,
  GARDEN_SCHEDULE_FREQUENCIES,
  GARDEN_ZONE_SHAPE_LABELS,
  type GardenActionType,
  type GardenCareLog,
  type GardenCareSchedule,
  type GardenPlant,
  type GardenPlantDetail,
  type GardenPlantIcon,
  type GardenPlantStatus,
  type GardenPlantType,
  type GardenScheduleFrequency,
  type GardenZoneShape,
} from "../../api/gardnrTypes";
import { PLANT_ICON_COMPONENTS, resolvePlantIcon } from "./plantIcons";
import { actionLabel, dueText, gardnrDate, todayLocalISO } from "../../utils/gardnr";

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
// Icon-only row actions get padding (not a bigger icon) so they're a finger-sized target on a phone.
const iconButtonClass = "-m-1 rounded p-2";
const secondaryButtonClass = "rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50";

type Tab = "overview" | "care-log" | "schedule";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overzicht" },
  { id: "care-log", label: "Verzorging" },
  { id: "schedule", label: "Schema" },
];

function ActionBadge({ actionType, customLabel }: { actionType: GardenActionType; customLabel: string | null }) {
  return <span>{actionLabel(actionType, customLabel)}</span>;
}

function SaveError({ show, text = "Opslaan is mislukt — probeer het opnieuw." }: { show: boolean; text?: string }) {
  return show ? <p className="text-sm text-red-600">{text}</p> : null;
}

function invalidatePlant(queryClient: ReturnType<typeof useQueryClient>, plant: { id: number; area_id: number }) {
  queryClient.invalidateQueries({ queryKey: ["gardnr-plant", plant.id] });
  queryClient.invalidateQueries({ queryKey: ["gardnr-plants"] });
  queryClient.invalidateQueries({ queryKey: ["gardnr-area", plant.area_id] });
}

function frequencyLabel(frequency: GardenScheduleFrequency): string {
  return GARDEN_FREQUENCY_UNIT_LABELS[frequency];
}

// -- Overview tab -----------------------------------------------------------------------------

function IconPicker({ value, type, onSelect }: { value: GardenPlantIcon | null; type: GardenPlantType; onSelect: (icon: GardenPlantIcon) => void }) {
  const resolved = resolvePlantIcon(value, type);
  return (
    <div className="flex flex-wrap gap-1.5">
      {GARDEN_PLANT_ICONS.map((icon) => {
        const Icon = PLANT_ICON_COMPONENTS[icon];
        const selected = icon === resolved;
        return (
          <button
            key={icon}
            type="button"
            onClick={() => onSelect(icon)}
            title={GARDEN_PLANT_ICON_LABELS[icon]}
            className={`flex h-9 w-9 items-center justify-center rounded-md border ${
              selected ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 text-slate-600 hover:bg-slate-50"
            }`}
          >
            <Icon className="h-4 w-4" strokeWidth={2} />
          </button>
        );
      })}
    </div>
  );
}

function StatusPicker({ value, onSelect }: { value: GardenPlantStatus; onSelect: (status: GardenPlantStatus) => void }) {
  return (
    <div className="flex items-center gap-2">
      {GARDEN_PLANT_STATUSES.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => onSelect(s)}
          title={GARDEN_PLANT_STATUS_LABELS[s]}
          aria-label={GARDEN_PLANT_STATUS_LABELS[s]}
          className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
            value === s ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 text-slate-600 hover:bg-slate-50"
          }`}
        >
          <span className={`h-2 w-2 rounded-full ${GARDEN_PLANT_STATUS_DOT_CLASS[s]}`} />
          {GARDEN_PLANT_STATUS_LABELS[s]}
        </button>
      ))}
    </div>
  );
}

/** What the panel opens on: what's due (with one-tap "Gedaan" per schedule), recent care, and the
 * plant's facts -- read-only, since on a phone the common job is "I just watered this", not
 * editing its name. The edit form sits one tap away behind "Gegevens bewerken". */
function SummarySection({
  detail,
  onEdit,
  onShowTab,
}: {
  detail: GardenPlantDetail;
  onEdit: () => void;
  onShowTab: (tab: Tab, openForm?: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { plant, care_logs: logs, care_schedules: schedules } = detail;
  const active = schedules.filter((s) => s.is_active).sort((a, b) => a.next_due.localeCompare(b.next_due));

  const doneMutation = useMutation({
    mutationFn: (s: GardenCareSchedule) =>
      gardnrApi.createLog(plant.id, { action_type: s.action_type, custom_label: s.custom_label, performed_on: todayLocalISO(), notes: null }),
    onSuccess: () => invalidatePlant(queryClient, plant),
  });

  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Te doen</h3>
        {active.length === 0 ? (
          <p className="text-sm text-slate-400">
            Geen terugkerende verzorging.{" "}
            <button onClick={() => onShowTab("schedule", true)} className="font-medium text-slate-700 underline">
              Schema toevoegen
            </button>
          </p>
        ) : (
          <ul className="flex flex-col divide-y divide-slate-100">
            {active.map((s) => {
              const due = dueText(s.next_due);
              const pending = doneMutation.isPending && doneMutation.variables?.id === s.id;
              return (
                <li key={s.id} className="flex items-center justify-between gap-3 py-2">
                  <div className="min-w-0 text-sm">
                    <div className="font-medium text-slate-900">
                      <ActionBadge actionType={s.action_type} customLabel={s.custom_label} />
                    </div>
                    <div className={`text-xs ${due.isDue ? "font-medium text-red-600" : "text-slate-500"}`}>
                      {due.text} · elke {s.interval_value} {GARDEN_FREQUENCY_UNIT_LABELS[s.frequency]}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => doneMutation.mutate(s)}
                    disabled={pending}
                    className={`flex shrink-0 items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 ${
                      due.isDue ? "bg-slate-900 text-white hover:bg-slate-800" : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    <CheckCircle2 className="h-4 w-4" strokeWidth={2} />
                    Gedaan
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        <SaveError show={doneMutation.isError} text="Registreren is mislukt — probeer het opnieuw." />
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Recente verzorging</h3>
          <button onClick={() => onShowTab("care-log", true)} className="py-1 text-sm font-medium text-slate-700 hover:text-slate-900">
            + Actie registreren
          </button>
        </div>
        {logs.length === 0 ? (
          <p className="text-sm text-slate-400">Nog niets geregistreerd.</p>
        ) : (
          <ul className="flex flex-col gap-1 text-sm">
            {logs.slice(0, 3).map((log) => (
              <li key={log.id} className="flex items-baseline gap-2">
                <span className="font-medium text-slate-900">
                  <ActionBadge actionType={log.action_type} customLabel={log.custom_label} />
                </span>
                <span className="text-xs text-slate-400">{gardnrDate(log.performed_on)}</span>
                {log.notes && <span className="min-w-0 truncate text-slate-500">{log.notes}</span>}
              </li>
            ))}
            {logs.length > 3 && (
              <li>
                <button onClick={() => onShowTab("care-log")} className="py-1 text-sm text-slate-500 underline hover:text-slate-900">
                  Alle {logs.length} registraties bekijken
                </button>
              </li>
            )}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-1.5 text-sm">
        <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Gegevens</h3>
        <div className="flex items-center gap-1.5 text-slate-700">
          <span className={`h-2 w-2 rounded-full ${GARDEN_PLANT_STATUS_DOT_CLASS[plant.status]}`} />
          {GARDEN_PLANT_STATUS_LABELS[plant.status]} · {GARDEN_PLANT_TYPE_LABELS[plant.type]}
          {plant.species && <span className="text-slate-500">· {plant.species}</span>}
        </div>
        {plant.planted_date && <div className="text-slate-500">Geplant op {gardnrDate(plant.planted_date)}</div>}
        {plant.notes && <p className="whitespace-pre-line text-slate-600">{plant.notes}</p>}
        <button onClick={onEdit} className={`mt-1 flex items-center gap-1.5 self-start ${secondaryButtonClass}`}>
          <Pencil className="h-4 w-4" strokeWidth={2} /> Gegevens bewerken
        </button>
      </section>
    </div>
  );
}

function PlantEditForm({ plant, onDone, onDeleted }: { plant: GardenPlant; onDone: () => void; onDeleted: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: plant.name,
    species: plant.species ?? "",
    type: plant.type,
    planted_date: plant.planted_date ?? "",
    notes: plant.notes ?? "",
    icon: plant.icon,
    marker_shape: plant.marker_shape,
    status: plant.status,
  });

  useEffect(() => {
    setForm({
      name: plant.name,
      species: plant.species ?? "",
      type: plant.type,
      planted_date: plant.planted_date ?? "",
      notes: plant.notes ?? "",
      icon: plant.icon,
      marker_shape: plant.marker_shape,
      status: plant.status,
    });
    // Only when another plant opens: an edit in progress isn't overwritten by a background refetch
    // of the same plant.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plant.id]);

  const updateMutation = useMutation({
    mutationFn: () =>
      gardnrApi.updatePlant(plant.id, {
        name: form.name,
        species: form.species || null,
        type: form.type,
        planted_date: form.planted_date || null,
        notes: form.notes || null,
        icon: form.icon,
        marker_shape: form.marker_shape,
        // No marker_width/height: size is dragged on the map, and sending this form's copy of it
        // would quietly undo a resize made there after the panel was opened.
        status: form.status,
      }),
    onSuccess: () => {
      invalidatePlant(queryClient, plant);
      onDone();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => gardnrApi.deletePlant(plant.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["gardnr-plants"] });
      queryClient.invalidateQueries({ queryKey: ["gardnr-area", plant.area_id] });
      onDeleted();
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        updateMutation.mutate();
      }}
      className="flex flex-col gap-3"
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Naam</span>
        <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} className={inputClass} />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Soort</span>
        <input value={form.species} onChange={(e) => setForm((f) => ({ ...f, species: e.target.value }))} className={inputClass} />
      </label>
      <div className="flex flex-col gap-1 text-sm">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Status</span>
        <StatusPicker value={form.status} onSelect={(status) => setForm((f) => ({ ...f, status }))} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Type</span>
          <select
            value={form.type}
            onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as GardenPlantType }))}
            className={inputClass}
          >
            {GARDEN_PLANT_TYPES.map((t) => (
              <option key={t} value={t}>
                {GARDEN_PLANT_TYPE_LABELS[t]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Geplant</span>
          <input
            type="date"
            value={form.planted_date}
            onChange={(e) => setForm((f) => ({ ...f, planted_date: e.target.value }))}
            className={inputClass}
          />
        </label>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Notities</span>
        <textarea
          value={form.notes}
          onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
          rows={4}
          className={inputClass}
        />
      </label>

      <div className="flex flex-col gap-2 rounded-lg border border-slate-200 p-3">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Weergave op de kaart</span>
        <IconPicker value={form.icon} type={form.type} onSelect={(icon) => setForm((f) => ({ ...f, icon }))} />
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={form.marker_shape}
            onChange={(e) => setForm((f) => ({ ...f, marker_shape: e.target.value as GardenZoneShape }))}
            className={inputClass}
          >
            <option value="rect">{GARDEN_ZONE_SHAPE_LABELS.rect}</option>
            <option value="circle">{GARDEN_ZONE_SHAPE_LABELS.circle}</option>
          </select>
          <span className="text-xs text-slate-500">Formaat: sleep op de kaart (Bewerken) het hoekje rechtsonder.</span>
        </div>
      </div>

      <SaveError show={updateMutation.isError || deleteMutation.isError} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => {
            if (confirm(`${plant.name} verwijderen? De verzorgingsgeschiedenis en het schema verdwijnen mee.`)) deleteMutation.mutate();
          }}
          className="py-2 text-sm font-medium text-red-600 hover:text-red-800"
        >
          Plant verwijderen
        </button>
        <div className="flex gap-2">
          <button type="button" onClick={onDone} className={secondaryButtonClass}>
            Annuleren
          </button>
          <button
            type="submit"
            disabled={updateMutation.isPending}
            className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {updateMutation.isPending ? "Opslaan…" : "Opslaan"}
          </button>
        </div>
      </div>
    </form>
  );
}

// -- Care log tab -----------------------------------------------------------------------------

function LogForm({
  initial,
  onCancel,
  onSubmit,
  isSubmitting,
}: {
  initial: GardenCareLog | undefined;
  onCancel: () => void;
  onSubmit: (
    input: { action_type: GardenActionType; custom_label: string | null; performed_on: string; notes: string | null },
    photo: File | null,
  ) => void;
  isSubmitting: boolean;
}) {
  const [actionType, setActionType] = useState<GardenActionType>(initial?.action_type ?? "water");
  const [customLabel, setCustomLabel] = useState(initial?.custom_label ?? "");
  const [performedOn, setPerformedOn] = useState(initial?.performed_on ?? todayLocalISO());
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [photo, setPhoto] = useState<File | null>(null);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(
          { action_type: actionType, custom_label: actionType === "other" ? customLabel || null : null, performed_on: performedOn, notes: notes || null },
          photo,
        );
      }}
      className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3"
    >
      <div className="grid grid-cols-2 gap-2">
        <select value={actionType} onChange={(e) => setActionType(e.target.value as GardenActionType)} className={inputClass}>
          {GARDEN_ACTION_TYPES.map((t) => (
            <option key={t} value={t}>
              {GARDEN_ACTION_LABELS[t]}
            </option>
          ))}
        </select>
        <input type="date" required value={performedOn} onChange={(e) => setPerformedOn(e.target.value)} className={inputClass} />
      </div>
      {actionType === "other" && (
        <input
          value={customLabel}
          onChange={(e) => setCustomLabel(e.target.value)}
          placeholder="Wat heb je gedaan?"
          className={inputClass}
        />
      )}
      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notities (optioneel)" rows={2} className={inputClass} />
      <div className="flex flex-col gap-1.5 text-xs text-slate-500">
        <span>{initial?.has_photo ? "Nieuwe foto (vervangt de huidige)" : "Foto (optioneel)"}</span>
        {/* Two inputs rather than one: `capture` sends a phone straight to the camera, which is
            the usual case in the garden, but would then hide the gallery for an older photo. */}
        <div className="flex flex-wrap items-center gap-2">
          <label className={`flex cursor-pointer items-center gap-1.5 ${secondaryButtonClass}`}>
            <Camera className="h-4 w-4" strokeWidth={2} /> Foto maken
            <input type="file" accept="image/*" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} className="sr-only" />
          </label>
          <label className={`flex cursor-pointer items-center gap-1.5 ${secondaryButtonClass}`}>
            <ImagePlus className="h-4 w-4" strokeWidth={2} /> Kies foto
            <input type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} className="sr-only" />
          </label>
          {photo && <span className="min-w-0 truncate text-slate-600">{photo.name}</span>}
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="rounded-md px-3 py-2 text-sm font-medium text-slate-500 hover:text-slate-900">
          Annuleren
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {isSubmitting ? "Opslaan…" : "Opslaan"}
        </button>
      </div>
    </form>
  );
}

function CareLogSection({ plantId, openForm }: { plantId: number; openForm: boolean }) {
  const queryClient = useQueryClient();
  // null = list only, undefined = new-entry form, a log = editing that entry.
  const [editing, setEditing] = useState<GardenCareLog | undefined | null>(openForm ? undefined : null);

  const logsQuery = useQuery({ queryKey: ["gardnr-plant", plantId], queryFn: () => gardnrApi.getPlantDetail(plantId) });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["gardnr-plant", plantId] });
    queryClient.invalidateQueries({ queryKey: ["gardnr-plants"] });
    // The map's markers carry last/next action too; the area id isn't known here, so refresh any.
    queryClient.invalidateQueries({ queryKey: ["gardnr-area"] });
  };

  const createMutation = useMutation({
    mutationFn: async ({ input, photo }: { input: Omit<GardenCareLog, "id" | "plant_id" | "has_photo">; photo: File | null }) => {
      const log = await gardnrApi.createLog(plantId, input);
      if (photo) await gardnrApi.setLogPhoto(log.id, photo);
    },
    onSuccess: () => {
      invalidate();
      setEditing(null);
    },
  });
  const updateMutation = useMutation({
    mutationFn: async ({
      id,
      input,
      photo,
    }: {
      id: number;
      input: Partial<Omit<GardenCareLog, "id" | "plant_id" | "has_photo">>;
      photo: File | null;
    }) => {
      await gardnrApi.updateLog(id, input);
      if (photo) await gardnrApi.setLogPhoto(id, photo);
    },
    onSuccess: () => {
      invalidate();
      setEditing(null);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => gardnrApi.deleteLog(id),
    onSuccess: invalidate,
  });
  const deletePhotoMutation = useMutation({
    mutationFn: (id: number) => gardnrApi.deleteLogPhoto(id),
    onSuccess: invalidate,
  });
  const [lightboxLogId, setLightboxLogId] = useState<number | null>(null);

  const logs = logsQuery.data?.care_logs ?? [];

  return (
    <div className="flex flex-col gap-3">
      {editing === undefined && (
        <LogForm
          initial={undefined}
          onCancel={() => setEditing(null)}
          isSubmitting={createMutation.isPending}
          onSubmit={(input, photo) => createMutation.mutate({ input, photo })}
        />
      )}
      {editing && (
        <LogForm
          initial={editing}
          onCancel={() => setEditing(null)}
          isSubmitting={updateMutation.isPending}
          onSubmit={(input, photo) => updateMutation.mutate({ id: editing.id, input, photo })}
        />
      )}
      {editing === null && (
        <button onClick={() => setEditing(undefined)} className={`self-start ${secondaryButtonClass}`}>
          + Actie registreren
        </button>
      )}
      <SaveError show={createMutation.isError || updateMutation.isError || deleteMutation.isError || deletePhotoMutation.isError} />

      {logsQuery.isLoading ? (
        <div className="py-4 text-center text-sm text-slate-400">Laden…</div>
      ) : logsQuery.isError ? (
        <div className="py-4 text-center text-sm text-slate-500">Het logboek kon niet worden geladen.</div>
      ) : logs.length === 0 ? (
        <div className="py-4 text-center text-sm text-slate-400">Nog geen verzorging geregistreerd — leg vast wat je hebt gedaan en wanneer.</div>
      ) : (
        <div className="flex flex-col divide-y divide-slate-100">
          {logs.map((log) => (
            <article key={log.id} className="flex items-start justify-between gap-2 py-2.5">
              <div className="flex min-w-0 items-start gap-2.5">
                {log.has_photo && (
                  <button
                    type="button"
                    onClick={() => setLightboxLogId(log.id)}
                    className="h-11 w-11 shrink-0 overflow-hidden rounded-md border border-slate-200"
                    aria-label="Foto bekijken"
                  >
                    <img src={gardnrApi.logPhotoUrl(log.id)} alt="" className="h-full w-full object-cover" />
                  </button>
                )}
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2 text-sm">
                    <span className="font-medium text-slate-900">
                      <ActionBadge actionType={log.action_type} customLabel={log.custom_label} />
                    </span>
                    <span className="text-xs text-slate-400">{gardnrDate(log.performed_on)}</span>
                  </div>
                  {log.notes && <div className="mt-0.5 text-sm text-slate-600">{log.notes}</div>}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button onClick={() => setEditing(log)} className={`${iconButtonClass} text-slate-500 hover:text-slate-900`} title="Bewerken" aria-label="Bewerken">
                  <Pencil className="h-4 w-4" strokeWidth={2} />
                </button>
                <button
                  onClick={() => {
                    if (confirm("Deze registratie verwijderen?")) deleteMutation.mutate(log.id);
                  }}
                  className={`${iconButtonClass} text-red-500 hover:text-red-700`}
                  title="Verwijderen"
                  aria-label="Verwijderen"
                >
                  <Trash2 className="h-4 w-4" strokeWidth={2} />
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {lightboxLogId !== null && (
        <div
          onClick={() => setLightboxLogId(null)}
          className="fixed inset-0 z-[60] flex cursor-zoom-out items-center justify-center bg-slate-900/80 p-6"
        >
          <img src={gardnrApi.logPhotoUrl(lightboxLogId)} alt="" className="max-h-full max-w-full rounded-lg object-contain" />
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              if (confirm("Deze foto verwijderen?")) {
                deletePhotoMutation.mutate(lightboxLogId);
                setLightboxLogId(null);
              }
            }}
            className="absolute right-6 top-6 rounded-md bg-white/90 px-2.5 py-1.5 text-xs font-medium text-red-600 hover:bg-white"
          >
            Foto verwijderen
          </button>
        </div>
      )}
    </div>
  );
}

// -- Schedule tab -----------------------------------------------------------------------------

function ScheduleForm({
  initial,
  onCancel,
  onSubmit,
  isSubmitting,
}: {
  /** The schedule being edited; omitted when adding a new one. */
  initial?: GardenCareSchedule;
  onCancel: () => void;
  onSubmit: (input: {
    action_type: GardenActionType;
    custom_label: string | null;
    interval_value: number;
    frequency: GardenScheduleFrequency;
    is_active: boolean;
    start_date: string | null;
    notes: string | null;
  }) => void;
  isSubmitting: boolean;
}) {
  const [actionType, setActionType] = useState<GardenActionType>(initial?.action_type ?? "water");
  const [customLabel, setCustomLabel] = useState(initial?.custom_label ?? "");
  const [interval, setInterval] = useState(String(initial?.interval_value ?? 3));
  const [frequency, setFrequency] = useState<GardenScheduleFrequency>(initial?.frequency ?? "daily");
  const [startDate, setStartDate] = useState(initial?.start_date ?? "");

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          action_type: actionType,
          custom_label: actionType === "other" ? customLabel || null : null,
          interval_value: Math.max(1, Number(interval) || 1),
          frequency,
          is_active: initial?.is_active ?? true,
          start_date: startDate || null,
          notes: initial?.notes ?? null,
        });
      }}
      className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3"
    >
      <select value={actionType} onChange={(e) => setActionType(e.target.value as GardenActionType)} className={inputClass}>
        {GARDEN_ACTION_TYPES.map((t) => (
          <option key={t} value={t}>
            {GARDEN_ACTION_LABELS[t]}
          </option>
        ))}
      </select>
      {actionType === "other" && (
        <input
          value={customLabel}
          onChange={(e) => setCustomLabel(e.target.value)}
          placeholder="Wat is het?"
          className={inputClass}
        />
      )}
      <div className="flex items-center gap-1.5">
        <span className="shrink-0 text-sm text-slate-500">elke</span>
        <input type="number" min={1} required value={interval} onChange={(e) => setInterval(e.target.value)} className={`${inputClass} w-16`} />
        <select value={frequency} onChange={(e) => setFrequency(e.target.value as GardenScheduleFrequency)} className={`${inputClass} flex-1`}>
          {GARDEN_SCHEDULE_FREQUENCIES.map((f) => (
            <option key={f} value={f}>
              {frequencyLabel(f)}
            </option>
          ))}
        </select>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Eerste keer (optioneel)</span>
        <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className={inputClass} />
      </label>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="rounded-md px-3 py-2 text-sm font-medium text-slate-500 hover:text-slate-900">
          Annuleren
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {isSubmitting ? "Opslaan…" : "Opslaan"}
        </button>
      </div>
    </form>
  );
}

function ScheduleSection({ plantId, openForm }: { plantId: number; openForm: boolean }) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(openForm);
  const [editingId, setEditingId] = useState<number | null>(null);

  const detailQuery = useQuery({ queryKey: ["gardnr-plant", plantId], queryFn: () => gardnrApi.getPlantDetail(plantId) });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["gardnr-plant", plantId] });
    queryClient.invalidateQueries({ queryKey: ["gardnr-plants"] });
    // The map's markers carry last/next action too; the area id isn't known here, so refresh any.
    queryClient.invalidateQueries({ queryKey: ["gardnr-area"] });
  };

  const createMutation = useMutation({
    mutationFn: (input: Omit<GardenCareSchedule, "id" | "plant_id" | "next_due" | "is_overdue">) => gardnrApi.createSchedule(plantId, input),
    onSuccess: () => {
      invalidate();
      setAdding(false);
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: Omit<GardenCareSchedule, "id" | "plant_id" | "next_due" | "is_overdue"> }) =>
      gardnrApi.updateSchedule(id, input),
    onSuccess: () => {
      invalidate();
      setEditingId(null);
    },
  });
  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) => gardnrApi.updateSchedule(id, { is_active }),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => gardnrApi.deleteSchedule(id),
    onSuccess: invalidate,
  });

  const schedules = detailQuery.data?.care_schedules ?? [];

  return (
    <div className="flex flex-col gap-3">
      {adding && (
        <ScheduleForm onCancel={() => setAdding(false)} isSubmitting={createMutation.isPending} onSubmit={(input) => createMutation.mutate(input)} />
      )}
      {!adding && (
        <button onClick={() => setAdding(true)} className={`self-start ${secondaryButtonClass}`}>
          + Schema toevoegen
        </button>
      )}
      <SaveError show={createMutation.isError || updateMutation.isError || toggleActiveMutation.isError || deleteMutation.isError} />

      {detailQuery.isLoading ? (
        <div className="py-4 text-center text-sm text-slate-400">Laden…</div>
      ) : detailQuery.isError ? (
        <div className="py-4 text-center text-sm text-slate-500">Het schema kon niet worden geladen.</div>
      ) : schedules.length === 0 ? (
        <div className="py-4 text-center text-sm text-slate-400">
          Nog geen terugkerende verzorging ingesteld — voeg er een toe om een herinnering te krijgen.
        </div>
      ) : (
        <div className="flex flex-col divide-y divide-slate-100">
          {schedules.map((s) =>
            editingId === s.id ? (
              <div key={s.id} className="py-2.5">
                <ScheduleForm
                  initial={s}
                  onCancel={() => setEditingId(null)}
                  isSubmitting={updateMutation.isPending}
                  onSubmit={(input) => updateMutation.mutate({ id: s.id, input })}
                />
              </div>
            ) : (
            <div key={s.id} className={`flex items-center justify-between gap-2 py-2.5 ${s.is_active ? "" : "opacity-50"}`}>
              <div className="min-w-0">
                <div className="text-sm font-medium text-slate-900">
                  <ActionBadge actionType={s.action_type} customLabel={s.custom_label} /> elke {s.interval_value} {frequencyLabel(s.frequency)}
                </div>
                <div className={`text-xs ${s.is_overdue && s.is_active ? "font-medium text-red-600" : "text-slate-400"}`}>
                  {s.is_active ? `Volgende: ${dueText(s.next_due).text}` : "gepauzeerd"}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  onClick={() => setEditingId(s.id)}
                  className={`${iconButtonClass} text-slate-500 hover:text-slate-900`}
                  title="Bewerken"
                  aria-label="Schema bewerken"
                >
                  <Pencil className="h-4 w-4" strokeWidth={2} />
                </button>
                <button
                  onClick={() => toggleActiveMutation.mutate({ id: s.id, is_active: !s.is_active })}
                  className="px-2 py-2 text-sm font-medium text-slate-500 hover:text-slate-900"
                >
                  {s.is_active ? "Pauzeren" : "Hervatten"}
                </button>
                <button
                  onClick={() => {
                    if (confirm("Dit schema verwijderen?")) deleteMutation.mutate(s.id);
                  }}
                  className={`${iconButtonClass} text-red-500 hover:text-red-700`}
                  title="Verwijderen"
                  aria-label="Verwijderen"
                >
                  <Trash2 className="h-4 w-4" strokeWidth={2} />
                </button>
              </div>
            </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}

// -- Panel shell ------------------------------------------------------------------------------

export default function PlantDetailPanel({ plantId, onClose }: { plantId: number | null; onClose: () => void }) {
  const [shown, setShown] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [editingDetails, setEditingDetails] = useState(false);
  // Set when the summary sends you to a tab to add something, so that tab opens with its form.
  const [openFormOn, setOpenFormOn] = useState<Tab | null>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const open = plantId !== null;

  useEffect(() => {
    if (!plantId) return;
    setShown(plantId);
    setTab("overview");
    setEditingDetails(false);
    setOpenFormOn(null);
    closeButton.current?.focus();
  }, [plantId]);

  function showTab(next: Tab, openForm = false) {
    setTab(next);
    setOpenFormOn(openForm ? next : null);
  }

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const detailQuery = useQuery({
    queryKey: ["gardnr-plant", shown],
    queryFn: () => gardnrApi.getPlantDetail(shown as number),
    enabled: shown !== null,
  });

  if (!shown) return null;
  const plant = detailQuery.data?.plant;

  return (
    <>
      <div
        onClick={onClose}
        aria-hidden
        className={`fixed inset-0 z-40 bg-slate-900/20 transition-opacity duration-200 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={plant ? `${plant.name} details` : "Plantgegevens"}
        aria-hidden={!open}
        // The shadow only while open: parked off-screen, it would still bleed in along the right edge.
        className={`fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-slate-200 bg-white transition-transform duration-200 ease-out sm:max-w-xl ${
          open ? "translate-x-0 shadow-2xl" : "pointer-events-none translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <h2 className="flex items-center gap-2 truncate text-base font-semibold text-slate-900">
            {plant?.name ?? "…"}
            {plant && plant.status !== "thriving" && (
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${GARDEN_PLANT_STATUS_DOT_CLASS[plant.status]}`}
                title={GARDEN_PLANT_STATUS_LABELS[plant.status]}
              />
            )}
          </h2>
          <button ref={closeButton} onClick={onClose} className="-m-2 p-2 text-slate-400 hover:text-slate-700" aria-label="Sluiten">
            ✕
          </button>
        </div>

        <nav className="flex gap-4 border-b border-slate-200 px-5" aria-label="Plantonderdelen">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => showTab(t.id)}
              aria-current={tab === t.id}
              className={`-mb-px border-b-2 py-2.5 text-sm font-medium transition-colors ${
                tab === t.id ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {detailQuery.isError ? (
            <div className="py-4 text-center text-sm text-slate-500">
              Deze plant kon niet worden geladen.{" "}
              <button onClick={() => detailQuery.refetch()} className="font-medium text-slate-900 underline">
                Opnieuw proberen
              </button>
            </div>
          ) : !plant || !detailQuery.data ? (
            <div className="py-4 text-center text-sm text-slate-400">Laden…</div>
          ) : tab === "overview" ? (
            editingDetails ? (
              <PlantEditForm plant={plant} onDone={() => setEditingDetails(false)} onDeleted={onClose} />
            ) : (
              <SummarySection detail={detailQuery.data} onEdit={() => setEditingDetails(true)} onShowTab={showTab} />
            )
          ) : tab === "care-log" ? (
            <CareLogSection key={`log-${plant.id}-${openFormOn === "care-log"}`} plantId={plant.id} openForm={openFormOn === "care-log"} />
          ) : (
            <ScheduleSection key={`schedule-${plant.id}-${openFormOn === "schedule"}`} plantId={plant.id} openForm={openFormOn === "schedule"} />
          )}
        </div>
      </aside>
    </>
  );
}
