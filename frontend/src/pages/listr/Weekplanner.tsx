import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShoppingCart, Trophy } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { listrApi } from "../../api/listrClient";
import type { ListrMealPlanEntry, ListrMealPlanInput } from "../../api/listrTypes";
import AddWeekToListDialog from "../../components/listr/AddWeekToListDialog";
import MealDayDialog from "../../components/listr/MealDayDialog";
import {
  IconCheck,
  IconChevronLeft,
  IconChevronRight,
  ModuleTopRow,
  PageTitle,
  iconButtonClass,
  primaryButtonClass,
} from "../../components/ui/kit";

const WEEKDAY_LABELS = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"];

function toIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function fromIso(iso: string): Date {
  return new Date(iso + "T00:00:00");
}
function addDays(iso: string, days: number): string {
  const d = fromIso(iso);
  d.setDate(d.getDate() + days);
  return toIso(d);
}
function addMonths(iso: string, months: number): string {
  const d = fromIso(iso);
  d.setMonth(d.getMonth() + months);
  return toIso(d);
}
// Monday-based week start, regardless of what JS's Sunday-first getDay() says.
function startOfWeek(iso: string): string {
  const day = fromIso(iso).getDay();
  return addDays(iso, day === 0 ? -6 : 1 - day);
}
function startOfMonth(iso: string): string {
  const d = fromIso(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}
function endOfMonth(iso: string): string {
  return addDays(addMonths(startOfMonth(iso), 1), -1);
}
function range(startIso: string, endIso: string): string[] {
  const days: string[] = [];
  let cur = startIso;
  while (cur <= endIso) {
    days.push(cur);
    cur = addDays(cur, 1);
  }
  return days;
}

export default function ListrWeekplanner() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const today = toIso(new Date());
  const [viewMode, setViewMode] = useState<"week" | "month">("week");
  const [cursor, setCursor] = useState(today);
  const [editingDate, setEditingDate] = useState<string | null>(null);
  const [addingToList, setAddingToList] = useState(false);

  const weekStart = startOfWeek(cursor);
  const monthStart = startOfMonth(cursor);
  const gridStart = viewMode === "week" ? weekStart : startOfWeek(monthStart);
  const gridEnd = viewMode === "week" ? addDays(weekStart, 6) : addDays(startOfWeek(endOfMonth(cursor)), 6);
  const days = range(gridStart, gridEnd);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["listr-meal-plan"] });
    queryClient.invalidateQueries({ queryKey: ["listr-popular-recipes"] });
  };

  const mealPlanQuery = useQuery({
    queryKey: ["listr-meal-plan", gridStart, gridEnd],
    queryFn: () => listrApi.listMealPlan(gridStart, gridEnd),
  });
  const popularQuery = useQuery({
    queryKey: ["listr-popular-recipes"],
    queryFn: () => listrApi.getPopularRecipes(10),
  });

  const entriesByDate = new Map<string, ListrMealPlanEntry>((mealPlanQuery.data ?? []).map((e) => [e.date, e]));

  // The exact in-view range, excluding month view's leading/trailing days from adjacent months --
  // what "this week"/"this month" actually means for the bulk add-to-list action below.
  const scopeStart = viewMode === "week" ? weekStart : monthStart;
  const scopeEnd = viewMode === "week" ? addDays(weekStart, 6) : endOfMonth(cursor);
  const plannedMeals = (mealPlanQuery.data ?? [])
    .filter((e) => e.recipe_id !== null && e.recipe_title !== null && e.date >= scopeStart && e.date <= scopeEnd)
    .map((e) => ({ date: e.date, recipeTitle: e.recipe_title as string }));

  const saveMutation = useMutation({
    mutationFn: ({ date, input }: { date: string; input: ListrMealPlanInput }) =>
      listrApi.setMealPlanDay(date, input),
    onSuccess: () => {
      invalidate();
      setEditingDate(null);
    },
  });
  const clearMutation = useMutation({
    mutationFn: (date: string) => listrApi.clearMealPlanDay(date),
    onSuccess: () => {
      invalidate();
      setEditingDate(null);
    },
  });
  const toggleCookedMutation = useMutation({
    mutationFn: ({ date, entry }: { date: string; entry: ListrMealPlanEntry }) =>
      listrApi.setMealPlanDay(date, {
        recipe_id: entry.recipe_id,
        notes: entry.notes,
        is_cooked: !entry.is_cooked,
      }),
    onSuccess: invalidate,
  });
  const addToListMutation = useMutation({
    mutationFn: (input: { listId: number | null; newListName: string | null; dates: string[] }) =>
      listrApi.addMealPlanToList({
        dates: input.dates,
        list_id: input.listId ?? undefined,
        new_list_name: input.newListName ?? undefined,
      }),
    onSuccess: (list) => {
      queryClient.invalidateQueries({ queryKey: ["listr-lists"] });
      setAddingToList(false);
      navigate(`/listr/lijst/${list.id}`);
    },
  });

  const label =
    viewMode === "week"
      ? `${fromIso(weekStart).toLocaleDateString("nl-NL", { day: "numeric", month: "short" })} – ${fromIso(
          addDays(weekStart, 6),
        ).toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" })}`
      : fromIso(monthStart).toLocaleDateString("nl-NL", { month: "long", year: "numeric" });

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow>
        <div className="flex h-11 items-stretch gap-1 rounded-xl border border-ui-border bg-ui-surface p-1">
          <button
            onClick={() => setViewMode("week")}
            aria-pressed={viewMode === "week"}
            className={`rounded-lg px-3 text-sm font-semibold transition-colors ${viewMode === "week" ? "bg-ui-brand-soft text-ui-brand-strong" : "text-ui-muted hover:text-ui-ink"}`}
          >
            Week
          </button>
          <button
            onClick={() => setViewMode("month")}
            aria-pressed={viewMode === "month"}
            className={`rounded-lg px-3 text-sm font-semibold transition-colors ${viewMode === "month" ? "bg-ui-brand-soft text-ui-brand-strong" : "text-ui-muted hover:text-ui-ink"}`}
          >
            Maand
          </button>
        </div>
      </ModuleTopRow>
      <PageTitle
        subtitle={`${plannedMeals.length} ${plannedMeals.length === 1 ? "maaltijd" : "maaltijden"} gepland deze ${viewMode === "week" ? "week" : "maand"}`}
      >
        Weekplanner
      </PageTitle>

      <div className="flex items-center justify-between gap-2">
        <button
          onClick={() => setCursor(viewMode === "week" ? addDays(cursor, -7) : addMonths(cursor, -1))}
          className={iconButtonClass}
          aria-label="Vorige"
        >
          <IconChevronLeft size={20} />
        </button>
        <span className="text-center text-[15px] font-semibold capitalize text-ui-ink">{label}</span>
        <button
          onClick={() => setCursor(viewMode === "week" ? addDays(cursor, 7) : addMonths(cursor, 1))}
          className={iconButtonClass}
          aria-label="Volgende"
        >
          <IconChevronRight size={20} />
        </button>
      </div>

      {/* Below `sm` every day is a full-width row (weekday + date on the left, the plan on the
          right) instead of a ~44px-wide grid cell -- 7 columns on a phone screen leaves no room
          for a recipe title, a weekday name, or even a comfortable tap target. Month view's
          leading/trailing days from adjacent months only exist to keep the calendar's column
          alignment, so they're dropped from that stacked list rather than shown as empty rows. */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-7">
        {viewMode === "month" &&
          WEEKDAY_LABELS.map((label) => (
            <div
              key={label}
              className="hidden text-center text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted sm:block"
            >
              {label}
            </div>
          ))}
        {days.map((dateIso) => {
          const entry = entriesByDate.get(dateIso);
          const isOutsideMonth = viewMode === "month" && (dateIso < monthStart || dateIso > endOfMonth(cursor));
          const isToday = dateIso === today;
          const d = fromIso(dateIso);
          return (
            <div
              key={dateIso}
              onClick={() => setEditingDate(dateIso)}
              className={`min-h-[56px] cursor-pointer items-center gap-3 rounded-2xl border px-4 py-2 text-left transition-colors hover:border-ui-line sm:min-h-[96px] sm:flex-col sm:items-stretch sm:gap-1.5 sm:px-2.5 ${
                isOutsideMonth ? "hidden border-ui-border bg-ui-tile sm:flex" : "flex border-ui-border bg-ui-surface"
              } ${isToday ? "border-ui-brand ring-1 ring-ui-brand" : ""}`}
            >
              <span
                className={`w-24 shrink-0 text-sm font-semibold sm:w-auto sm:text-xs ${
                  isOutsideMonth ? "text-ui-faint" : isToday ? "text-ui-brand-strong" : "text-ui-muted"
                }`}
              >
                {/* The stacked mobile row has no column header to say which weekday a date
                    falls on, so it always spells that out -- the cramped grid cell keeps the
                    terser version (bare day number in month view, since the header row above
                    already names the weekday there). */}
                <span className="sm:hidden">
                  {d.toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" })}
                </span>
                <span className="hidden sm:inline">
                  {viewMode === "week"
                    ? d.toLocaleDateString("nl-NL", { weekday: "short", day: "numeric" })
                    : d.getDate()}
                </span>
              </span>
              {entry?.recipe_title ? (
                <div className="flex min-w-0 flex-1 items-center justify-between gap-1 sm:flex-none sm:items-start">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/listr/recept/${entry.recipe_id}`);
                    }}
                    className="min-w-0 truncate text-left text-[15px] font-semibold text-ui-ink hover:underline sm:text-xs"
                    title={entry.recipe_title}
                  >
                    {entry.recipe_title}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleCookedMutation.mutate({ date: dateIso, entry });
                    }}
                    title={entry.is_cooked ? "Gekookt" : "Markeer als gekookt"}
                    aria-label={entry.is_cooked ? "Gekookt" : "Markeer als gekookt"}
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border sm:h-6 sm:w-6 ${
                      entry.is_cooked ? "border-ui-brand bg-ui-brand text-white" : "border-ui-line text-ui-faint hover:text-ui-muted"
                    }`}
                  >
                    <IconCheck size={14} strokeWidth={3} />
                  </button>
                </div>
              ) : entry?.notes ? (
                <span className="min-w-0 flex-1 truncate text-sm italic text-ui-muted sm:flex-none sm:text-xs">
                  {entry.notes}
                </span>
              ) : (
                !isOutsideMonth && (
                  <span className="flex-1 text-sm text-ui-faint sm:flex-none sm:text-xs">+ plannen</span>
                )
              )}
            </div>
          );
        })}
      </div>

      <button
        onClick={() => setAddingToList(true)}
        disabled={plannedMeals.length === 0}
        className={`${primaryButtonClass} sm:self-end`}
      >
        <ShoppingCart className="h-[18px] w-[18px]" strokeWidth={2} />
        Boodschappenlijst van deze {viewMode === "week" ? "week" : "maand"}
      </button>

      <div className="rounded-[20px] border border-ui-border bg-ui-surface p-4">
        <div className="flex items-center gap-2">
          <Trophy className="h-5 w-5 text-ui-brand" strokeWidth={2} />
          <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">Populairste recepten</h2>
        </div>
        {!popularQuery.data || popularQuery.data.length === 0 ? (
          <div className="mt-2 text-sm text-ui-muted">
            Nog niets gekookt — vink een geplande maaltijd af om deze lijst te vullen.
          </div>
        ) : (
          <ul className="mt-2 flex flex-col text-[15px]">
            {popularQuery.data.map((recipe, i) => (
              <li key={recipe.recipe_id} className="flex min-h-[44px] items-center justify-between gap-2 border-b border-ui-border last:border-0">
                <button
                  onClick={() => navigate(`/listr/recept/${recipe.recipe_id}`)}
                  className="flex min-w-0 items-center gap-2 truncate text-left text-ui-ink hover:underline"
                >
                  <span className="w-5 shrink-0 text-right text-sm font-semibold text-ui-muted">{i + 1}</span>
                  <span className="truncate">{recipe.title}</span>
                </button>
                <span className="shrink-0 tabular-nums text-sm text-ui-muted">
                  {recipe.times_cooked}× gekookt
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {editingDate && (
        <MealDayDialog
          date={editingDate}
          entry={entriesByDate.get(editingDate)}
          isSubmitting={saveMutation.isPending || clearMutation.isPending}
          onCancel={() => setEditingDate(null)}
          onSave={(input) => saveMutation.mutate({ date: editingDate, input })}
          onClear={() => clearMutation.mutate(editingDate)}
        />
      )}

      {addingToList && (
        <AddWeekToListDialog
          meals={plannedMeals}
          defaultListName={`Boodschappen ${label}`}
          isSubmitting={addToListMutation.isPending}
          onCancel={() => setAddingToList(false)}
          onSubmit={(input) => addToListMutation.mutate(input)}
        />
      )}
    </div>
  );
}
