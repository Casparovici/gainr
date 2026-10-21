import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Droplets, FileText, ListChecks, Pin, Tags, UtensilsCrossed, type LucideIcon } from "lucide-react";
import { useCallback, useState, type ReactNode } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { taskrApi } from "../api/taskrClient";
import type { AgendaItem, Today, TaskrTaskInput } from "../api/taskrTypes";
import { AgendaSection, type TaskActions } from "../components/taskr/AgendaList";
import TaskDialog from "../components/taskr/TaskDialog";
import UndoToast from "../components/UndoToast";
import { ModuleTopRow, PageTitle, inputClass, primaryButtonClass, secondaryButtonClass } from "../components/ui/kit";
import Sheet from "../components/ui/Sheet";
import { positionPath } from "../config/modules";
import { useToday } from "../hooks/useToday";
import { formatEur, formatPct, formatSignedEur, pnlColorClass, toNumber } from "../utils/format";
import { overdueTitle } from "../utils/taskr";
import { dateLocale, t, tp } from "../i18n";

interface Attention {
  key: string;
  to: string;
  icon: LucideIcon;
  /** The module colour of the icon tile, as a CSS colour. */
  color: string;
  title: string;
  detail: string;
  late?: boolean;
}

const BRAND = {
  briefr: "var(--brand-briefr)",
  gripr: "var(--brand-gripr)",
  gardnr: "var(--brand-gardnr)",
  taskr: "var(--brand-taskr)",
  listr: "var(--brand-listr)",
  notr: "var(--brand-notr, #5E7F12)",
};

/** How many pinned notes the card lists; the rest are one tap away in notr. */
const PINNED_SHOWN = 5;

/** What asks for the reader across the modules, most pressing first. Built from the counts the
 * server worked out; this only words them. */
export function attentionItems(today: Today): Attention[] {
  const c = today.counts;
  const items: Attention[] = [];
  if (c.gardnr_due > 0) {
    const late = today.agenda.overdue.some((i) => i.source === "gardnr");
    items.push({
      key: "gardnr", to: "/gardnr/vandaag", icon: Droplets, color: BRAND.gardnr, late,
      title: tp(c.gardnr_due, "{n} verzorging in de tuin", "{n} verzorgingen in de tuin"),
      detail: late ? t("gardnr · te laat") : t("gardnr · vandaag"),
    });
  }
  if (c.taskr_overdue > 0) {
    items.push({
      key: "taskr", to: "/taskr", icon: ListChecks, color: BRAND.taskr, late: true,
      title: tp(c.taskr_overdue, "{n} taak te laat", "{n} taken te laat"),
      detail: t("taskr · eigen taken"),
    });
  }
  if (c.gripr_uncategorized > 0) {
    items.push({
      key: "gripr", to: "/gripr/transactions?category=uncategorized", icon: Tags, color: BRAND.gripr,
      title: tp(c.gripr_uncategorized, "{n} betaling zonder categorie", "{n} betalingen zonder categorie"),
      detail: t("gripr · nog in te delen"),
    });
  }
  if (c.briefr_unread > 0 && today.latest_unread_report) {
    items.push({
      key: "briefr", to: "/briefr", icon: FileText, color: BRAND.briefr,
      title: today.latest_unread_report.title,
      detail: tp(c.briefr_unread, "briefr · {n} ongelezen rapport", "briefr · {n} ongelezen rapporten"),
    });
  }
  return items;
}

function Card({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section aria-label={title} className="overflow-hidden rounded-2xl border border-ui-border bg-ui-surface">
      <div className="flex items-center justify-between gap-3 px-4 pb-2 pt-3.5">
        <h2 className="m-0 text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/** Vandaag, the app's start screen (docs/adr/0048): what needs you today from every module --
 * what's late or waiting, the money in one glance, today's agenda and tonight's meal -- each
 * linking to the module where it's dealt with. taskr's own tasks are ticked off right here. */
export default function Vandaag({ today: todayOverride }: { today?: string } = {}) {
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const todayQuery = useToday();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<AgendaItem | null>(null);
  const [ticked, setTicked] = useState<AgendaItem | null>(null);
  const dismissToast = useCallback(() => setTicked(null), []);
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["today"] });
    queryClient.invalidateQueries({ queryKey: ["taskr-agenda"] });
  };

  const complete = useMutation({
    mutationFn: ({ id, done }: { id: number; done: boolean }) => taskrApi.setTaskCompleted(id, done),
    onSuccess: refresh,
  });
  const add = useMutation({
    mutationFn: (input: TaskrTaskInput) => taskrApi.createTask(input),
    onSuccess: () => {
      setAdding(false);
      refresh();
    },
  });
  const save = useMutation({
    mutationFn: ({ id, input }: { id: number; input: TaskrTaskInput }) => taskrApi.updateTask(id, input),
    onSuccess: () => {
      setEditing(null);
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => taskrApi.deleteTask(id),
    onSuccess: () => {
      setEditing(null);
      refresh();
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

  // The app's root used to be gainr Home, and position links pointed at it.
  const legacyPosition = params.get("position");
  if (legacyPosition) return <Navigate to={positionPath(Number(legacyPosition))} replace />;

  const data = todayQuery.data;
  const today = todayOverride ?? data?.date ?? "";
  const attention = data ? attentionItems(data) : [];
  const todayItems = data?.agenda.days.find((d) => d.date === today)?.items ?? [];
  const overdueTasks = data?.agenda.overdue.filter((i) => i.source === "taskr") ?? [];
  const dateLabel = today
    ? new Date(`${today}T00:00:00`).toLocaleDateString(dateLocale("nl-NL"), { weekday: "long", day: "numeric", month: "long" })
    : "";

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow />
      <PageTitle
        subtitle={
          data
            ? `${dateLabel} · ${attention.length === 0 ? t("niets vraagt aandacht") : tp(attention.length, "{n} ding vraagt aandacht", "{n} dingen vragen aandacht")}`
            : dateLabel || undefined
        }
      >{t("Vandaag")}</PageTitle>

      {todayQuery.isPending ? (
        <div className="flex flex-col gap-4" role="status" aria-label={t("Vandaag laden")}>
          {[96, 120, 160].map((h) => (
            <div key={h} className="animate-pulse rounded-2xl bg-ui-tile" style={{ height: h }} />
          ))}
        </div>
      ) : todayQuery.isError || !data ? (
        <div className="rounded-2xl border border-ui-border bg-ui-surface px-4 py-6 text-center text-sm text-ui-muted" role="alert">{t("Kon vandaag niet laden.")}<button type="button" onClick={() => todayQuery.refetch()} className={`${secondaryButtonClass} mt-3 flex w-full sm:mx-auto sm:w-auto`}>{t("Opnieuw proberen")}</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start">
          <div className="flex min-w-0 flex-col gap-4">
            <Card title={t("Vraagt aandacht")}>
              {attention.length === 0 ? (
                <p className="m-0 border-t border-ui-line/50 px-4 py-3.5 text-[15px] text-ui-muted">{t("Alles bij. Niets te laat, niets te doen.")}</p>
              ) : (
                <ul className="m-0 list-none p-0">
                  {attention.map((a) => (
                    <li key={a.key} className="border-t border-ui-line/50">
                      <Link to={a.to} className="flex items-center gap-3 px-4 py-3 text-ui-ink no-underline hover:bg-ui-tile/60">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] text-white" style={{ backgroundColor: a.color }}>
                          <a.icon className="h-[18px] w-[18px]" strokeWidth={2.2} />
                        </span>
                        <span className="flex min-w-0 flex-1 flex-col">
                          <span className="truncate text-[15px] font-semibold">{a.title}</span>
                          <span className={`truncate text-[13px] ${a.late ? "text-ui-late" : "text-ui-muted"}`}>{a.detail}</span>
                        </span>
                        <ChevronRight aria-hidden className="h-[18px] w-[18px] shrink-0 text-ui-faint" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            {(data.portfolio || data.money) && (
              <div className="grid grid-cols-2 gap-3">
                {data.portfolio && (
                  <Link to="/gainr" className="flex min-w-0 flex-col gap-1 rounded-2xl border border-ui-border bg-ui-surface p-3.5 text-ui-ink no-underline hover:bg-ui-tile/60">
                    <span className="truncate text-[13px] font-semibold" style={{ color: "var(--brand-gainr)" }}>{t("gainr · {name}", { name: data.portfolio.name })}</span>
                    <span className="font-display text-[22px] font-bold tracking-[-0.02em] tabular-nums">{formatEur(data.portfolio.value_eur, true)}</span>
                    <span className={`text-sm font-semibold tabular-nums ${pnlColorClass(data.portfolio.day_change_eur)}`}>
                      {toNumber(data.portfolio.day_change_eur) === null
                        ? "—"
                        : `${formatSignedEur(data.portfolio.day_change_eur)} · ${formatPct(data.portfolio.day_change_pct)}`}
                    </span>
                    <span className="text-xs text-ui-muted">{t("sinds gisteren")}</span>
                  </Link>
                )}
                {data.money && (
                  <Link to="/gripr/overview" className="flex min-w-0 flex-col gap-1 rounded-2xl border border-ui-border bg-ui-surface p-3.5 text-ui-ink no-underline hover:bg-ui-tile/60">
                    <span className="truncate text-[13px] font-semibold" style={{ color: "var(--brand-gripr)" }}>{t("gripr · deze periode")}</span>
                    <span className="font-display text-[22px] font-bold tracking-[-0.02em] tabular-nums">{formatEur(data.money.safe_to_move_eur, true)}</span>
                    <span className="text-sm font-semibold">{t("veilig over te boeken")}</span>
                    {data.money.expected_end_eur !== null && (
                      <span className="text-xs text-ui-muted">{t("eind van de periode {amount}", { amount: formatEur(data.money.expected_end_eur, true) })}</span>
                    )}
                  </Link>
                )}
              </div>
            )}
          </div>

          <div className="flex min-w-0 flex-col gap-4">
            {/* Only taskr's own late tasks, which are ticked off here: what's late in another module is
                one line under "Vraagt aandacht", linking to where it's done. */}
            {overdueTasks.length > 0 && (
              <AgendaSection title={overdueTitle(today, today)} items={overdueTasks} today={today} tone="late" showDates actions={actions} />
            )}
            {todayItems.length > 0 ? (
              <AgendaSection title={t("Op de agenda")} items={todayItems} today={today} tone="today" actions={actions} />
            ) : (
              <p className="m-0 rounded-2xl border border-ui-border bg-ui-surface px-4 py-3.5 text-[15px] text-ui-muted">{t("Niets gepland vandaag.")}</p>
            )}
            {data.meal && (
              <Link to="/listr/weekplanner" className="flex items-center gap-3 rounded-2xl border border-ui-border bg-ui-surface px-4 py-3 text-ui-ink no-underline hover:bg-ui-tile/60">
                <UtensilsCrossed aria-hidden className="h-5 w-5 shrink-0" style={{ color: "var(--brand-listr)" }} strokeWidth={2} />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-[15px] font-semibold">{t("Vanavond: {meal}", { meal: data.meal.title })}</span>
                  <span className="text-[13px] text-ui-muted">
                    {data.meal.is_cooked
                      ? t("gekookt")
                      : data.counts.listr_to_get > 0
                        ? tp(data.counts.listr_to_get, "{n} ding op de boodschappenlijst", "{n} dingen op de boodschappenlijst")
                        : t("listr · weekplanner")}
                  </span>
                </span>
                <ChevronRight aria-hidden className="h-[18px] w-[18px] shrink-0 text-ui-faint" />
              </Link>
            )}
            {data.pinned_notes.length > 0 && (
              <Card
                title={t("Vastgezet")}
                action={<Link to="/notr" className="text-sm font-semibold no-underline" style={{ color: BRAND.notr }}>{t("Alle notities ›")}</Link>}
              >
                <ul className="m-0 list-none p-0">
                  {data.pinned_notes.slice(0, PINNED_SHOWN).map((note) => (
                    <li key={note.id} className="border-t border-ui-line/50">
                      <Link to={`/notr/${note.id}`} className="flex items-center gap-3 px-4 py-3 text-ui-ink no-underline hover:bg-ui-tile/60">
                        <Pin aria-hidden className="h-[18px] w-[18px] shrink-0" style={{ color: BRAND.notr }} strokeWidth={2} />
                        <span className="min-w-0 flex-1 truncate text-[15px] font-semibold">{note.title || note.preview || t("Notitie zonder titel")}</span>
                        <ChevronRight aria-hidden className="h-[18px] w-[18px] shrink-0 text-ui-faint" />
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            <Link to="/taskr" className="self-start px-1 text-sm font-semibold" style={{ color: "var(--brand-taskr)" }}>{t("Hele agenda in taskr ›")}</Link>

            <div role="group" aria-label={t("Snel toevoegen")} className="flex flex-wrap gap-2">
              <button type="button" onClick={() => setAdding(true)} className={secondaryButtonClass}>{t("+ Taak")}</button>
              <button type="button" onClick={() => navigate("/gripr/transactions?add=1")} className={secondaryButtonClass}>{t("+ Uitgave")}</button>
              <button type="button" onClick={() => navigate("/listr")} className={secondaryButtonClass}>{t("+ Boodschap")}</button>
              <button type="button" onClick={() => navigate("/trainr")} className={secondaryButtonClass}>{t("+ Workout")}</button>
              <button type="button" onClick={() => navigate("/notr/new")} className={secondaryButtonClass}>{t("+ Notitie")}</button>
            </div>
          </div>
        </div>
      )}

      {adding && (
        <NewTaskSheet
          today={today}
          isSubmitting={add.isPending}
          failed={add.isError}
          onAdd={(input) => add.mutate(input)}
          onClose={() => {
            add.reset();
            setAdding(false);
          }}
        />
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

function NewTaskSheet({
  today,
  isSubmitting,
  failed,
  onAdd,
  onClose,
}: {
  today: string;
  isSubmitting: boolean;
  failed: boolean;
  onAdd: (input: TaskrTaskInput) => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState(today);
  const submit = () => {
    if (title.trim() && dueDate) onAdd({ title: title.trim(), due_date: dueDate, notes: null });
  };
  return (
    <Sheet
      title={t("Nieuwe taak")}
      onClose={onClose}
      footer={
        <button type="button" onClick={submit} disabled={!title.trim() || isSubmitting} className={primaryButtonClass}>
          {isSubmitting ? t("Toevoegen…") : t("Toevoegen")}
        </button>
      }
    >
      <form
        className="flex flex-col gap-3 pt-2"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label className="flex flex-col gap-1.5 text-sm font-semibold text-ui-ink-soft">{t("Wat")}<input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t("bv. fietsband plakken")} maxLength={200} className={inputClass} />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-semibold text-ui-ink-soft">{t("Wanneer")}<input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className={inputClass} />
        </label>
        {failed && (
          <p className="m-0 text-sm text-ui-late" role="alert">{t("Toevoegen is mislukt — probeer het opnieuw.")}</p>
        )}
      </form>
    </Sheet>
  );
}
