import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { griprApi } from "../../api/griprClient";
import type { GriprCategory, GriprRecurrenceFrequency, GriprRecurring, GriprRecurringInput, GriprTransactionType } from "../../api/griprTypes";
import AccountBadge from "../../components/gripr/AccountBadge";
import GriprButton from "../../components/gripr/GriprButton";
import { ModuleTopRow, PageTitle } from "../../components/ui/kit";
import { QueryError } from "../../components/ui/QueryError";
import RecurringForm from "../../components/gripr/RecurringForm";
import { useConfirmDialog } from "../../components/gripr/useConfirmDialog";
import MobileFab from "../../components/MobileFab";
import { buildCategoryColorMap } from "../../utils/categoryColor";
import { formatDate, formatEur, pnlColorClass } from "../../utils/format";
import { GRIPR_TYPE_BADGE, GRIPR_TYPE_OPTIONS, griprSignedAmount, griprTypeLabel } from "../../utils/griprTransactionType";
import { msg, t } from "../../i18n";

const selectClass =
  "rounded-md border border-outline px-2.5 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

const FREQUENCY_LABEL: Record<GriprRecurrenceFrequency, string> = {
  weekly: msg("Weekly"),
  monthly: msg("Monthly"),
  yearly: msg("Yearly"),
};

const FREQUENCY_EVERY: Record<GriprRecurrenceFrequency, string> = {
  weekly: msg("Every {n} weeks"),
  monthly: msg("Every {n} months"),
  yearly: msg("Every {n} years"),
};

function frequencyLabel(r: GriprRecurring): string {
  return r.interval > 1 ? t(FREQUENCY_EVERY[r.frequency], { n: r.interval }) : t(FREQUENCY_LABEL[r.frequency]);
}

/** The overview only ever shows the top-level category, whether a rule is tagged at the top
 * level or one of its subcategories — same convention as Transactions' Category column. */
function resolveTopCategory(categoryId: number | null, categoriesById: Map<number, GriprCategory>): GriprCategory | null {
  if (categoryId === null) return null;
  const category = categoriesById.get(categoryId);
  if (!category) return null;
  return category.parent_id === null ? category : categoriesById.get(category.parent_id) ?? null;
}

export default function GriprRecurring() {
  const queryClient = useQueryClient();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const [editing, setEditing] = useState<GriprRecurring | undefined | null>(null); // null = closed
  const [scrolled, setScrolled] = useState(false);
  const [typeFilter, setTypeFilter] = useState<GriprTransactionType | "">("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");

  const accountsQuery = useQuery({ queryKey: ["gripr-accounts", false], queryFn: () => griprApi.listAccounts() });
  const categoriesQuery = useQuery({ queryKey: ["gripr-categories"], queryFn: () => griprApi.listCategories() });
  const recurringQuery = useQuery({ queryKey: ["gripr-recurring"], queryFn: () => griprApi.listRecurring() });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["gripr-recurring"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-transactions"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-accounts"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-budgets"] });
  };

  const createMutation = useMutation({
    mutationFn: (input: GriprRecurringInput) => griprApi.createRecurring(input),
    onSuccess: () => {
      invalidateAll();
      setEditing(null);
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: Partial<GriprRecurringInput> }) => griprApi.updateRecurring(id, input),
    onSuccess: () => {
      invalidateAll();
      setEditing(null);
    },
  });
  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) => griprApi.updateRecurring(id, { is_active }),
    onSuccess: invalidateAll,
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => griprApi.deleteRecurring(id),
    onSuccess: invalidateAll,
  });

  const accountsById = useMemo(
    () => new Map((accountsQuery.data ?? []).map((a) => [a.id, a])),
    [accountsQuery.data],
  );
  const categories = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);
  const categoryColors = useMemo(() => buildCategoryColorMap(categories), [categories]);
  const categoriesById = useMemo(() => new Map(categories.map((c) => [c.id, c])), [categories]);
  // Top-level categories only, same as the Transactions page's category filter — picking one
  // also matches everything filed under it (see categoryFilterIds below).
  const categoryOptions = useMemo(
    () => categories.filter((c) => c.parent_id === null).sort((a, b) => a.name.localeCompare(b.name)),
    [categories],
  );
  // A selected (always top-level) category filter also matches every subcategory filed under
  // it — the options list only offers top-level picks, so this always expands, never narrows.
  const categoryFilterIds = useMemo(() => {
    if (!categoryFilter) return null;
    const id = Number(categoryFilter);
    return new Set([id, ...categories.filter((c) => c.parent_id === id).map((c) => c.id)]);
  }, [categoryFilter, categories]);

  const rules = (recurringQuery.data ?? []).filter(
    (r) =>
      (!typeFilter || r.type === typeFilter) &&
      (!categoryFilterIds || (r.category_id !== null && categoryFilterIds.has(r.category_id))),
  );

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow>
        {/* On mobile this is the FAB's job instead (MobileFab, below), like every other page's add action. */}
        <GriprButton onClick={() => setEditing(undefined)} className="hidden sm:inline-flex">{t("Add recurring")}</GriprButton>
      </ModuleTopRow>
      <PageTitle>{t("Recurring")}</PageTitle>

      <p className="text-sm text-on-surface-variant">{t("Subscriptions, salary, mortgage payments — anything on a schedule. Its next occurrence is booked into Transactions once it's within 2 days out so you can review or adjust it before it happens, but it won't count toward any balance, budget, or overview total until its own date arrives.")}</p>

      <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-outline-variant bg-surface p-3">
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium uppercase tracking-wide text-on-surface-variant">{t("Type")}</span>
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as GriprTransactionType | "")} className={selectClass}>
            <option value="">{t("All")}</option>
            {GRIPR_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {t(o.label)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium uppercase tracking-wide text-on-surface-variant">{t("Category")}</span>
          <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className={selectClass}>
            <option value="">{t("All")}</option>
            {categoryOptions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="overflow-hidden rounded-2xl border border-outline-variant bg-surface">
        {/* One line per rule; on a phone the name column stays pinned while the rest scrolls,
            fading behind it once scrolled (`.pinned-col`, index.css). */}
        <div
          className={`overflow-x-auto ${scrolled ? "pinned-col-scrolled" : ""}`}
          onScroll={(e) => setScrolled(e.currentTarget.scrollLeft > 0)}
        >
          <table className="w-full whitespace-nowrap text-sm">
            <thead>
              <tr className="border-b border-outline-variant text-left text-xs uppercase tracking-wide text-on-surface-variant">
                <th className="pinned-col px-4 py-2 font-medium">{t("Name")}</th>
                <th className="px-4 py-2 font-medium">{t("Category")}</th>
                <th className="px-4 py-2 font-medium">{t("Type")}</th>
                <th className="px-4 py-2 font-medium">{t("Account")}</th>
                <th className="px-4 py-2 font-medium">{t("Frequency")}</th>
                <th className="px-4 py-2 font-medium">{t("Next due")}</th>
                <th className="px-4 py-2 text-right font-medium">{t("Amount")}</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {recurringQuery.isLoading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-6 text-center text-on-surface-variant">{t("Loading…")}</td>
                </tr>
              ) : recurringQuery.isError ? (
                <tr>
                  <td colSpan={8} className="px-4 py-6 text-center">
                    <QueryError message={t("Couldn't load recurring transactions.")} onRetry={() => recurringQuery.refetch()} />
                  </td>
                </tr>
              ) : rules.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-6 text-center text-on-surface-variant">{t("No recurring transactions yet")}</td>
                </tr>
              ) : (
                rules.map((r) => {
                  const topCategory = resolveTopCategory(r.category_id, categoriesById);
                  return (
                  <tr key={r.id} className={`border-b border-outline-variant last:border-0 hover:bg-on-surface/5 ${r.is_active ? "" : "opacity-50"}`}>
                    <td className="pinned-col max-w-[10rem] truncate px-4 py-2 font-medium text-on-surface sm:max-w-none" title={r.name}>
                      {r.name}
                    </td>
                    <td className="px-4 py-2 text-on-surface-variant">
                      {topCategory ? (
                        <span className="flex items-center gap-1.5">
                          <span
                            className="h-2 w-2 shrink-0 rounded-full"
                            style={{ backgroundColor: categoryColors.get(topCategory.id) ?? "#94a3b8" }}
                          />
                          {topCategory.name}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${GRIPR_TYPE_BADGE[r.type]}`}>
                        {griprTypeLabel(r.type)}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <span className="flex items-center gap-1">
                        <AccountBadge name={r.account_name ?? ""} account={accountsById.get(r.account_id)} />
                        {r.counter_account_name && (
                          <>
                            <span className="text-on-surface-variant">→</span>
                            <AccountBadge
                              name={r.counter_account_name}
                              account={r.counter_account_id ? accountsById.get(r.counter_account_id) : undefined}
                            />
                          </>
                        )}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-on-surface-variant">{frequencyLabel(r)}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-on-surface-variant">
                      {r.is_active ? formatDate(r.next_due_date) : t("paused")}
                    </td>
                    <td className={`px-4 py-2 text-right tabular-nums font-medium ${r.type === "transfer" ? "text-on-surface-variant" : pnlColorClass(griprSignedAmount(r))}`}>
                      {r.type === "transfer" ? formatEur(r.amount) : formatEur(griprSignedAmount(r))}
                    </td>
                    <td className="px-4 py-2 text-right whitespace-nowrap">
                      <button
                        onClick={() => toggleActiveMutation.mutate({ id: r.id, is_active: !r.is_active })}
                        className="text-on-surface-variant hover:text-on-surface"
                      >
                        {r.is_active ? t("Pause") : t("Resume")}
                      </button>
                      <button onClick={() => setEditing(r)} className="ml-3 text-on-surface-variant hover:text-on-surface" title={t("Edit")} aria-label={t("Edit")}>
                        <Pencil className="h-4 w-4" strokeWidth={2} />
                      </button>
                      <button
                        onClick={async () => {
                          const ok = await confirm({
                            title: t("Delete \"{name}\"?", { name: r.name }),
                            description: t("Transactions it already created stay in your ledger."),
                          });
                          if (ok) deleteMutation.mutate(r.id);
                        }}
                        className="ml-3 text-error hover:opacity-80"
                        title={t("Delete")}
                        aria-label={t("Delete")}
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
      </div>

      {editing !== null && (
        <RecurringForm
          accounts={accountsQuery.data ?? []}
          categories={categoriesQuery.data ?? []}
          initial={editing}
          isSubmitting={createMutation.isPending || updateMutation.isPending}
          onCancel={() => setEditing(null)}
          onSubmit={(input) => {
            if (editing) {
              updateMutation.mutate({ id: editing.id, input });
            } else {
              createMutation.mutate(input);
            }
          }}
        />
      )}

      <MobileFab label={t("Add recurring")} onClick={() => setEditing(undefined)} />

      {confirmDialog}
    </div>
  );
}
