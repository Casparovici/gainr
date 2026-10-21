import { ArrowUpRight, Circle } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { AgendaItem, AgendaSource } from "../../api/taskrTypes";
import { AGENDA_SOURCE_LABELS, shortDayDate } from "../../utils/taskr";
import { ModuleGlyph } from "../ModuleLogo";
import { t } from "../../i18n";

/** Which module an item comes from: its glyph and name in that module's own brand colour
 * (`--brand-<module>`, which follows dark mode) -- the colour the reader already knows it by. */
export function SourceBadge({ source }: { source: AgendaSource }) {
  const color = `var(--brand-${source})`;
  return (
    <span
      className="inline-flex h-[22px] items-center gap-1 rounded-full border px-2 text-xs font-semibold"
      style={{ color, borderColor: color }}
    >
      <ModuleGlyph module={source} size={12} />
      {AGENDA_SOURCE_LABELS[source]}
    </span>
  );
}

/** What a taskr task's line can do; a module's item has only its link. */
export interface TaskActions {
  onComplete: (item: AgendaItem) => void;
  onEdit: (item: AgendaItem) => void;
}

/** One agenda line: an open circle for something to do and tick off. A module's item is completed
 * in that module, so its only action is the link there; a taskr task is ticked off with its
 * circle and opened for editing with its title. `showDate` is for the overdue list, where the day
 * isn't already the heading; `today` only decides whether that date needs its year. */
export function AgendaItemRow({
  item,
  today,
  showDate = false,
  actions,
}: {
  item: AgendaItem;
  today: string;
  showDate?: boolean;
  actions?: TaskActions;
}) {
  const source = AGENDA_SOURCE_LABELS[item.source];
  const isTask = item.task_id !== null && actions !== undefined;
  const circle = (
    <Circle className={`h-5 w-5 shrink-0 ${item.is_overdue ? "text-ui-late" : "text-ui-faint"}`} strokeWidth={2} aria-hidden />
  );
  let title: ReactNode = <p className="m-0 break-words text-[15px] font-semibold text-ui-ink">{item.title}</p>;
  if (isTask) {
    title = (
      <button
        type="button"
        onClick={() => actions.onEdit(item)}
        aria-label={t("{title}: wijzigen", { title: item.title })}
        className="m-0 break-words text-left text-[15px] font-semibold text-ui-ink hover:underline"
      >
        {item.title}
      </button>
    );
  }
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      {isTask ? (
        <button
          type="button"
          onClick={() => actions.onComplete(item)}
          aria-label={t("{title}: afvinken", { title: item.title })}
          className="-mx-2.5 -mb-2.5 -mt-2 shrink-0 rounded-full p-2.5"
        >
          {circle}
        </button>
      ) : (
        <span className="mt-0.5">{circle}</span>
      )}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <SourceBadge source={item.source} />
          {item.is_overdue && (
            <span className="inline-flex h-[22px] items-center rounded-full bg-ui-late-soft px-2 text-xs font-semibold text-ui-late">
              {showDate ? t("te laat · {date}", { date: shortDayDate(item.due_date, today) }) : t("te laat")}
            </span>
          )}
          {!item.is_overdue && showDate && <span className="text-xs font-medium text-ui-muted">{shortDayDate(item.due_date, today)}</span>}
        </div>
        {title}
        {item.detail && <p className="m-0 whitespace-pre-line text-sm text-ui-ink-soft">{item.detail}</p>}
        {item.link && (
          <Link
            to={item.link}
            className="inline-flex w-fit items-center gap-1 py-1 text-sm font-semibold text-ui-brand-strong hover:underline"
            aria-label={t("{title}: open in {source}", { title: item.title, source })}
          >{t("Open in {source}", { source: source })}<ArrowUpRight className="h-4 w-4" strokeWidth={2} aria-hidden />
          </Link>
        )}
      </div>
    </li>
  );
}

/** A titled card holding a list of agenda lines: the overdue list or one day. */
export function AgendaSection({
  title,
  items,
  today,
  tone = "default",
  showDates = false,
  actions,
}: {
  title: string;
  items: AgendaItem[];
  today: string;
  tone?: "default" | "late" | "today";
  showDates?: boolean;
  actions?: TaskActions;
}) {
  const titleClass = tone === "late" ? "text-ui-late" : tone === "today" ? "text-ui-brand-strong" : "text-ui-ink";
  return (
    <section aria-label={title} className="rounded-2xl border border-ui-border bg-ui-surface">
      <div className="flex items-center gap-2 border-b border-ui-border px-4 py-2.5">
        <h2 className={`m-0 font-display text-base font-bold tracking-[-0.01em] ${titleClass}`}>{title}</h2>
        <span className="ml-auto text-xs font-medium text-ui-muted">{items.length}</span>
      </div>
      <ul className="m-0 list-none divide-y divide-ui-border p-0">
        {items.map((item) => (
          <AgendaItemRow key={item.key} item={item} today={today} showDate={showDates} actions={actions} />
        ))}
      </ul>
    </section>
  );
}
