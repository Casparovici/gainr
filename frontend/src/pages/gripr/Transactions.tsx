import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, Repeat } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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
import AttachmentBadge from "../../components/AttachmentBadge";
import GriprTransactionForm from "../../components/gripr/GriprTransactionForm";
import GriprButton from "../../components/gripr/GriprButton";
import TransactionBulkBar from "../../components/gripr/TransactionBulkBar";
import MobileFab from "../../components/MobileFab";
import { ModuleTopRow, PageTitle, secondaryButtonClass } from "../../components/ui/kit";
import CollapsibleCard from "../../components/CollapsibleCard";
import { useConfirmDialog } from "../../components/gripr/useConfirmDialog";
import { warnFailedAttachments } from "../../utils/attachments";
import { buildCategoryColorMap } from "../../utils/categoryColor";
import { categoryIcon } from "../../utils/categoryIcons";
import { addDaysIso, decimalInputToApi, formatDate, formatEur, pnlColorClass, todayIsoDate } from "../../utils/format";
import { GRIPR_TYPE_BADGE, GRIPR_TYPE_OPTIONS, griprSignedAmount, griprTypeLabel } from "../../utils/griprTransactionType";
import { QueryError } from "../../components/ui/QueryError";
import { msg, t as tr, tp } from "../../i18n";

const LOAD_ERROR = msg("Couldn't load transactions.");

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
        <span className="whitespace-nowrap text-xs text-on-surface-variant" title={tr("Net cost {amount}", { amount: formatEur(parseFloat(t.amount) - refunded) })}>
          {formatEur(refunded)}{" "}{tr("back")}</span>
      )}
      {parseFloat(t.outstanding) > 0 && (
        <span className="whitespace-nowrap text-xs text-on-surface-variant" title={t.expected_from ? tr("Owed by {name}", { name: t.expected_from }) : undefined}>
          {formatEur(t.outstanding)}{" "}{tr("to come back")}</span>
      )}
    </span>
  );
}

/** For a linked refund's badge: what it came back for. */
function refundTitle(t: GriprTransaction): string | undefined {
  if (!t.refund_of) return undefined;
  const what = t.refund_of.notes || tr("expense");
  return tr("Money back for {what} ({amount}, {date})", { what, amount: formatEur(t.refund_of.amount), date: formatDate(t.refund_of.date) });
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
            <span className="rounded-full border border-dashed border-outline px-2 py-0.5 text-xs font-medium text-on-surface-variant">{tr("planned")}</span>
            <Repeat className="h-3.5 w-3.5 shrink-0 text-on-surface-variant" strokeWidth={2} aria-label={tr("From a recurring rule")} />
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
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  // Typing settles for a moment before it searches, so each keystroke isn't a request.
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);
  // Select mode: a row tap ticks it instead of opening it, and the bulk bar acts on the ticked ones.
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  // A short line saying what the last bulk action or "file similar" did.
  const [notice, setNotice] = useState<string | null>(null);
  // Offered after categorising a bank-synced transaction: file the others from that counterparty too.
  const [similarPrompt, setSimilarPrompt] = useState<{ id: number; count: number; counterparty: string; categoryName: string } | null>(null);
  // null = closed. Vandaag's "+ Uitgave" links here with ?add=1, which opens the form for a new one.
  const [editing, setEditing] = useState<GriprTransaction | undefined | null>(() => (searchParams.get("add") ? undefined : null));
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
    queryKey: ["gripr-transactions", page, typeFilter, accountFilter, categoryFilter, minAmount, maxAmount, search],
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
        search: search || undefined,
      }),
  });
  // A selection only ever spans what's on screen: changing the page or a filter starts afresh.
  useEffect(() => setSelected(new Set()), [page, typeFilter, accountFilter, categoryFilter, minAmount, maxAmount, search]);
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
    mutationFn: ({ input, files }: { input: GriprTransactionInput; files: File[] }) =>
      griprApi.createTransactionWithAttachments(input, files),
    onSuccess: ({ failed }) => {
      invalidateAll();
      closeForm();
      warnFailedAttachments(failed);
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: GriprTransactionInput; previousCategoryId: number | null }) =>
      griprApi.updateTransaction(id, input),
    onSuccess: async (_updated, { id, input, previousCategoryId }) => {
      invalidateAll();
      closeForm();
      if (input.category_id === null || input.category_id === previousCategoryId) return;
      const similar = await griprApi.similarUncategorised(id).catch(() => null);
      if (similar && similar.count > 0) {
        const category = categoriesQuery.data?.find((c) => c.id === input.category_id);
        setSimilarPrompt({
          id,
          count: similar.count,
          counterparty: similar.counterparty ?? tr("this counterparty"),
          categoryName: category?.name ?? tr("this category"),
        });
      }
    },
  });
  const similarMutation = useMutation({
    mutationFn: (id: number) => griprApi.applyCategoryToSimilar(id),
    onSuccess: ({ updated }) => {
      invalidateAll();
      setSimilarPrompt(null);
      setNotice(tp(updated, "Filed {n} more transaction.", "Filed {n} more transactions."));
    },
  });
  const bulkMutation = useMutation({
    mutationFn: (args: { action: "set_category" | "set_account" | "delete"; categoryId?: number; accountId?: number }) =>
      griprApi.bulkTransactions([...selected], args.action, { categoryId: args.categoryId, accountId: args.accountId }),
    onSuccess: ({ updated, skipped }, { action }) => {
      invalidateAll();
      setSelected(new Set());
      const done =
        action === "delete"
          ? tr("Deleted {n}.", { n: updated })
          : action === "set_account"
            ? tr("Moved {n}.", { n: updated })
            : tr("Filed {n}.", { n: updated });
      const why =
        action === "set_category"
          ? tr("Skipped {n} (a transfer takes no category, and an income category only fits income).", { n: skipped })
          : tr("Skipped {n} (a transfer can't move onto its own other side).", { n: skipped });
      setNotice(skipped ? `${done} ${why}` : done);
    },
  });

  function toggleSelected(id: number) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  // A row tap opens the transaction, or in select mode ticks it.
  const onRowClick = (t: GriprTransaction) => (selectMode ? toggleSelected(t.id) : setEditing(t));

  async function handleBulkDelete() {
    const ok = await confirm({
      title: tp(selected.size, "Delete {n} transaction?", "Delete {n} transactions?"),
      description: tr("They are permanently removed. Refunds pointing at a deleted expense stay, without the link."),
    });
    if (ok) bulkMutation.mutate({ action: "delete" });
  }
  const deleteMutation = useMutation({
    mutationFn: (id: number) => griprApi.deleteTransaction(id),
    onSuccess: invalidateAll,
  });

  async function handleDelete(t: GriprTransaction) {
    const ok = await confirm({
      title: tr("Delete transaction?"),
      description: tr("This {type} transaction from {date} will be permanently removed.", {
        type: griprTypeLabel(t.type).toLowerCase(),
        date: formatDate(t.date),
      }),
    });
    if (ok) {
      deleteMutation.mutate(t.id);
      closeForm();
    }
  }

  const total = transactionsQuery.data?.total ?? 0;
  const pageIds = (transactionsQuery.data?.items ?? []).map((t) => t.id);
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
        <a href="/api/gripr/transactions/export.csv" download className={`${secondaryButtonClass} no-underline`} aria-label={tr("Export CSV")}>
          <span className="sm:hidden">CSV</span>
          <span className="hidden sm:inline">{tr("Export CSV")}</span>
        </a>
        {/* On mobile this is the FAB's job instead (MobileFab, below) -- a thumb-reachable
            button beats one pinned to the top of a tall page. */}
        <GriprButton onClick={() => setEditing(undefined)} className="hidden sm:inline-flex">{tr("Add transaction")}</GriprButton>
      </ModuleTopRow>
      <PageTitle>{tr("Transactions")}</PageTitle>

      <CollapsibleCard
        storageKey="gripr-upcoming-recurring"
        defaultOpen={false}
        title={tr("Upcoming")}
        cardClassName="rounded-2xl border border-outline-variant bg-surface"
        meta={
          <span className="text-xs text-on-surface-variant">
            {upcomingQuery.data && plannedQuery.data
              ? tr("{count} · until {date}", { count: upcomingEntries.length, date: formatDate(plannedQuery.data.until) })
              : ""}
          </span>
        }
      >
        {upcomingQuery.isLoading || plannedQuery.isLoading ? (
          <div className="py-2 text-sm text-on-surface-variant">{tr("Loading…")}</div>
        ) : upcomingQuery.isError || plannedQuery.isError ? (
          <div className="py-2 text-sm text-error">{tr("Couldn't load what's coming up.")}</div>
        ) : upcomingEntries.length === 0 ? (
          <div className="py-2 text-sm text-on-surface-variant">{tr("Nothing dated ahead of today, and no recurring rule due before the period ends.")}</div>
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
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${GRIPR_TYPE_BADGE[t.type]}`}
                          title={refundTitle(t)}
                        >
                    {griprTypeLabel(t.type)}
                  </span>
                  <AttachmentBadge variant="gripr" count={t.attachment_count} />
                  {t.is_recurring && (
                    <span title={tr("From a recurring rule")} aria-label={tr("From a recurring rule")}>
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
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CollapsibleCard>

      <div className="flex items-center gap-2 overflow-x-auto pb-1 [scrollbar-width:none]">
        <input
          type="search"
          aria-label={tr("Search transactions")}
          placeholder={tr("Search…")}
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className={`w-40 ${chipClass}`}
        />
        <button
          type="button"
          aria-pressed={selectMode}
          onClick={() => {
            setSelectMode((on) => !on);
            setSelected(new Set());
          }}
          className={`${chipClass} ${selectMode ? "border-primary text-primary" : ""}`}
        >
          {selectMode ? tr("Done") : tr("Select")}
        </button>
        <select
          aria-label={tr("Type")}
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value as GriprTransactionType | "");
            setPage(0);
          }}
          className={chipClass}
        >
          <option value="">{tr("All types")}</option>
          {GRIPR_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {tr(o.label)}
            </option>
          ))}
        </select>
        <select
          aria-label={tr("Account")}
          value={accountFilter}
          onChange={(e) => {
            setAccountFilter(e.target.value);
            setPage(0);
          }}
          className={chipClass}
        >
          <option value="">{tr("All accounts")}</option>
          {(accountsQuery.data ?? []).map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <select
          aria-label={tr("Category")}
          value={categoryFilter}
          onChange={(e) => {
            setCategoryFilter(e.target.value);
            setPage(0);
          }}
          className={chipClass}
        >
          <option value="">{tr("All categories")}</option>
          <option value={UNCATEGORIZED}>{tr("Uncategorized")}</option>
          {categoryOptions.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <input
          aria-label={tr("Min amount")}
          inputMode="decimal"
          placeholder={tr("Min €")}
          value={minAmountInput}
          onChange={(e) => setMinAmountInput(e.target.value)}
          onBlur={commitMinAmount}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
          className={`w-20 ${chipClass}`}
        />
        <input
          aria-label={tr("Max amount")}
          inputMode="decimal"
          placeholder={tr("Max €")}
          value={maxAmountInput}
          onChange={(e) => setMaxAmountInput(e.target.value)}
          onBlur={commitMaxAmount}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
          className={`w-20 ${chipClass}`}
        />

      </div>

      {similarPrompt && (
        <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-outline-variant bg-surface-container-high px-4 py-2.5 text-sm">
          <span className="min-w-0 flex-1 text-on-surface">{tp(similarPrompt.count, "Also file {n} other uncategorised transaction", "Also file {n} other uncategorised transactions")}{" "}{tr("from")}{" "}
            <span className="font-medium">{similarPrompt.counterparty}</span>{" "}{tr("under")}{" "}
            <span className="font-medium">{similarPrompt.categoryName}</span>?
          </span>
          <button
            type="button"
            disabled={similarMutation.isPending}
            onClick={() => similarMutation.mutate(similarPrompt.id)}
            className="rounded-full border border-outline px-3 py-1 font-medium text-on-surface hover:bg-on-surface/10 disabled:opacity-40"
          >{tr("File them")}</button>
          <button type="button" onClick={() => setSimilarPrompt(null)} className="text-on-surface-variant hover:text-on-surface">{tr("Not now")}</button>
        </div>
      )}
      {notice && (
        <div className="flex items-center justify-between gap-2 rounded-2xl border border-outline-variant bg-surface px-4 py-2 text-sm text-on-surface">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(null)} className="text-on-surface-variant hover:text-on-surface" aria-label={tr("Dismiss")}>
            ✕
          </button>
        </div>
      )}

      <div className="rounded-2xl border border-outline-variant bg-surface">
        {/* Tablet and up: a table. Below that, no column arrangement fits seven columns
            without side-to-side scrolling, so every field stacks into a card instead —
            nothing hidden, just reflowed. */}
        <div className="hidden overflow-x-auto sm:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-outline-variant text-left text-xs uppercase tracking-wide text-on-surface-variant">
                {selectMode && (
                  <th className="w-8 py-2 pl-4">
                    <input
                      type="checkbox"
                      aria-label={tr("Select all on this page")}
                      checked={pageIds.length > 0 && pageIds.every((id) => selected.has(id))}
                      onChange={(e) => setSelected(e.target.checked ? new Set(pageIds) : new Set())}
                    />
                  </th>
                )}
                <th className="px-4 py-2 font-medium">{tr("Date")}</th>
                <th className="px-4 py-2 font-medium">{tr("Type")}</th>
                <th className="px-4 py-2 font-medium">{tr("Account")}</th>
                <th className="px-4 py-2 font-medium">{tr("Category")}</th>
                <th className="px-4 py-2 font-medium">{tr("Subcategory")}</th>
                <th className="px-4 py-2 text-right font-medium">{tr("Amount")}</th>
              </tr>
            </thead>
            <tbody>
              {transactionsQuery.isLoading ? (
                <tr>
                  <td colSpan={selectMode ? 7 : 6} className="px-4 py-6 text-center text-on-surface-variant">{tr("Loading…")}</td>
                </tr>
              ) : transactionsQuery.isError ? (
                <tr>
                  <td colSpan={selectMode ? 7 : 6} className="px-4 py-6 text-center">
                    <QueryError message={tr(LOAD_ERROR)} onRetry={() => transactionsQuery.refetch()} />
                  </td>
                </tr>
              ) : transactionsQuery.data?.items.length === 0 ? (
                <tr>
                  <td colSpan={selectMode ? 7 : 6} className="px-4 py-6 text-center text-on-surface-variant">
                    {search ? tr("Nothing matches \"{search}\"", { search }) : tr("No transactions")}
                  </td>
                </tr>
              ) : (
                transactionsQuery.data?.items.map((t) => {
                  const { top, sub } = resolveCategory(t.category_id, categoriesById);
                  return (
                    <tr
                      key={t.id}
                      onClick={() => onRowClick(t)}
                      className={`cursor-pointer border-b border-outline-variant last:border-0 hover:bg-on-surface/5 ${selected.has(t.id) ? "bg-primary/10" : ""}`}
                    >
                      {selectMode && (
                        <td className="py-2 pl-4" onClick={(e) => e.stopPropagation()}>
                          <input type="checkbox" aria-label={tr("Select")} checked={selected.has(t.id)} onChange={() => toggleSelected(t.id)} />
                        </td>
                      )}
                      <td className="px-4 py-2 whitespace-nowrap text-on-surface-variant">{formatDate(t.date)}</td>
                      <td className="px-4 py-2">
                        <span className="flex items-center gap-1.5">
                          <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${GRIPR_TYPE_BADGE[t.type]}`}
                          title={refundTitle(t)}
                        >
                            {griprTypeLabel(t.type)}
                          </span>
                          <AttachmentBadge variant="gripr" count={t.attachment_count} />
                          {t.is_recurring && (
                            <span title={tr("From a recurring rule")} aria-label={tr("From a recurring rule")}>
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
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="divide-y divide-outline-variant sm:hidden">
          {transactionsQuery.isLoading ? (
            <div className="px-4 py-6 text-center text-on-surface-variant">{tr("Loading…")}</div>
          ) : transactionsQuery.isError ? (
            <QueryError className="px-4 py-6 text-center" message={tr(LOAD_ERROR)} onRetry={() => transactionsQuery.refetch()} />
          ) : transactionsQuery.data?.items.length === 0 ? (
            <div className="px-4 py-6 text-center text-on-surface-variant">{search ? tr("Nothing matches \"{search}\"", { search }) : tr("No transactions")}</div>
          ) : (
            transactionsQuery.data?.items.map((t) => {
              const { top, sub } = resolveCategory(t.category_id, categoriesById);
              const Icon = top ? categoryIcon(top.name) : ArrowLeftRight;
              const avatarColor = top ? categoryColors.get(top.id) ?? "#94a3b8" : "#94a3b8";
              return (
                <div
                  key={t.id}
                  onClick={() => onRowClick(t)}
                  className={`flex cursor-pointer items-start gap-3 px-4 py-3 hover:bg-on-surface/5 ${selected.has(t.id) ? "bg-primary/10" : ""}`}
                >
                  {selectMode && (
                    <input
                      type="checkbox"
                      aria-label={tr("Select")}
                      checked={selected.has(t.id)}
                      onClick={(e) => e.stopPropagation()}
                      onChange={() => toggleSelected(t.id)}
                      className="mt-3 h-4 w-4 shrink-0"
                    />
                  )}
                  <span
                    className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                    style={{ backgroundColor: avatarColor }}
                  >
                    <Icon className="h-5 w-5 text-white" strokeWidth={2} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${GRIPR_TYPE_BADGE[t.type]}`}
                          title={refundTitle(t)}
                        >
                        {griprTypeLabel(t.type)}
                      </span>
                      <AttachmentBadge variant="gripr" count={t.attachment_count} />
                      {t.is_recurring && (
                        <span title={tr("From a recurring rule")} aria-label={tr("From a recurring rule")}>
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
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="flex items-center justify-between border-t border-outline-variant px-4 py-3 text-sm text-on-surface-variant">
          <span>
            {tr("{n} transactions — page {page} of {totalPages}", { n: total, page: page + 1, totalPages })}</span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="rounded-full border border-outline px-3 py-1 disabled:opacity-40"
            >{tr("Prev")}</button>
            <button
              disabled={page + 1 >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-full border border-outline px-3 py-1 disabled:opacity-40"
            >{tr("Next")}</button>
          </div>
        </div>
      </div>

      {selectMode && selected.size > 0 && (
        <TransactionBulkBar
          count={selected.size}
          categories={categoriesQuery.data ?? []}
          accounts={accountsQuery.data ?? []}
          busy={bulkMutation.isPending}
          onSetCategory={(categoryId) => bulkMutation.mutate({ action: "set_category", categoryId })}
          onSetAccount={(accountId) => bulkMutation.mutate({ action: "set_account", accountId })}
          onDelete={handleBulkDelete}
          onClear={() => setSelected(new Set())}
        />
      )}

      {!selectMode && <MobileFab label={tr("Add")} onClick={() => setEditing(undefined)} />}

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
          onDelete={handleDelete}
          isSubmitting={createMutation.isPending || updateMutation.isPending}
          onCancel={closeForm}
          onSubmit={(input, files) => {
            if (editing) {
              updateMutation.mutate({ id: editing.id, input, previousCategoryId: editing.category_id });
            } else {
              createMutation.mutate({ input, files });
            }
          }}
        />
      )}

      {confirmDialog}
    </div>
  );
}
