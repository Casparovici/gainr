import type { NotrPinnedNote } from "./notrTypes";

// Mirrors backend/app/schemas/taskr.py. A module's item is completed in the module that owns it,
// through its `link` (docs/adr/0038); taskr's own tasks are ticked off on the agenda (its addendum).

/** The modules that contribute to the agenda -- a subset of the app's module keys, so each one
 * has a brand colour and a logo (components/ModuleLogo.tsx). "taskr" is a task added in taskr. */
export type AgendaSource = "gardnr" | "trainr" | "taskr";

export interface AgendaItem {
  /** Stable per item, e.g. "gardnr:schedule:12". */
  key: string;
  source: AgendaSource;
  title: string;
  detail: string | null;
  /** YYYY-MM-DD */
  due_date: string;
  /** Due before today (the server's), not before the requested range. */
  is_overdue: boolean;
  /** The owning module's page where the item is completed, e.g. "/gardnr/vandaag"; null for a
   * taskr task. */
  link: string | null;
  /** Set on a taskr task only: ticked off, changed or deleted right here. */
  task_id: number | null;
}

export interface AgendaDay {
  /** YYYY-MM-DD */
  date: string;
  items: AgendaItem[];
}

export interface Agenda {
  date_from: string;
  date_to: string;
  /** Everything due before `date_from` and not yet done, oldest first. */
  overdue: AgendaItem[];
  /** One entry per day in the range that has something due, in date order. */
  days: AgendaDay[];
}

/** A task added in taskr itself. */
export interface TaskrTask {
  id: number;
  title: string;
  notes: string | null;
  /** YYYY-MM-DD */
  due_date: string;
  completed_at: string | null;
}

export interface TaskrTaskInput {
  title: string;
  notes: string | null;
  /** YYYY-MM-DD */
  due_date: string;
}

// -- Vandaag, the app's start screen (backend/app/schemas/taskr.py, TodayOut) --------------------

export interface TodayPortfolio {
  portfolio_id: number;
  name: string;
  value_eur: string | null;
  /** The portfolio's time-weighted move since yesterday's close. */
  day_change_eur: string | null;
  day_change_pct: string | null;
}

export interface TodayMoney {
  /** What could leave the checking account today without the forecast dipping into a week of
   * everyday spending; null while there's no forecast to tell. */
  safe_to_move_eur: string | null;
  expected_end_eur: string | null;
}

export interface TodayCounts {
  gripr_uncategorized: number;
  /** Overdue or due today. */
  gardnr_due: number;
  /** Planned for today and not done yet. */
  trainr_today: number;
  taskr_overdue: number;
  /** Unticked items on the active shopping lists. */
  listr_to_get: number;
  briefr_unread: number;
  /** Pinned notes (notr). */
  notr_pinned: number;
}

export interface Today {
  date: string;
  /** Overdue, and today's items. */
  agenda: Agenda;
  portfolio: TodayPortfolio | null;
  money: TodayMoney | null;
  latest_unread_report: { id: number; title: string; attention: string } | null;
  meal: { title: string; is_cooked: boolean } | null;
  /** notr's pinned notes, most recently edited first. */
  pinned_notes: NotrPinnedNote[];
  counts: TodayCounts;
}
