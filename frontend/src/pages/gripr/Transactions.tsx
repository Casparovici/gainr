import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, Pencil, Repeat, Trash2, Undo2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { griprApi } from "../../api/griprClient";
import type {
  GriprAccount,
  GriprCategory,
  GriprPlannedOccurrence,
  GriprTransaction,
  GriprTransactionInput,
  GriprTransactionType,
} from "../../api/griprTypes";
import AccountBadge from "../../components/gripr/AccountBadge";
import GriprTransactionForm from "../../components/gripr/GriprTransactionForm";
import GriprButton from "../../components/gripr/GriprButton";
import MobileFab from "../../components/MobileFab";
import { ModuleTopRow, PageTitle, secondaryButtonClass } from "../../components/ui/kit";
import CollapsibleCard from "../../components/CollapsibleCard";
import { useConfirmDialog } from "../../components/gripr/useConfirmDialog";
import { buildCategoryColorMap } from "../../utils/categoryColor";
import { categoryIcon } from "../../utils/categoryIcons";
import { addDaysIso, decimalInputToApi, formatDate, formatEur, pnlColorClass, todayIsoDate } from "../../utils/format";
import { GRIPR_TYPE_BADGE, GRIPR_TYPE_OPTIONS, griprSignedAmount } from "../../utils/griprTransactionType";

const PAGE_SIZE = 50;
// The category filter's "no category yet" choice -- not a real category id.
const UNCATEGORIZED = "uncategorized";
// M3 filter chips: 8dp corner radius (not the fully-rounded pill buttons/segmented controls get)
// -- still plain native `<select>`/`<input>` elements, so keyboard/screen-reader support comes
// free, per this app's own UX conventions; a custom popover would have to rebuild all of that.
const chipClass =
  "shrink-0 rounded-lg border border-outline bg-surface px-3 py-2 text-sm font-medium text-on-surface-variant focus:outline-none focus:ring-2 focus:ring-primary";

/** The amount as booked, plus -- for an expense some of which came back -- what came back, so
 * a €60 dinner someone paid half of reads as costing €30 without doing the math. */
function AmountWithRefunds({ t }: { t: GriprTransaction }) {
  const refunded = parseFloat(t.refunded_amount);
  return (
    <span className="flex flex-col items-end">
      <span
        className={`tabular-nums text-sm font-medium ${t.type === "transfer" ? "text-on-surface-variant" : pnlColorClass(griprSignedAmount(t))}`}
      >
        {t.type === "transfer" ? formatEur(t.amount) : formatEur(griprSignedAmount(t))}
      </span>
      {refunded > 0 && (
        <span className="whitespace-nowrap text-xs text-on-surface-variant" title={`Net cost ${formatEur(parseFloat(t.amount) - refunded)}`}>
          {formatEur(refunded)} back
        </span>
      )}
      {parseFloat(t.outstanding) > 0 && (
        <span className="whitespace-nowrap text-xs text-on-surface-variant" title={t.expected_from ? `Owed by ${t.expected_from}` : undefined}>
          {formatEur(t.outstanding)} to come back
        </span>
      )}
    </span>
  );
}

/** For a linked refund's badge: what it came back for. */
function refundTitle(t: GriprTransaction): string | undefined {
  if (!t.refund_of) return undefined;
  const what = t.refund_of.notes || "expense";
  return `Money back for ${what} (${formatEur(t.refund_of.amount)}, ${formatDate(t.refund_of.date)})`;
}

/** Splits a transaction's (possibly leaf-level) category into its top-level category and,
 * separately, the subcategory it's actually filed under, if any. */
function resolveCategory(categoryId: number | null, categoriesById: Map<number, GriprCategory>) {
  if (categoryId === null) return { top: null, sub: null };
  const category = categoriesById.get(categoryId);
  if (!category) return { top: null, sub: null };
  if (category.parent_id === null) return { top: category, sub: null };
  return { top: categoriesById.get(category.parent_id) ?? null, sub: category };
}

/** A recurring rule's occurrence that isn't booked yet, in the Upcoming card: the same fields as a
 * booked row, but quieter (dashed "planned" chip, muted amount) and not editable as a
 * transaction -- it isn't one yet. It links to Recurring, where the rule itself is edited. */
function PlannedRow({
  occurrence: p,
  categoryName,
  accountsById,
}: {
  occurrence: GriprPlannedOccurrence;
  categoryName: string | undefined;
  accountsById: Map<number, GriprAccount>;
}) {
  const signed = griprSignedAmount(p);
  return (
    <li className="py-2 text-sm">
      <Link to="/gripr/recurring" className="flex items-start justify-between gap-3 text-inherit no-underline hover:bg-on-surface/5 sm:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="rounded-full border border-dashed border-outline px-2 py-0.5 text-xs font-medium text-on-surface-variant">
              planned
            </span>
            <Repeat className="h-3.5 w-3.5 shrink-0 text-on-surface-variant" strokeWidth={2} aria-label="From a recurring rule" />
            <AccountBadge name={p.account_name ?? ""} account={accountsById.get(p.account_id)} />
            {p.counter_account_name && (
              <>
                <span className="text-on-surface-variant">→</span>
                <AccountBadge
                  name={p.counter_account_name}
                  account={p.counter_account_id ? accountsById.get(p.counter_account_id) : undefined}
                />
              </>
            )}
            <span className="text-xs text-on-surface-variant">{formatDate(p.date)}</span>
          </div>
          <div className="mt-1 truncate text-xs text-on-surface-variant">
            <span className="font-medium text-on-surface">{p.name}</span>
            {categoryName && ` · ${categoryName}`}
          </div>
        </div>
        <span className={`shrink-0 tabular-nums text-sm font-medium opacity-70 ${p.type === "transfer" ? "text-on-surface-variant" : pnlColorClass(signed)}`}>
          {p.type === "transfer" ? formatEur(p.amount) : formatEur(signed)}
        </span>
      </Link>
    </li>
  );
}

export default function GriprTransactions() {
  const queryClient = useQueryClient();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const [page, setPage] = useState(0);
  const [typeFilter, setTypeFilter] = useState<GriprTransactionType | "">("");
  const [accountFilter, setAccountFilter] = useState<string>("");
  // Opens pre-filtered when linked to with ?category=uncategorized (the bank card's "categorise").
  const [searchParams] = useSearchParams();
  const [categoryFilter, setCategoryFilter] = useState<string>(() =>
    searchParams.get("category") === UNCATEGORIZED ? UNCATEGORIZED : "",
  );
  const [minAmountInput, setMinAmountInput] = useState("");
  const [maxAmountInput, setMaxAmountInput] = useState("");
  const [minAmount, setMinAmount] = useState<string | undefined>(undefined);
  const [maxAmount, setMaxAmount] = useState<string | undefined>(undefined);
  const [editing, setEditing] = useState<GriprTransaction | undefined | null>(null); // null = closed
  // Set = the open form is a new refund for this expense ("Got money back").
  const [refundOf, setRefundOf] = useState<GriprTransaction | undefined>(undefined);
  const closeForm = () => {
    setEditing(null);
    setRefundOf(undefined);
  };
  const openRefund = (expense: GriprTransaction) => {
    setRefundOf(expense);
    setEditing(undefined);
  };

  const accountsQuery = useQuery({ queryKey: ["gripr-accounts", false], queryFn: () => griprApi.listAccounts() });
  const categoriesQuery = useQuery({ queryKey: ["gripr-categories"], queryFn: () => griprApi.listCategories() });
  const today = todayIsoDate();
  // Future-dated rows (pre-booked recurring occurrences, or anything entered ahead of time) sort
  // to the top of a date-desc list and bury what actually happened recently -- they live in the
  // "Upcoming" card below instead, fetched separately so this list only ever shows the past.
  const transactionsQuery = useQuery({
    queryKey: ["gripr-transactions", page, typeFilter, accountFilter, categoryFilter, minAmount, maxAmount],
    queryFn: () =>
      griprApi.listTransactions({
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        type: typeFilter || undefined,
        accountId: accountFilter ? Number(accountFilter) : undefined,
        categoryId: categoryFilter && categoryFilter !== UNCATEGORIZED ? Number(categoryFilter) : undefined,
        uncategorized: categoryFilter === UNCATEGORIZED,
        amountMin: minAmount,
        amountMax: maxAmount,
        dateTo: today,
      }),
  });
  // What recurring rules will still book through the end of the current period, beyond the
  // couple of days ahead they're actually pre-booked (see gripr_recurring_service). Keyed under
  // "gripr-transactions" so every mutation here that refreshes the list refreshes this too.
  const plannedQuery = useQuery({
    queryKey: ["gripr-transactions", "planned-recurring"],
    queryFn: () => griprApi.upcomingRecurring(),
  });
  const upcomingQuery = useQuery({
    queryKey: ["gripr-transactions", "upcoming"],
    queryFn: () =>
      griprApi.listTransactions({
        dateFrom: addDaysIso(today, 1),
        sortBy: "date",
        sortDir: "asc",
        limit: 100,
      }),
  });

  function commitMinAmount() {
    setMinAmount(decimalInputToApi(minAmountInput) ?? undefined);
    setPage(0);
  }
  function commitMaxAmount() {
    setMaxAmount(decimalInputToApi(maxAmountInput) ?? undefined);
    setPage(0);
  }

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["gripr-transactions"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-receivables"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-accounts"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-budgets"] });
  };

  const createMutation = useMutation({
    mutationFn: (input: GriprTransactionInput) => griprApi.createTransaction(input),
    onSuccess: () => {
      invalidateAll();
      closeForm();
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: GriprTransactionInput }) => griprApi.updateTransaction(id, input),
    onSuccess: () => {
      invalidateAll();
      closeForm();
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => griprApi.deleteTransaction(id),
    onSuccess: invalidateAll,
  });

  async function handleDelete(t: GriprTransaction) {
    const ok = await confirm({
      title: "Delete transaction?",
      description: `This ${t.type} transaction from ${formatDate(t.date)} will be permanently removed.`,
    });
    if (ok) deleteMutation.mutate(t.id);
  }

  const total = transactionsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const categoryColors = useMemo(() => buildCategoryColorMap(categoriesQuery.data ?? []), [categoriesQuery.data]);
  const accountsById = useMemo(
    () => new Map((accountsQuery.data ?? []).map((a) => [a.id, a])),
    [accountsQuery.data],
  );
  const categoriesById = useMemo(
    () => new Map((categoriesQuery.data ?? []).map((c) => [c.id, c])),
    [categoriesQuery.data],
  );
  // Top-level categories only — picking one matches everything filed under it too (the
  // backend rolls subcategories up), so there's no need to list them separately.
  const categoryOptions = useMemo(
    () => (categoriesQuery.data ?? []).filter((c) => c.parent_id === null).sort((a, b) => a.name.localeCompare(b.name)),
    [categoriesQuery.data],
  );

  const upcoming = upcomingQuery.data?.items ?? [];
  const planned = plannedQuery.data?.items ?? [];
  // Booked future-dated rows and planned occurrences in one date-ordered list; a booked row
  // sorts ahead of a planned one on the same day.
  const upcomingEntries: ({ kind: "booked"; t: GriprTransaction } | { kind: "planned"; p: GriprPlannedOccurrence })[] = [
    ...upcoming.map((t) => ({ kind: "booked" as const, t })),
    ...planned.map((p) => ({ kind: "planned" as const, p })),
  ].sort((a, b) => {
    const da = a.kind === "booked" ? a.t.date : a.p.date;
    const db = b.kind === "booked" ? b.t.date : b.p.date;
    return da < db ? -1 : da > db ? 1 : a.kind === b.kind ? 0 : a.kind === "booked" ? -1 : 1;
  });

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow>
        <a href="/api/gripr/transactions/export.csv" download className={`${secondaryButtonClass} no-underline`} aria-label="Export CSV">
          <span className="sm:hidden">CSV</span>
          <span className="hidden sm:inline">Export CSV</span>
        </a>
        {/* On mobile this is the FAB's job instead (MobileFab, below) -- a thumb-reachable
            button beats one pinned to the top of a tall page. */}
        <GriprButton onClick={() => setEditing(undefined)} className="hidden sm:inline-flex">
          Add transaction
        </GriprButton>
      </ModuleTopRow>
      <PageTitle>Transactions</PageTitle>

      <CollapsibleCard
        storageKey="gripr-upcoming-recurring"
        defaultOpen={false}
        title="Upcoming"
        cardClassName="rounded-2xl border border-outline-variant bg-surface"
        meta={
          <span className="text-xs text-on-surface-variant">
            {upcomingQuery.data && plannedQuery.data
              ? `${upcomingEntries.length} · until ${formatDate(plannedQuery.data.until)}`
              : ""}
          </span>
        }
      >
        {upcomingQuery.isLoading || plannedQuery.isLoading ? (
          <div className="py-2 text-sm text-on-surface-variant">Loading…</div>
        ) : upcomingQuery.isError || plannedQuery.isError ? (
          <div className="py-2 text-sm text-error">Couldn't load what's coming up.</div>
        ) : upcomingEntries.length === 0 ? (
          <div className="py-2 text-sm text-on-surface-variant">Nothing dated ahead of today, and no recurring rule due before the period ends.</div>
        ) : (
          <ul className="divide-y divide-outline-variant">
            {upcomingEntries.map((entry) => {
              if (entry.kind === "planned") {
                return (
                  <PlannedRow
                    key={`planned-${entry.p.recurring_id}-${entry.p.date}`}
                    occurrence={entry.p}
                    categoryName={(() => {
                      const { top, sub } = resolveCategory(entry.p.category_id, categoriesById);
                      return sub ? sub.name : top?.name;
                    })()}
                    accountsById={accountsById}
                  />
                );
              }
              const t = entry.t;
              const { top, sub } = resolveCategory(t.category_id, categoriesById);
              const badges = (
                <>
                  <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${GRIPR_TYPE_BADGE[t.type]}`}
                          title={refundTitle(t)}
                        >
                    {t.type}
                  </span>
                  {t.is_recurring && (
                    <span title="From a recurring rule" aria-label="From a recurring rule">
                      <Repeat className="h-3.5 w-3.5 shrink-0 text-on-surface-variant" strokeWidth={2} />
                    </span>
                  )}
                  <AccountBadge name={t.account_name ?? ""} account={accountsById.get(t.account_id)} />
                  {t.counter_account_name && (
                    <>
                      <span className="text-on-surface-variant">→</span>
                      <AccountBadge
                        name={t.counter_account_name}
                        account={t.counter_account_id ? accountsById.get(t.counter_account_id) : undefined}
                      />
                    </>
                  )}
                </>
              );
              const amount = (
                <span
                  className={`tabular-nums text-sm font-medium ${t.type === "transfer" ? "text-on-surface-variant" : pnlColorClass(griprSignedAmount(t))}`}
                >
                  {t.type === "transfer" ? formatEur(t.amount) : formatEur(griprSignedAmount(t))}
                </span>
              );
              const deleteButton = (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(t);
                  }}
                  className="text-error hover:opacity-80"
                  title="Delete"
                  aria-label="Delete"
                >
                  <Trash2 className="h-4 w-4" strokeWidth={2} />
                </button>
              );
              return (
                <li key={t.id} onClick={() => setEditing(t)} className="cursor-pointer py-2 text-sm hover:bg-on-surface/5">
                  {/* Tablet and up: one row, like the main list's desktop table. Below that, the
                      same six-ish fields wrap into two lines instead of being squeezed sideways. */}
                  <div className="hidden items-center justify-between gap-3 sm:flex">
                    <div className="flex min-w-0 items-center gap-2">
                      {badges}
                      {(top || sub) && (
                        <span className="shrink-0 truncate text-on-surface-variant">{sub ? sub.name : top?.name}</span>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="text-on-surface-variant">{formatDate(t.date)}</span>
                      {amount}
                      {deleteButton}
                    </div>
                  </div>
                  <div className="flex items-start justify-between gap-3 sm:hidden">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {badges}
                        <span className="text-xs text-on-surface-variant">{formatDate(t.date)}</span>
                      </div>
                      {(top || sub) && (
                        <div className="mt-1 truncate text-xs text-on-surface-variant">{sub ? sub.name : top?.name}</div>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1.5">
                      {amount}
                      {deleteButton}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CollapsibleCard>

      <div className="flex items-center gap-2 overflow-x-auto pb-1 [scrollbar-width:none]">
        <select
          aria-label="Type"
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value as GriprTransactionType | "");
            setPage(0);
          }}
          className={chipClass}
        >
          <option value="">All types</option>
          {GRIPR_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          aria-label="Account"
          value={accountFilter}
          onChange={(e) => {
            setAccountFilter(e.target.value);
            setPage(0);
          }}
          className={chipClass}
        >
          <option value="">All accounts</option>
          {(accountsQuery.data ?? []).map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Category"
          value={categoryFilter}
          onChange={(e) => {
            setCategoryFilter(e.target.value);
            setPage(0);
          }}
          className={chipClass}
        >
          <option value="">All categories</option>
          <option value={UNCATEGORIZED}>Uncategorized</option>
          {categoryOptions.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <input
          aria-label="Min amount"
          inputMode="decimal"
          placeholder="Min €"
          value={minAmountInput}
          onChange={(e) => setMinAmountInput(e.target.value)}
          onBlur={commitMinAmount}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
          className={`w-20 ${chipClass}`}
        />
        <input
          aria-label="Max amount"
          inputMode="decimal"
          placeholder="Max €"
          value={maxAmountInput}
          onChange={(e) => setMaxAmountInput(e.target.value)}
          onBlur={commitMaxAmount}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
          className={`w-20 ${chipClass}`}
        />
      </div>

      <div className="rounded-2xl border border-outline-variant bg-surface">
        {/* Tablet and up: a table. Below that, no column arrangement fits seven columns
            without side-to-side scrolling, so every field stacks into a card instead —
            nothing hidden, just reflowed. */}
        <div className="hidden overflow-x-auto sm:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-outline-variant text-left text-xs uppercase tracking-wide text-on-surface-variant">
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="px-4 py-2 font-medium">Account</th>
                <th className="px-4 py-2 font-medium">Category</th>
                <th className="px-4 py-2 font-medium">Subcategory</th>
                <th className="px-4 py-2 text-right font-medium">Amount</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {transactionsQuery.isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-on-surface-variant">
                    Loading…
                  </td>
                </tr>
              ) : transactionsQuery.data?.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-on-surface-variant">
                    No transactions
                  </td>
                </tr>
              ) : (
                transactionsQuery.data?.items.map((t) => {
                  const { top, sub } = resolveCategory(t.category_id, categoriesById);
                  return (
                    <tr
                      key={t.id}
                      onClick={() => setEditing(t)}
                      className="cursor-pointer border-b border-outline-variant last:border-0 hover:bg-on-surface/5"
                    >
                      <td className="px-4 py-2 whitespace-nowrap text-on-surface-variant">{formatDate(t.date)}</td>
                      <td className="px-4 py-2">
                        <span className="flex items-center gap-1.5">
                          <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${GRIPR_TYPE_BADGE[t.type]}`}
                          title={refundTitle(t)}
                        >
                            {t.type}
                          </span>
                          {t.is_recurring && (
                            <span title="From a recurring rule" aria-label="From a recurring rule">
                              <Repeat className="h-3.5 w-3.5 shrink-0 text-on-surface-variant" strokeWidth={2} />
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <span className="flex flex-wrap items-center gap-1">
                          <AccountBadge name={t.account_name ?? ""} account={accountsById.get(t.account_id)} />
                          {t.counter_account_name && (
                            <>
                              <span className="text-on-surface-variant">→</span>
                              <AccountBadge
                                name={t.counter_account_name}
                                account={t.counter_account_id ? accountsById.get(t.counter_account_id) : undefined}
                              />
                            </>
                          )}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-on-surface-variant">
                        {top ? (
                          <span className="flex items-center gap-1.5">
                            <span
                              className="h-2 w-2 shrink-0 rounded-full"
                              style={{ backgroundColor: categoryColors.get(top.id) ?? "#94a3b8" }}
                            />
                            {top.name}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-4 py-2 text-on-surface-variant">{sub ? sub.name : "—"}</td>
                      <td className="px-4 py-2 text-right">
                        <AmountWithRefunds t={t} />
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right">
                        {t.type === "expense" && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              openRefund(t);
                            }}
                            className="mr-3 text-on-surface-variant hover:text-on-surface"
                            title="Got money back"
                            aria-label="Got money back"
                          >
                            <Undo2 className="h-4 w-4" strokeWidth={2} />
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditing(t);
                          }}
                          className="text-on-surface-variant hover:text-on-surface"
                          title="Edit"
                          aria-label="Edit"
                        >
                          <Pencil className="h-4 w-4" strokeWidth={2} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(t);
                          }}
                          className="ml-3 text-error hover:opacity-80"
                          title="Delete"
                          aria-label="Delete"
                        >
                          <Trash2 className="h-4 w-4" strokeWidth={2} />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="divide-y divide-outline-variant sm:hidden">
          {transactionsQuery.isLoading ? (
            <div className="px-4 py-6 text-center text-on-surface-variant">Loading…</div>
          ) : transactionsQuery.data?.items.length === 0 ? (
            <div className="px-4 py-6 text-center text-on-surface-variant">No transactions</div>
          ) : (
            transactionsQuery.data?.items.map((t) => {
              const { top, sub } = resolveCategory(t.category_id, categoriesById);
              const Icon = top ? categoryIcon(top.name) : ArrowLeftRight;
              const avatarColor = top ? categoryColors.get(top.id) ?? "#94a3b8" : "#94a3b8";
              return (
                <div
                  key={t.id}
                  onClick={() => setEditing(t)}
                  className="flex cursor-pointer items-start gap-3 px-4 py-3 hover:bg-on-surface/5"
                >
                  <span
                    className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                    style={{ backgroundColor: avatarColor }}
                  >
                    <Icon className="h-5 w-5 text-white" strokeWidth={2} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${GRIPR_TYPE_BADGE[t.type]}`}
                          title={refundTitle(t)}
                        >
                        {t.type}
                      </span>
                      {t.is_recurring && (
                        <span title="From a recurring rule" aria-label="From a recurring rule">
                          <Repeat className="h-3.5 w-3.5 shrink-0 text-on-surface-variant" strokeWidth={2} />
                        </span>
                      )}
                      <AccountBadge name={t.account_name ?? ""} account={accountsById.get(t.account_id)} />
                      {t.counter_account_name && (
                        <>
                          <span className="text-on-surface-variant">→</span>
                          <AccountBadge
                            name={t.counter_account_name}
                            account={t.counter_account_id ? accountsById.get(t.counter_account_id) : undefined}
                          />
                        </>
                      )}
                      <span className="text-xs text-on-surface-variant">{formatDate(t.date)}</span>
                    </div>
                    {(top || sub) && (
                      <div className="mt-1 truncate text-xs text-on-surface-variant">
                        {top?.name}
                        {sub && <span>{top ? ` › ${sub.name}` : sub.name}</span>}
                      </div>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1.5">
                    <AmountWithRefunds t={t} />
                    <div className="flex items-center gap-3">
                      {t.type === "expense" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            openRefund(t);
                          }}
                          className="text-on-surface-variant hover:text-on-surface"
                          title="Got money back"
                          aria-label="Got money back"
                        >
                          <Undo2 className="h-4 w-4" strokeWidth={2} />
                        </button>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditing(t);
                        }}
                        className="text-on-surface-variant hover:text-on-surface"
                        title="Edit"
                        aria-label="Edit"
                      >
                        <Pencil className="h-4 w-4" strokeWidth={2} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(t);
                        }}
                        className="text-error hover:opacity-80"
                        title="Delete"
                        aria-label="Delete"
                      >
                        <Trash2 className="h-4 w-4" strokeWidth={2} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="flex items-center justify-between border-t border-outline-variant px-4 py-3 text-sm text-on-surface-variant">
          <span>
            {total} transactions — page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="rounded-full border border-outline px-3 py-1 disabled:opacity-40"
            >
              Prev
            </button>
            <button
              disabled={page + 1 >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-full border border-outline px-3 py-1 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <MobileFab label="Add" onClick={() => setEditing(undefined)} />

      {editing !== null && (
        <GriprTransactionForm
          // Remount when switching from editing an expense to its new refund, so the form
          // starts from the refund prefill instead of keeping the expense's state.
          key={refundOf ? `refund-${refundOf.id}` : (editing?.id ?? "new")}
          accounts={accountsQuery.data ?? []}
          categories={categoriesQuery.data ?? []}
          initial={editing}
          refundOf={refundOf}
          onAddRefund={openRefund}
          isSubmitting={createMutation.isPending || updateMutation.isPending}
          onCancel={closeForm}
          onSubmit={(input) => {
            if (editing) {
              updateMutation.mutate({ id: editing.id, input });
            } else {
              createMutation.mutate(input);
            }
          }}
        />
      )}

      {confirmDialog}
    </div>
  );
}
