import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import type { CalendarEvent, EarningsResult, PositionEventInput, PositionEventKind } from "../api/types";
import { daysUntil, formatCountdown } from "../utils/calendar";
import { formatCompactCurrency, formatCurrency, formatDate, pnlColorClass, todayIsoDate, toNumber } from "../utils/format";

/** What the user can add by hand -- Yahoo only knows earnings and dividends. */
const OWN_EVENT_KINDS: { value: PositionEventKind; label: string }[] = [
  { value: "investor_day", label: "Investor day" },
  { value: "capital_markets_day", label: "Capital markets day" },
  { value: "agm", label: "Shareholder meeting (AGM)" },
  { value: "product_event", label: "Product event" },
  { value: "other", label: "Other" },
];

const TIME_OF_DAY_LABEL = { before_open: "before market open", after_close: "after market close" } as const;

// Anything inside a surprise this small reads as "met expectations", not a beat or a miss --
// EPS is quoted to the cent, so a fraction of a percent is rounding, not news.
const IN_LINE_PCT = 0.5;

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

export function usePositionCalendar(assetId: number, enabled: boolean) {
  return useQuery({
    queryKey: ["position-calendar", assetId],
    queryFn: () => api.getPositionCalendar(assetId),
    enabled,
    staleTime: 60 * 60 * 1000,
  });
}

function Placeholder({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-dashed border-slate-200 px-4 py-6 text-center text-sm text-slate-400">{children}</div>;
}

/** One line on the Overview tab: the soonest upcoming event, so it's visible without opening
 * Calendar. Renders nothing while loading or when there's nothing coming up -- it's a hint,
 * not a widget of its own. */
export function NextEventLine({ assetId, enabled }: { assetId: number; enabled: boolean }) {
  const { data } = usePositionCalendar(assetId, enabled);
  const next = data?.upcoming[0];
  if (!next) return null;
  return (
    <p className="mt-3 text-sm text-slate-600">
      <span className="text-slate-500">Next:</span> <span className="font-medium text-slate-900">{next.title}</span> ·{" "}
      {formatDate(next.date, { day: "numeric", month: "short" })}
      {next.is_estimate && " (estimated)"} <span className="text-slate-500">— {formatCountdown(daysUntil(next.date))}</span>
    </p>
  );
}

function DateBlock({ iso }: { iso: string }) {
  return (
    <div className="flex w-12 shrink-0 flex-col items-center rounded-md border border-slate-200 py-1 leading-tight">
      <span className="text-[10px] font-semibold uppercase text-slate-500">{formatDate(iso, { month: "short" })}</span>
      <span className="text-lg font-semibold tabular-nums text-slate-900">{formatDate(iso, { day: "numeric" })}</span>
    </div>
  );
}

function EventForm({
  initial,
  onCancel,
  onSubmit,
  isSubmitting,
}: {
  initial: CalendarEvent | undefined;
  onCancel: () => void;
  onSubmit: (input: PositionEventInput) => void;
  isSubmitting: boolean;
}) {
  const [date, setDate] = useState(initial?.date ?? todayIsoDate());
  const [kind, setKind] = useState<PositionEventKind>((initial?.kind as PositionEventKind | undefined) ?? "investor_day");
  const [title, setTitle] = useState(initial?.title ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const kindLabel = OWN_EVENT_KINDS.find((k) => k.value === kind)?.label ?? "Event";

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        // An empty title just takes the type's name -- "Investor day" is usually all it needs.
        onSubmit({ date, kind, title: title.trim() || kindLabel.replace(" (AGM)", ""), notes: notes.trim() || null });
      }}
      className="mb-3 flex flex-col gap-2 rounded-lg border border-slate-200 p-3"
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
          Date
          <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} className={inputClass} />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
          Type
          <select value={kind} onChange={(e) => setKind(e.target.value as PositionEventKind)} className={inputClass}>
            {OWN_EVENT_KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={200}
        placeholder={`Title (default: ${kindLabel.replace(" (AGM)", "")})`}
        className={inputClass}
      />
      <textarea
        rows={2}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        maxLength={2000}
        placeholder="Notes — what to watch for, a link to the announcement…"
        className={`${inputClass} resize-y`}
      />
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {isSubmitting ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}

function EventRow({
  event,
  currency,
  onEdit,
  onDelete,
  showCountdown,
}: {
  event: CalendarEvent;
  currency: string | null;
  onEdit: () => void;
  onDelete: () => void;
  showCountdown: boolean;
}) {
  const isOwn = event.source === "manual";
  const details = [
    event.is_estimate && (event.end_date ? `estimated, ${formatDate(event.date, { day: "numeric", month: "short" })}–${formatDate(event.end_date, { day: "numeric", month: "short" })}` : "estimated date"),
    event.time_of_day && TIME_OF_DAY_LABEL[event.time_of_day],
    isOwn && "added by you",
  ].filter(Boolean);
  const expected = [
    event.eps_estimate && `EPS ${formatCurrency(event.eps_estimate, currency)}`,
    event.revenue_estimate && `revenue ${formatCompactCurrency(event.revenue_estimate, currency)}`,
  ].filter(Boolean);

  return (
    <li className="flex gap-3 py-2.5">
      <DateBlock iso={event.date} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-medium text-slate-900">{event.title}</span>
          {showCountdown && <span className="shrink-0 text-xs text-slate-500">{formatCountdown(daysUntil(event.date))}</span>}
        </div>
        {details.length > 0 && <div className="text-xs text-slate-500">{details.join(" · ")}</div>}
        {expected.length > 0 && <div className="text-xs text-slate-600">Expected: {expected.join(" · ")}</div>}
        {event.notes && <p className="mt-0.5 whitespace-pre-line text-xs text-slate-600">{event.notes}</p>}
        {isOwn && (
          <div className="mt-1 flex gap-3">
            <button type="button" onClick={onEdit} className="text-slate-500 hover:text-slate-900" title="Edit" aria-label={`Edit ${event.title}`}>
              <Pencil className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
            <button type="button" onClick={onDelete} className="text-red-500 hover:text-red-700" title="Delete" aria-label={`Delete ${event.title}`}>
              <Trash2 className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
          </div>
        )}
      </div>
    </li>
  );
}

function SurpriseCell({ result }: { result: EarningsResult }) {
  const pct = toNumber(result.surprise_pct);
  if (pct === null) return <span className="text-slate-400">—</span>;
  if (Math.abs(pct) < IN_LINE_PCT) return <span className="text-slate-500">in line</span>;
  const rounded = Math.round(pct);
  return (
    <span className={pnlColorClass(pct)}>
      {pct > 0 ? "beat" : "miss"} {pct > 0 ? "+" : "−"}
      {Math.abs(rounded)}%
    </span>
  );
}

export default function PositionCalendarSection({ assetId, enabled }: { assetId: number; enabled: boolean }) {
  const queryClient = useQueryClient();
  const query = usePositionCalendar(assetId, enabled);
  // null = closed; { event: undefined } = adding; { event } = editing that one.
  const [editing, setEditing] = useState<{ event: CalendarEvent | undefined } | null>(null);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["position-calendar", assetId] });
    setEditing(null);
  };
  const createMutation = useMutation({
    mutationFn: (input: PositionEventInput) => api.createPositionEvent(assetId, input),
    onSuccess: invalidate,
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: PositionEventInput }) => api.updatePositionEvent(assetId, id, input),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deletePositionEvent(assetId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["position-calendar", assetId] }),
  });

  if (query.isLoading) return <Placeholder>Loading calendar…</Placeholder>;
  if (query.isError || !query.data) return <Placeholder>Couldn't load the calendar for this holding.</Placeholder>;

  const { upcoming, past, results, currency } = query.data;
  const nothingFromYahoo = results.length === 0 && !upcoming.some((e) => e.source === "yahoo");
  const confirmDelete = (event: CalendarEvent) => {
    if (event.id !== null && confirm(`Delete "${event.title}" on ${formatDate(event.date)}?`)) deleteMutation.mutate(event.id);
  };
  const rowProps = (event: CalendarEvent) => ({
    event,
    currency,
    onEdit: () => setEditing({ event }),
    onDelete: () => confirmDelete(event),
  });

  return (
    <div className="flex flex-col gap-5">
      <section>
        <div className="flex items-baseline justify-between">
          <h3 className="text-sm font-medium text-slate-700">Upcoming</h3>
          {editing === null && (
            <button
              type="button"
              onClick={() => setEditing({ event: undefined })}
              className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
            >
              + Add event
            </button>
          )}
        </div>
        <div className="mt-2">
          {editing && (
            <EventForm
              key={editing.event?.id ?? "new"}
              initial={editing.event}
              isSubmitting={createMutation.isPending || updateMutation.isPending}
              onCancel={() => setEditing(null)}
              onSubmit={(input) =>
                editing.event?.id != null ? updateMutation.mutate({ id: editing.event.id, input }) : createMutation.mutate(input)
              }
            />
          )}
          {upcoming.length === 0 ? (
            editing === null && (
              <Placeholder>
                {nothingFromYahoo
                  ? "Yahoo doesn't publish company events for funds, crypto or commodities — add your own, like a fund's dividend date."
                  : "Nothing scheduled yet. Add an investor day or AGM when it's announced."}
              </Placeholder>
            )
          ) : (
            <ul className="divide-y divide-slate-100">
              {upcoming.map((event) => (
                <EventRow key={`${event.source}-${event.kind}-${event.id ?? event.date}`} {...rowProps(event)} showCountdown />
              ))}
            </ul>
          )}
        </div>
      </section>

      {results.length > 0 && (
        <section>
          <h3 className="text-sm font-medium text-slate-700">Past results</h3>
          <p className="text-xs text-slate-500">Earnings per share against what analysts expected{currency ? ` (${currency})` : ""}.</p>
          <table className="mt-2 w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-1 font-medium">Reported</th>
                <th className="py-1 text-right font-medium">Expected</th>
                <th className="py-1 text-right font-medium">Actual</th>
                <th className="py-1 text-right font-medium">Surprise</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.report_date} className="border-t border-slate-100">
                  <td className="py-1.5 text-slate-600">{formatDate(r.report_date, { day: "numeric", month: "short", year: "2-digit" })}</td>
                  <td className="py-1.5 text-right tabular-nums text-slate-600">{formatCurrency(r.eps_estimate, currency)}</td>
                  <td className="py-1.5 text-right tabular-nums text-slate-900">{formatCurrency(r.eps_actual, currency)}</td>
                  <td className="py-1.5 text-right tabular-nums">
                    <SurpriseCell result={r} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {past.length > 0 && (
        <section>
          <h3 className="text-sm font-medium text-slate-700">Your past events</h3>
          <ul className="mt-1 divide-y divide-slate-100">
            {past.map((event) => (
              <EventRow key={`past-${event.id}`} {...rowProps(event)} showCountdown={false} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
