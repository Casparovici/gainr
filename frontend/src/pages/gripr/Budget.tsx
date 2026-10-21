import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { Check, Link2, PiggyBank, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";

import { griprApi } from "../../api/griprClient";
import type {
  GriprAccount,
  GriprBudgetLine,
  GriprBudgetSuggestion,
  GriprCategory,
  GriprCategoryKind,
  GriprSavingsGoalLine,
  GriprSavingsGoalSuggestion,
  GriprSavingsRoom,
} from "../../api/griprTypes";
import BudgetCell from "../../components/gripr/BudgetCell";
import CategoryDetailDialog from "../../components/gripr/CategoryDetailDialog";
import NewCategoryForm from "../../components/gripr/NewCategoryForm";
import PeriodSwitcher, { formatPeriodLabel } from "../../components/gripr/PeriodSwitcher";
import { ModuleTopRow, PageTitle } from "../../components/ui/kit";
import { QueryError } from "../../components/ui/QueryError";
import ProgressBar from "../../components/gripr/ProgressBar";
import { buildCategoryColorMap } from "../../utils/categoryColor";
import { CategoryGlyph } from "../../utils/categoryIcons";
import { formatEur, toNumber } from "../../utils/format";
import { currentPeriodStart, periodBounds } from "../../utils/griprPeriod";
import { t, tp } from "../../i18n";

/** How a line is doing against its number, in words -- spend against a cap, receipts against a
 * target, savings against a goal. One function so the kinds can't drift into inconsistent
 * wording: "Left € 461,38" / "Over by € 12,00" for spending; "Ahead by" / "Behind by" for income
 * and savings, where more is better. */
function remainingText(kind: GriprCategoryKind, actual: number, budgeted: number): { text: string; bad: boolean } {
  const remaining = kind === "income" ? actual - budgeted : budgeted - actual;
  if (kind === "income") {
    const amount = formatEur(Math.abs(remaining));
    return { text: remaining < 0 ? t("Behind by {amount}", { amount }) : t("Ahead by {amount}", { amount }), bad: remaining < 0 };
  }
  return remaining < 0
    ? { text: t("Over by {amount}", { amount: formatEur(-remaining) }), bad: true }
    : { text: t("Left {amount}", { amount: formatEur(remaining) }), bad: false };
}

/** One budget line as a quiet two-line row: icon, name and "actual of budget" on top, the
 * progress bar and what's left underneath. Shared by category lines and savings goals. */
function BudgetRow({
  icon,
  name,
  marker,
  kind,
  actualLabel,
  actual,
  budgeted,
  budgetCell,
  rowProps,
  highlighted = false,
}: {
  icon: React.ReactNode;
  name: string;
  marker?: React.ReactNode;
  kind: GriprCategoryKind;
  /** "Spent" / "Received" / "Saved" -- said outright on every row, not left to the reader. */
  actualLabel: string;
  actual: number;
  budgeted: number;
  budgetCell: React.ReactNode;
  /** Click/drag/keyboard handlers for a row that opens something; absent for a static row. */
  rowProps?: React.LiHTMLAttributes<HTMLLIElement>;
  highlighted?: boolean;
}) {
  const status = budgeted > 0 ? remainingText(kind, actual, budgeted) : null;
  return (
    <li
      {...rowProps}
      className={`flex items-center gap-3 border-t border-outline-variant px-4 py-2 sm:py-2.5 lg:odd:border-r ${
        rowProps ? "cursor-pointer" : ""
      } ${highlighted ? "bg-primary-container" : rowProps ? "hover:bg-surface-container" : ""}`}
    >
      {icon}
      {/* Wider screens: name + figures on one line, bar + what's left on the next. On a phone the
          figures would squeeze the name to a few letters, so they drop to a third line of their
          own, in smaller type: name / bar + what's left / spent of budget. Grid areas rather than two copies of the
          markup, so the budget editor exists once. */}
      <div className="grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 [grid-template-areas:'name_name'_'bar_status'_'figures_figures'] sm:[grid-template-areas:'name_figures'_'bar_status']">
        <span className="flex min-w-0 items-center gap-1.5 [grid-area:name]">
          <span className="truncate text-sm text-on-surface">{name}</span>
          {marker}
        </span>
        {/* Editing the number is its own action, not a click through to the row's dialog. */}
        <span
          className="flex min-w-0 items-baseline gap-1 whitespace-nowrap text-xs tabular-nums [grid-area:figures] sm:justify-self-end sm:text-sm"
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
          <span className="text-xs text-on-surface-variant">{actualLabel}</span>
          <span className="font-medium text-on-surface">{formatEur(actual)}</span>
          <span className="text-xs text-on-surface-variant">{t("of")}</span>
          {budgetCell}
        </span>
        <div className="[grid-area:bar]">
          <ProgressBar spent={actual} budgeted={budgeted} kind={kind} />
        </div>
        {status && (
          <span className={`justify-self-end whitespace-nowrap text-xs tabular-nums [grid-area:status] ${status.bad ? "text-error" : "text-on-surface-variant"}`}>
            {status.text}
          </span>
        )}
      </div>
    </li>
  );
}

/** The tab's totals, closing the list like a statement's bottom line (same place Accounts puts
 * net worth). */
function TotalsSummary({ kind, actual, budgeted, actualLabel }: { kind: GriprCategoryKind; actual: number; budgeted: number; actualLabel: string }) {
  const status = budgeted > 0 ? remainingText(kind, actual, budgeted) : null;
  return (
    <section className="rounded-2xl border border-outline-variant bg-surface px-4 py-3" aria-label={t("Totals")}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm text-on-surface-variant">{actualLabel}{" "}{t("this period")}</span>
        <span className="tabular-nums">
          <span className="text-lg font-semibold text-on-surface">{formatEur(actual)}</span>{" "}
          <span className="text-sm text-on-surface-variant">{t("of {amount}", { amount: formatEur(budgeted) })}</span>
        </span>
      </div>
      <div className="mt-2">
        <ProgressBar spent={actual} budgeted={budgeted} kind={kind} />
      </div>
      {status && (
        <div className={`mt-1 text-right text-xs tabular-nums ${status.bad ? "text-error" : "text-on-surface-variant"}`}>{status.text}</div>
      )}
    </section>
  );
}

function CategoryIcon({ name, color, dimmed = false }: { name: string; color: string; dimmed?: boolean }) {
  return (
    <span
      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${dimmed ? "opacity-50" : ""}`}
      style={{ backgroundColor: color }}
    >
      <CategoryGlyph name={name} className="h-3.5 w-3.5 text-white" strokeWidth={2.25} />
    </span>
  );
}

/** A tab's list: one card of rows, two columns of rows on a wide screen. The wrapper clips the
 * first row's top border so it doesn't double up with the card's own. */
function RowCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant bg-surface">
      <ul className="-mt-px lg:grid lg:grid-cols-2">{children}</ul>
    </div>
  );
}

function BudgetSection({
  kind,
  lines,
  colorOf,
  suggestionByCategory,
  linkedLoanNameOf,
  archived,
  onOpen,
  onAdd,
  draggedId,
  dragOverId,
  onDragStart,
  onDragOver,
  onDragEnd,
  onDrop,
  onSaveBudget,
}: {
  kind: GriprCategoryKind;
  lines: GriprBudgetLine[];
  colorOf: Map<number, string>;
  suggestionByCategory: Map<number, GriprBudgetSuggestion>;
  /** The loan a category pays off, if linked -- shown as a small marker on its row. */
  linkedLoanNameOf: (categoryId: number) => string | null;
  /** This kind's archived top-level categories, which have no budget line of their own. */
  archived: GriprCategory[];
  onOpen: (categoryId: number) => void;
  onAdd: () => void;
  draggedId: number | null;
  dragOverId: number | null;
  onDragStart: (id: number) => void;
  onDragOver: (id: number) => void;
  onDragEnd: () => void;
  onDrop: (lines: GriprBudgetLine[], targetId: number) => void;
  onSaveBudget: (categoryId: number, amount: string) => void;
}) {
  const totalBudgeted = lines.reduce((sum, l) => sum + (toNumber(l.budgeted) ?? 0), 0);
  const totalActual = lines.reduce((sum, l) => sum + (toNumber(l.spent) ?? 0), 0);
  const [showArchived, setShowArchived] = useState(false);

  return (
    <div className="flex flex-col gap-3">
      {lines.length === 0 ? (
        <p className="text-sm text-on-surface-variant">{kind === "income"
            ? t("No income categories yet — add your first one below.")
            : t("No expense categories yet — add your first one below.")}</p>
      ) : (
        <RowCard>
          {lines.map((line) => {
            const linkedLoan = linkedLoanNameOf(line.category_id);
            return (
              <BudgetRow
                key={line.category_id}
                icon={<CategoryIcon name={line.category_name} color={colorOf.get(line.category_id) ?? "#94a3b8"} />}
                name={line.category_name}
                marker={
                  linkedLoan && (
                    <span className="shrink-0 text-on-surface-variant" title={t("Pays off {loan}", { loan: linkedLoan })} aria-label={t("Pays off {loan}", { loan: linkedLoan })}>
                      <Link2 className="h-3.5 w-3.5" strokeWidth={2} />
                    </span>
                  )
                }
                kind={kind}
                actualLabel={kind === "income" ? t("Received") : t("Spent")}
                actual={toNumber(line.spent) ?? 0}
                budgeted={toNumber(line.budgeted) ?? 0}
                highlighted={dragOverId === line.category_id && draggedId !== line.category_id}
                budgetCell={
                  <BudgetCell
                    compact
                    value={line.budgeted}
                    kind={kind}
                    suggestion={suggestionByCategory.get(line.category_id)}
                    onSave={(amount) => onSaveBudget(line.category_id, amount)}
                  />
                }
                rowProps={{
                  role: "button",
                  tabIndex: 0,
                  "aria-label": t("{category}: transactions and settings", { category: line.category_name }),
                  title: t("Drag to reorder"),
                  onClick: () => onOpen(line.category_id),
                  onKeyDown: (e) => {
                    if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      onOpen(line.category_id);
                    }
                  },
                  draggable: true,
                  onDragStart: () => onDragStart(line.category_id),
                  onDragEnd,
                  onDragOver: (e) => {
                    e.preventDefault();
                    if (dragOverId !== line.category_id) onDragOver(line.category_id);
                  },
                  onDrop: () => onDrop(lines, line.category_id),
                }}
              />
            );
          })}
        </RowCard>
      )}

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
        <button type="button" onClick={onAdd} className="text-sm font-medium text-primary hover:underline">{t("+ Add category")}</button>
        {archived.length > 0 && (
          <button
            type="button"
            onClick={() => setShowArchived((x) => !x)}
            className="text-sm font-medium text-on-surface-variant hover:text-on-surface hover:underline"
          >
            {showArchived
              ? t("Hide archived categories")
              : tp(archived.length, "Show {n} archived category", "Show {n} archived categories")}
          </button>
        )}
      </div>

      {showArchived && archived.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-outline-variant bg-surface">
          <ul className="-mt-px">
            {archived.map((category) => (
              <li key={category.id} className="border-t border-outline-variant">
                <button
                  type="button"
                  onClick={() => onOpen(category.id)}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-surface-container"
                >
                  <CategoryIcon name={category.name} color={colorOf.get(category.id) ?? category.color ?? "#94a3b8"} dimmed />
                  <span className="min-w-0 flex-1 truncate text-sm text-on-surface-variant">{category.name}</span>
                  <span className="shrink-0 rounded-full bg-surface-container-high px-2 py-0.5 text-[10px] text-on-surface-variant">{t("archived")}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {lines.length > 0 && (
        <TotalsSummary kind={kind} actual={totalActual} budgeted={totalBudgeted} actualLabel={kind === "income" ? t("Received") : t("Spent")} />
      )}
    </div>
  );
}

/** What the period's budget leaves for saving and investing: budgeted income minus budgeted
 * expenses, set against what the savings goals below already plan to take. The server works the
 * figures out; this only says them. */
function SavingsRoomCard({ room }: { room: GriprSavingsRoom }) {
  const income = toNumber(room.income_budgeted) ?? 0;
  const expenses = toNumber(room.expense_budgeted) ?? 0;
  const roomAmount = toNumber(room.room) ?? 0;
  const goals = toNumber(room.goals_budgeted) ?? 0;
  const unallocated = toNumber(room.unallocated) ?? 0;
  const nothingBudgeted = income === 0 && expenses === 0;

  return (
    <section className="rounded-2xl border border-outline-variant bg-surface px-4 py-3" aria-label={t("Room to save")}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm text-on-surface-variant">{t("Room to save this period")}</span>
        <span className={`text-lg font-semibold tabular-nums ${roomAmount < 0 ? "text-error" : "text-on-surface"}`}>
          {formatEur(roomAmount)}
        </span>
      </div>
      {nothingBudgeted ? (
        <p className="mt-1 text-xs text-on-surface-variant">
          {t("Budget your income and expenses first, and what's left to save shows here.")}
        </p>
      ) : (
        <>
          <p className="mt-1 text-xs tabular-nums text-on-surface-variant">
            {t("{income} income budgeted − {expenses} expenses budgeted", {
              income: formatEur(income),
              expenses: formatEur(expenses),
            })}
          </p>
          {roomAmount < 0 ? (
            <p role="status" className="mt-2 text-xs text-error">
              {t("The budgeted expenses are more than the budgeted income, so there's nothing left to save.")}
            </p>
          ) : (
            <p
              role="status"
              className={`mt-2 border-t border-outline-variant pt-2 text-xs tabular-nums ${unallocated < 0 ? "text-error" : "text-on-surface-variant"}`}
            >
              {unallocated < 0
                ? t("The goals below plan {amount} more than the budget leaves.", { amount: formatEur(-unallocated) })
                : t("{goals} planned in the goals below, {amount} not planned yet.", {
                    goals: formatEur(goals),
                    amount: formatEur(unallocated),
                  })}
            </p>
          )}
        </>
      )}
    </section>
  );
}

/** Savings & Investments' own list -- same rows and totals as BudgetSection, keyed by account
 * rather than category (no dialog, no drag-to-reorder: an account's order and settings live on
 * the Accounts page). */
function SavingsSection({
  lines,
  roomQuery,
  suggestionByAccount,
  onSaveGoal,
}: {
  lines: GriprSavingsGoalLine[];
  roomQuery: UseQueryResult<GriprSavingsRoom>;
  suggestionByAccount: Map<number, GriprSavingsGoalSuggestion>;
  onSaveGoal: (accountId: number, amount: string) => void;
}) {
  const totalBudgeted = lines.reduce((sum, l) => sum + (toNumber(l.budgeted) ?? 0), 0);
  const totalActual = lines.reduce((sum, l) => sum + (toNumber(l.saved) ?? 0), 0);

  const roomCard = roomQuery.isError ? (
    <QueryError
      className="rounded-2xl border border-outline-variant bg-surface px-4 py-3 text-sm"
      message={t("Couldn't work out how much room there is to save.")}
      onRetry={() => roomQuery.refetch()}
    />
  ) : roomQuery.data ? (
    <SavingsRoomCard room={roomQuery.data} />
  ) : (
    <div className="h-[72px] animate-pulse rounded-2xl border border-outline-variant bg-surface-container" aria-label={t("Loading…")} />
  );

  if (lines.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        {roomCard}
        <div className="rounded-2xl border border-dashed border-outline-variant px-4 py-6 text-center text-sm text-on-surface-variant">{t("No savings or investment accounts yet — add one on the Accounts page.")}</div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {roomCard}
      <RowCard>
        {lines.map((line) => {
          const Icon = line.account_type === "investment" ? TrendingUp : PiggyBank;
          return (
            <BudgetRow
              key={line.account_id}
              icon={
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary">
                  <Icon className="h-3.5 w-3.5 text-white" strokeWidth={2.25} />
                </span>
              }
              name={line.account_name}
              kind="income"
              actualLabel={t("Saved")}
              actual={toNumber(line.saved) ?? 0}
              budgeted={toNumber(line.budgeted) ?? 0}
              budgetCell={
                <BudgetCell
                  compact
                  value={line.budgeted}
                  kind="income"
                  suggestion={suggestionByAccount.get(line.account_id)}
                  onSave={(amount) => onSaveGoal(line.account_id, amount)}
                />
              }
            />
          );
        })}
      </RowCard>
      <TotalsSummary kind="income" actual={totalActual} budgeted={totalBudgeted} actualLabel={t("Saved")} />
    </div>
  );
}

export default function GriprBudget() {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({ queryKey: ["gripr-settings"], queryFn: () => griprApi.getSettings() });
  const startDay = settingsQuery.data?.period_start_day ?? 1;
  // Seeded only once settings have loaded -- guessing a calendar-month default first and
  // correcting it afterward would send the wrong period to the backend whenever the configured
  // start day has already been passed this month but isn't the 1st (see PeriodSwitcher).
  const [month, setMonth] = useState<string | null>(null);
  useEffect(() => {
    if (settingsQuery.data && month === null) setMonth(currentPeriodStart(settingsQuery.data.period_start_day));
  }, [settingsQuery.data, month]);
  const [draggedId, setDraggedId] = useState<number | null>(null);
  const [dragOverId, setDragOverId] = useState<number | null>(null);
  // One section visible at a time instead of three independently-collapsible cards -- on a
  // narrow screen that meant scrolling past Expenses' whole tile grid just to glance at
  // Savings; a segmented switch shows one focused grid instead, no scrolling required.
  const [tab, setTab] = useState<GriprCategoryKind | "savings">("expense");
  // The category whose detail dialog is open -- held as an id and looked up fresh from the
  // query below, so a rename or recolour made inside the dialog shows up in it right away.
  const [viewingCategoryId, setViewingCategoryId] = useState<number | null>(null);
  const [newKind, setNewKind] = useState<GriprCategoryKind | null>(null);

  const budgetsKey = ["gripr-budgets", month] as const;
  const { data: lines, isLoading, isError, refetch } = useQuery({
    queryKey: budgetsKey,
    queryFn: () => griprApi.getBudgets(month as string),
    enabled: month !== null,
  });
  const { data: categories } = useQuery({
    queryKey: ["gripr-categories"],
    queryFn: () => griprApi.listCategories(),
  });
  // Archived ones included: archived top-level categories get their own (collapsed) list per
  // tab, and a category's dialog manages its archived subcategories too.
  const { data: allCategories } = useQuery({
    queryKey: ["gripr-categories", "with-archived"],
    queryFn: () => griprApi.listCategories(true),
  });
  const { data: accounts } = useQuery({ queryKey: ["gripr-accounts", false], queryFn: () => griprApi.listAccounts() });
  const createCategoryMutation = useMutation({
    mutationFn: (input: { name: string; kind: GriprCategoryKind; parent_id: number | null }) =>
      griprApi.createCategory(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["gripr-categories"] });
      queryClient.invalidateQueries({ queryKey: budgetsKey });
      setNewKind(null);
    },
  });
  const { data: suggestions } = useQuery({
    queryKey: ["gripr-budget-suggestions", month],
    queryFn: () => griprApi.getBudgetSuggestions(month as string),
    enabled: month !== null,
  });
  const suggestionByCategory = new Map((suggestions ?? []).map((s) => [s.category_id, s]));

  const savingsGoalsKey = ["gripr-savings-goals", month] as const;
  const savingsQuery = useQuery({
    queryKey: savingsGoalsKey,
    queryFn: () => griprApi.getSavingsGoals(month as string),
    enabled: month !== null,
  });
  const { data: savingsSuggestions } = useQuery({
    queryKey: ["gripr-savings-goal-suggestions", month],
    queryFn: () => griprApi.getSavingsGoalSuggestions(month as string),
    enabled: month !== null,
  });
  const suggestionByAccount = new Map((savingsSuggestions ?? []).map((s) => [s.account_id, s]));

  // Under "gripr-budgets" so every place that changes a budget (a category's dialog, a transaction
  // that moves a refund) refreshes it with the lines.
  const savingsRoomKey = ["gripr-budgets", "savings-room", month] as const;
  const savingsRoomQuery = useQuery({
    queryKey: savingsRoomKey,
    queryFn: () => griprApi.getSavingsRoom(month as string),
    enabled: month !== null,
  });

  const setBudgetMutation = useMutation({
    mutationFn: ({ categoryId, amount }: { categoryId: number; amount: string }) =>
      griprApi.setBudget(categoryId, month as string, amount),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: budgetsKey });
      queryClient.invalidateQueries({ queryKey: savingsRoomKey });
    },
  });
  const setSavingsGoalMutation = useMutation({
    mutationFn: ({ accountId, amount }: { accountId: number; amount: string }) =>
      griprApi.setSavingsGoal(accountId, month as string, amount),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: savingsGoalsKey });
      queryClient.invalidateQueries({ queryKey: savingsRoomKey });
    },
  });
  // Reordering here changes the category's own sort_order, so it's applied optimistically to
  // this month's line list for a snappy drag, then invalidated everywhere that order is read —
  // including Categories, which shows the same tiles in the same order.
  const reorderMutation = useMutation({
    mutationFn: (categoryIds: number[]) => griprApi.reorderCategories(categoryIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["gripr-categories"] }),
    onError: () => queryClient.invalidateQueries({ queryKey: budgetsKey }),
  });

  // `sectionLines` scopes both the source and target lookup to the section being dragged
  // within — sort_order is only ever compared within one kind (see GriprCategory), so a drag
  // can't reorder expense against income anyway; this just keeps the id list consistent with
  // that.
  function handleDrop(sectionLines: GriprBudgetLine[], targetCategoryId: number) {
    const sourceCategoryId = draggedId;
    setDraggedId(null);
    setDragOverId(null);
    if (sourceCategoryId === null || sourceCategoryId === targetCategoryId) return;

    const ids = sectionLines.map((l) => l.category_id);
    const fromIdx = ids.indexOf(sourceCategoryId);
    const toIdx = ids.indexOf(targetCategoryId);
    if (fromIdx === -1 || toIdx === -1) return;
    ids.splice(toIdx, 0, ids.splice(fromIdx, 1)[0]);

    queryClient.setQueryData<GriprBudgetLine[]>(budgetsKey, (old) => {
      if (!old) return old;
      const byId = new Map(old.map((l) => [l.category_id, l]));
      const reordered = ids.map((id) => byId.get(id)!);
      // Splice the reordered section back into the full (mixed-kind) list, other kind's lines
      // untouched and in their original relative positions.
      const otherLines = old.filter((l) => l.kind !== sectionLines[0]?.kind);
      return [...reordered, ...otherLines];
    });
    reorderMutation.mutate(ids);
  }

  const savingsLines = savingsQuery.data;

  if (month === null && settingsQuery.isError) {
    return (
      <QueryError
        className="rounded-2xl border border-outline-variant bg-surface px-4 py-6 text-center"
        message={t("Couldn't load your period settings, so there's no budget period to show.")}
        onRetry={() => settingsQuery.refetch()}
      />
    );
  }
  if (month === null) {
    return <div className="rounded-2xl border border-outline-variant bg-surface px-4 py-6 text-center text-on-surface-variant">{t("Loading…")}</div>;
  }

  const colorOf = buildCategoryColorMap(categories ?? []);
  const expenseLines = (lines ?? []).filter((l) => l.kind === "expense");
  const incomeLines = (lines ?? []).filter((l) => l.kind === "income");

  const loanAccounts = (accounts ?? []).filter((a) => a.type === "loan");
  const accountsById = new Map<number, GriprAccount>((accounts ?? []).map((a) => [a.id, a]));
  const categoriesById = new Map((allCategories ?? []).map((c) => [c.id, c]));
  const linkedLoanNameOf = (categoryId: number): string | null => {
    const loanId = categoriesById.get(categoryId)?.linked_loan_account_id;
    if (loanId == null) return null;
    return accountsById.get(loanId)?.name ?? t("a deleted account");
  };
  const archivedOf = (kind: GriprCategoryKind) =>
    (allCategories ?? []).filter((c) => c.kind === kind && c.parent_id === null && c.is_archived);
  const viewingCategory = viewingCategoryId !== null ? categoriesById.get(viewingCategoryId) : undefined;

  return (
    <div className="flex flex-col gap-6">
      <div className="-mb-2 flex flex-col gap-4">
        <div className="sm:hidden">
          <ModuleTopRow settings={false} />
        </div>
        <div className="flex flex-wrap items-end justify-between gap-x-3 gap-y-2">
          <PageTitle>{t("Budget")}</PageTitle>
          <PeriodSwitcher periodStart={month} startDay={startDay} onChange={setMonth} />
        </div>
      </div>

      {/* M3's SegmentedButton -- one outlined container, a shared border between segments, the
          selected one filled with secondary-container and marked with a check, replacing three
          stacked collapsible cards with one focused view at a time. */}
      <div className="inline-flex self-start overflow-hidden rounded-full border border-outline">
        {(
          [
            ["expense", t("Expenses")],
            ["income", t("Income")],
            ["savings", t("Savings")],
          ] as const
        ).map(([key, label], i) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium transition-colors ${
              i > 0 ? "border-l border-outline" : ""
            } ${tab === key ? "bg-secondary-container text-on-secondary-container" : "text-on-surface hover:bg-on-surface/5"}`}
          >
            {tab === key && <Check className="h-4 w-4" strokeWidth={2.5} />}
            {label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="rounded-2xl border border-outline-variant bg-surface px-4 py-6 text-center text-on-surface-variant">{t("Loading…")}</div>
      ) : tab !== "savings" && isError ? (
        <QueryError
          className="rounded-2xl border border-outline-variant bg-surface px-4 py-6 text-center"
          message={t("Couldn't load this period's budget.")}
          onRetry={() => refetch()}
        />
      ) : tab === "savings" && savingsQuery.isError ? (
        <QueryError
          className="rounded-2xl border border-outline-variant bg-surface px-4 py-6 text-center"
          message={t("Couldn't load this period's savings goals.")}
          onRetry={() => savingsQuery.refetch()}
        />
      ) : tab === "expense" ? (
        <BudgetSection
          kind="expense"
          lines={expenseLines}
          archived={archivedOf("expense")}
          onAdd={() => setNewKind("expense")}
          colorOf={colorOf}
          suggestionByCategory={suggestionByCategory}
          linkedLoanNameOf={linkedLoanNameOf}
          onOpen={setViewingCategoryId}
          draggedId={draggedId}
          dragOverId={dragOverId}
          onDragStart={setDraggedId}
          onDragOver={setDragOverId}
          onDragEnd={() => {
            setDraggedId(null);
            setDragOverId(null);
          }}
          onDrop={handleDrop}
          onSaveBudget={(categoryId, amount) => setBudgetMutation.mutate({ categoryId, amount })}
        />
      ) : tab === "income" ? (
        <BudgetSection
          kind="income"
          lines={incomeLines}
          archived={archivedOf("income")}
          onAdd={() => setNewKind("income")}
          colorOf={colorOf}
          suggestionByCategory={suggestionByCategory}
          linkedLoanNameOf={linkedLoanNameOf}
          onOpen={setViewingCategoryId}
          draggedId={draggedId}
          dragOverId={dragOverId}
          onDragStart={setDraggedId}
          onDragOver={setDragOverId}
          onDragEnd={() => {
            setDraggedId(null);
            setDragOverId(null);
          }}
          onDrop={handleDrop}
          onSaveBudget={(categoryId, amount) => setBudgetMutation.mutate({ categoryId, amount })}
        />
      ) : (
        <SavingsSection
          lines={savingsLines ?? []}
          roomQuery={savingsRoomQuery}
          suggestionByAccount={suggestionByAccount}
          onSaveGoal={(accountId, amount) => setSavingsGoalMutation.mutate({ accountId, amount })}
        />
      )}

      {newKind && (
        <NewCategoryForm
          kind={newKind}
          parents={(categories ?? []).filter((c) => c.kind === newKind && c.parent_id === null)}
          isSubmitting={createCategoryMutation.isPending}
          onCancel={() => setNewKind(null)}
          onSubmit={(input) => createCategoryMutation.mutate(input)}
        />
      )}

      {viewingCategory && (
        <CategoryDetailDialog
          key={viewingCategory.id}
          category={viewingCategory}
          color={colorOf.get(viewingCategory.id) ?? viewingCategory.color ?? "#94a3b8"}
          subcategories={(allCategories ?? []).filter((c) => c.parent_id === viewingCategory.id)}
          loanAccounts={loanAccounts}
          periodStart={month}
          periodEnd={periodBounds(month, startDay).end}
          periodLabel={formatPeriodLabel(month, startDay)}
          accounts={accounts ?? []}
          categories={categories ?? []}
          accountsById={accountsById}
          onClose={() => setViewingCategoryId(null)}
        />
      )}
    </div>
  );
}
