import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { taskrApi } from "../../api/taskrClient";
import type { AgendaItem, TaskrTaskInput } from "../../api/taskrTypes";
import { AgendaSection, type TaskActions } from "../../components/taskr/AgendaList";
import TaskDialog from "../../components/taskr/TaskDialog";
import UndoToast from "../../components/UndoToast";
import InfoHeading from "../../components/ui/InfoTip";
import {
  IconChevronLeft,
  IconChevronRight,
  ModuleTopRow,
  iconButtonClass,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "../../components/ui/kit";
import { AGENDA_VIEWS, AGENDA_VIEW_LABELS, agendaRange, dayLabel, overdueTitle, rangeLabel, shiftStart, type AgendaView } from "../../utils/taskr";
import { toIso } from "../../utils/weekCalendar";
import { t } from "../../i18n";

const cardClass = "rounded-2xl border border-ui-border bg-ui-surface px-4 py-6 text-center text-sm text-ui-muted";

/** taskr's agenda: what's due across gardnr and trainr, plus the tasks added here. Overdue first,
 * then one card per day that has something on it (the backend does the grouping). A module's item
 * links to where it's done; a taskr task is added in the row on top, ticked off with its circle
 * (with an undo) and changed by tapping its title. `today` is injectable so tests don't depend on
 * the clock; the app passes nothing and gets the browser's local date. */
export default function TaskrAgenda({ today: todayOverride }: { today?: string } = {}) {
  const today = todayOverride ?? toIso(new Date());
  const [view, setView] = useState<AgendaView>("week");
  // null = "start today", so the page follows the date instead of pinning the day it was opened.
  const [start, setStart] = useState<string | null>(null);
  const from = start ?? today;
  const range = agendaRange(view, from);
  const queryClient = useQueryClient();
  const [newTitle, setNewTitle] = useState("");
  // null = the first day on screen, so paging ahead and adding puts the task in view.
  const [newDate, setNewDate] = useState<string | null>(null);
  const [editing, setEditing] = useState<AgendaItem | null>(null);
  const [ticked, setTicked] = useState<AgendaItem | null>(null);
  const dismissToast = useCallback(() => setTicked(null), []);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["taskr-agenda"] });

  const add = useMutation({
    mutationFn: (input: TaskrTaskInput) => taskrApi.createTask(input),
    onSuccess: () => {
      setNewTitle("");
      setNewDate(null);
      return refresh();
    },
  });
  const complete = useMutation({
    mutationFn: ({ id, done }: { id: number; done: boolean }) => taskrApi.setTaskCompleted(id, done),
    onSuccess: refresh,
  });
  const save = useMutation({
    mutationFn: ({ id, input }: { id: number; input: TaskrTaskInput }) => taskrApi.updateTask(id, input),
    onSuccess: () => {
      setEditing(null);
      return refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => taskrApi.deleteTask(id),
    onSuccess: () => {
      setEditing(null);
      return refresh();
    },
  });

  const actions: TaskActions = {
    onComplete: (item) => {
      if (item.task_id === null) return;
      complete.mutate({ id: item.task_id, done: true }, { onSuccess: () => setTicked(item) });
    },
    onEdit: (item) => {
      save.reset();
      remove.reset();
      setEditing(item);
    },
  };

  const agendaQuery = useQuery({
    queryKey: ["taskr-agenda", range.from, range.to],
    queryFn: () => taskrApi.getAgenda(range.from, range.to),
    // Items are completed in their own module, whose mutations don't know about this key; always
    // refetch when the page is opened again so a care action logged a minute ago is gone.
    staleTime: 0,
    // Keep the previous window on screen (dimmed) while the next one loads.
    placeholderData: keepPreviousData,
  });

  const agenda = agendaQuery.data;
  const upcomingCount = agenda?.days.reduce((n, d) => n + d.items.length, 0) ?? 0;
  const lateCount = agenda?.overdue.filter((i) => i.is_overdue).length ?? 0;
  const isEmpty = agenda !== undefined && agenda.overdue.length === 0 && agenda.days.length === 0;

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow />

      <div className="flex flex-col gap-1 pt-2">
        <InfoHeading
          title={<h1 className="m-0 font-display text-4xl font-bold leading-[1.05] tracking-[-0.025em] text-ui-ink">{t("Agenda")}</h1>}
          label="taskr"
          textClassName="m-0 text-sm text-ui-ink-soft"
          buttonClassName="text-ui-muted hover:text-ui-ink"
        >{t("Wat er in gardnr en trainr op de planning staat, op één plek, plus je eigen taken. Een regel uit een module vink je af of verzet je in die module, via de link erbij. Een eigen taak voeg je hieronder toe, vink je hier af met het rondje en wijzig je door op de naam te tikken.")}</InfoHeading>
        {agenda && !isEmpty && (
          <p className="m-0 text-[15px] text-ui-ink-soft">
            {lateCount > 0 && t("{n} te laat · ", { n: lateCount })}
            {t("{n} in deze periode", { n: upcomingCount })}
          </p>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (newTitle.trim()) add.mutate({ title: newTitle.trim(), due_date: newDate ?? from, notes: null });
        }}
        className="flex flex-col gap-2 rounded-2xl border border-ui-border bg-ui-surface p-3 sm:flex-row sm:items-center"
      >
        <input
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder={t("Nieuwe taak, bv. fietsband plakken")}
          aria-label={t("Nieuwe taak")}
          maxLength={200}
          className={inputClass}
        />
        <div className="flex gap-2">
          <input
            type="date"
            value={newDate ?? from}
            onChange={(e) => e.target.value && setNewDate(e.target.value)}
            aria-label={t("Datum van de nieuwe taak")}
            className={`${inputClass} sm:w-auto`}
          />
          <button type="submit" disabled={!newTitle.trim() || add.isPending} className={`${primaryButtonClass} shrink-0`}>{t("Toevoegen")}</button>
        </div>
      </form>
      {(add.isError || complete.isError) && (
        <p className="m-0 text-sm text-ui-late" role="alert">
          {add.isError ? t("Toevoegen is mislukt — probeer het opnieuw.") : t("Afvinken is mislukt — probeer het opnieuw.")}
        </p>
      )}

      {/* Its own row rather than in the top row: three segments next to the switcher pill and the
          gear don't fit a 390px phone. */}
      <div className="flex h-11 items-stretch gap-1 rounded-xl border border-ui-border bg-ui-surface p-1 sm:w-fit" role="group" aria-label={t("Periode")}>
        {AGENDA_VIEWS.map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setView(v)}
            aria-pressed={view === v}
            className={`flex-1 rounded-lg px-4 text-sm font-semibold transition-colors ${
              view === v ? "bg-ui-brand-soft text-ui-brand-strong" : "text-ui-muted hover:text-ui-ink"
            }`}
          >
            {t(AGENDA_VIEW_LABELS[v])}
          </button>
        ))}
      </div>
      <div className="flex items-center justify-between gap-2">
        <button type="button" onClick={() => setStart(shiftStart(view, from, -1))} className={iconButtonClass} aria-label={t("Vorige")}>
          <IconChevronLeft size={20} />
        </button>
        <div className="flex min-w-0 flex-col items-center gap-1">
          <span className="text-center text-[15px] font-semibold text-ui-ink">{rangeLabel(view, from, today)}</span>
          {from !== today && (
            <button type="button" onClick={() => setStart(null)} className="text-sm font-semibold text-ui-brand-strong hover:underline">{t("Naar vandaag")}</button>
          )}
        </div>
        <button type="button" onClick={() => setStart(shiftStart(view, from, 1))} className={iconButtonClass} aria-label={t("Volgende")}>
          <IconChevronRight size={20} />
        </button>
      </div>

      {agendaQuery.isPending ? (
        <div className={cardClass} role="status">{t("Agenda laden…")}</div>
      ) : agendaQuery.isError && !agenda ? (
        <div className={cardClass} role="alert">{t("Kon de agenda niet laden.")}{" "}
          <button type="button" onClick={() => agendaQuery.refetch()} className={`${secondaryButtonClass} mt-3 flex w-full sm:mx-auto sm:w-auto`}>{t("Opnieuw proberen")}</button>
        </div>
      ) : isEmpty ? (
        <div className={cardClass}>
          <p className="m-0 font-display text-lg font-bold text-ui-ink">{t("Niets te doen")}</p>
          <p className="m-0 mt-1">
            {view === "day"
              ? t("Niets achterstallig en niets gepland op deze dag. Wat gardnr en trainr plannen, verschijnt hier vanzelf; een eigen taak voeg je hierboven toe.")
              : t("Niets achterstallig en niets gepland in deze periode. Wat gardnr en trainr plannen, verschijnt hier vanzelf; een eigen taak voeg je hierboven toe.")}
          </p>
        </div>
      ) : (
        agenda && (
          <div className={`flex flex-col gap-3 transition-opacity ${agendaQuery.isPlaceholderData ? "opacity-60" : ""}`} aria-busy={agendaQuery.isFetching}>
            {agendaQuery.isError && (
              <p className="m-0 text-sm text-ui-late" role="alert">{t("Kon de agenda niet verversen.")}{" "}
                <button type="button" onClick={() => agendaQuery.refetch()} className="font-semibold underline">{t("Opnieuw proberen")}</button>
              </p>
            )}
            {agenda.overdue.length > 0 && (
              <AgendaSection
                title={overdueTitle(agenda.date_from, today)}
                items={agenda.overdue}
                today={today}
                tone={agenda.date_from <= today ? "late" : "default"}
                showDates
                actions={actions}
              />
            )}
            {agenda.days.map((day) => (
              <AgendaSection
                key={day.date}
                title={dayLabel(day.date, today)}
                items={day.items}
                today={today}
                tone={day.date === today ? "today" : "default"}
                actions={actions}
              />
            ))}
          </div>
        )
      )}

      {editing && editing.task_id !== null && (
        <TaskDialog
          key={editing.key}
          task={{ title: editing.title, due_date: editing.due_date, notes: editing.detail }}
          isSubmitting={save.isPending || remove.isPending}
          error={save.isError ? t("Opslaan is mislukt — probeer het opnieuw.") : remove.isError ? t("Verwijderen is mislukt.") : null}
          onSave={(input) => editing.task_id !== null && save.mutate({ id: editing.task_id, input })}
          onDelete={() => editing.task_id !== null && remove.mutate(editing.task_id)}
          onCancel={() => setEditing(null)}
        />
      )}
      {ticked && ticked.task_id !== null && (
        <UndoToast
          message={t("“{title}” afgevinkt", { title: ticked.title })}
          onUndo={() => {
            if (ticked.task_id !== null) complete.mutate({ id: ticked.task_id, done: false });
            setTicked(null);
          }}
          onDismiss={dismissToast}
        />
      )}
    </div>
  );
}
