import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Pencil, Trash2 } from "lucide-react";
import { useId, useState } from "react";

import { griprApi } from "../../api/griprClient";
import type {
  GriprAccount,
  GriprCategory,
  GriprTransaction,
  GriprTransactionInput,
} from "../../api/griprTypes";
import { CategoryGlyph } from "../../utils/categoryIcons";
import { formatDate, formatEur, pnlColorClass } from "../../utils/format";
import { GRIPR_TYPE_BADGE, griprSignedAmount } from "../../utils/griprTransactionType";
import ColorPicker from "../ColorPicker";
import InlineEditText from "../InlineEditText";
import ModalOverlay from "../ModalOverlay";
import AccountBadge from "./AccountBadge";
import GriprTransactionForm from "./GriprTransactionForm";
import { useConfirmDialog } from "./useConfirmDialog";

const PAGE_SIZE = 20;

const inputClass =
  "rounded-md border border-outline px-2.5 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

/** Everything about one top-level category, opened by clicking its Budget tile -- the same
 * "tile opens a detail dialog" shape as AccountCard/AccountDetailDialog. The period's
 * transactions come first (rolled up from subcategories, same as the budget "spent" figure,
 * or narrowed to one subcategory), with add/edit/delete inline; the category's own settings
 * (name, colour, subcategories, loan link, archive, delete) sit below them, since those change
 * far less often than a budget gets checked. */
export default function CategoryDetailDialog({
  category,
  color,
  subcategories,
  loanAccounts,
  periodStart,
  periodEnd,
  periodLabel,
  accounts,
  categories,
  accountsById,
  onClose,
}: {
  category: GriprCategory;
  color: string;
  /** This category's children, archived ones included -- they're managed here. */
  subcategories: GriprCategory[];
  loanAccounts: GriprAccount[];
  periodStart: string;
  periodEnd: string;
  periodLabel: string;
  accounts: GriprAccount[];
  categories: GriprCategory[];
  accountsById: Map<number, GriprAccount>;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const [page, setPage] = useState(0);
  // Null = the whole category, subcategories rolled up; set = just that subcategory.
  const [subFilter, setSubFilter] = useState<number | null>(null);
  const [addingTransaction, setAddingTransaction] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<GriprTransaction | undefined>(undefined);
  // Set = the "add" form is a new refund for this expense ("Got money back").
  const [refundOf, setRefundOf] = useState<GriprTransaction | undefined>(undefined);
  const [newSubName, setNewSubName] = useState("");
  const loanSelectId = useId();

  const filteredCategoryId = subFilter ?? category.id;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["gripr-transactions"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-receivables"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-category-transactions"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-budgets"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-accounts"] });
  };
  const invalidateCategories = () => {
    queryClient.invalidateQueries({ queryKey: ["gripr-categories"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-budgets"] });
  };

  const { data, isLoading } = useQuery({
    queryKey: ["gripr-category-transactions", filteredCategoryId, periodStart, periodEnd, page],
    queryFn: () =>
      griprApi.listTransactions({
        categoryId: filteredCategoryId,
        dateFrom: periodStart,
        dateTo: periodEnd,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        sortBy: "date",
        sortDir: "desc",
      }),
  });

  const createTransactionMutation = useMutation({
    mutationFn: (input: GriprTransactionInput) => griprApi.createTransaction(input),
    onSuccess: () => {
      invalidate();
      setAddingTransaction(false);
      setRefundOf(undefined);
    },
  });
  const updateTransactionMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: GriprTransactionInput }) => griprApi.updateTransaction(id, input),
    onSuccess: () => {
      invalidate();
      setEditingTransaction(undefined);
    },
  });
  const deleteTransactionMutation = useMutation({
    mutationFn: (id: number) => griprApi.deleteTransaction(id),
    onSuccess: invalidate,
  });

  const updateCategoryMutation = useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: number;
      patch: { name?: string; color?: string | null; is_archived?: boolean; linked_loan_account_id?: number | null };
    }) => griprApi.updateCategory(id, patch),
    onSuccess: invalidateCategories,
  });
  const createSubMutation = useMutation({
    mutationFn: (name: string) => griprApi.createCategory({ name, kind: category.kind, parent_id: category.id }),
    onSuccess: () => {
      invalidateCategories();
      setNewSubName("");
    },
  });
  const deleteCategoryMutation = useMutation({
    mutationFn: (id: number) => griprApi.deleteCategory(id),
    onSuccess: () => {
      invalidateCategories();
      queryClient.invalidateQueries({ queryKey: ["gripr-transactions"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-category-transactions"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-recurring"] });
    },
  });

  async function confirmDelete(target: GriprCategory, childCount: number) {
    const cascadeNote = childCount > 0 ? ` Its ${childCount} subcategor${childCount === 1 ? "y" : "ies"} will be deleted too.` : "";
    const ok = await confirm({
      title: `Delete "${target.name}"?`,
      description: `Transactions filed under it become uncategorized, not deleted.${cascadeNote}`,
    });
    if (!ok) return;
    if (target.id === category.id) {
      deleteCategoryMutation.mutate(target.id, { onSuccess: onClose });
    } else {
      if (subFilter === target.id) setSubFilter(null);
      deleteCategoryMutation.mutate(target.id);
    }
  }

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const items = data?.items ?? [];
  const totalAmount = items
    .filter((t) => t.type !== "transfer")
    .reduce((sum, t) => sum + griprSignedAmount(t), 0);
  const isExpense = category.kind === "expense";
  const linkedLoanMissing =
    category.linked_loan_account_id != null && !loanAccounts.some((a) => a.id === category.linked_loan_account_id);

  return (
    <>
      <ModalOverlay
        onClose={onClose}
        cardClassName="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-[28px] bg-surface shadow-xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-outline-variant p-5">
          <div className="flex min-w-0 items-center gap-3">
            <ColorPicker
              value={category.color}
              onSelect={(next) => updateCategoryMutation.mutate({ id: category.id, patch: { color: next } })}
              trigger={
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                  style={{ backgroundColor: color }}
                  title="Change colour"
                >
                  <CategoryGlyph name={category.name} className="h-5 w-5 text-white" strokeWidth={2} />
                </span>
              }
            />
            <div className="flex min-w-0 flex-col">
              <InlineEditText
                value={category.name}
                onSave={(name) => updateCategoryMutation.mutate({ id: category.id, patch: { name } })}
                title="Edit category name"
                textClassName="truncate text-lg font-medium text-on-surface"
              />
              <span className="text-xs text-on-surface-variant">
                {isExpense ? "Expense" : "Income"} category · {periodLabel}
                {category.is_archived && " · archived"}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="shrink-0 text-on-surface-variant hover:text-on-surface" aria-label="Close">
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-on-surface">Transactions</h3>
              {subcategories.length > 0 && (
                <select
                  aria-label="Subcategory"
                  value={subFilter ?? ""}
                  onChange={(e) => {
                    setSubFilter(e.target.value ? Number(e.target.value) : null);
                    setPage(0);
                  }}
                  className="rounded-md border border-outline px-2 py-1 text-xs"
                >
                  <option value="">All of {category.name}</option>
                  {subcategories.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <button
              onClick={() => setAddingTransaction(true)}
              className="rounded-full border border-outline px-3 py-1 text-xs font-medium text-primary hover:bg-primary/10"
            >
              + Add transaction
            </button>
          </div>
          <div className="mt-1 flex items-baseline justify-between text-sm text-on-surface-variant">
            <span>
              {total} transaction{total === 1 ? "" : "s"}
            </span>
            {total > 0 && (
              <span className={`font-medium tabular-nums ${pnlColorClass(totalAmount)}`}>{formatEur(totalAmount)}</span>
            )}
          </div>

          <div className="mt-2">
            {isLoading ? (
              <div className="py-6 text-center text-sm text-on-surface-variant">Loading…</div>
            ) : total === 0 ? (
              <div className="py-6 text-center text-sm text-on-surface-variant">No transactions in this period.</div>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {items.map((t) => (
                    <tr
                      key={t.id}
                      onClick={() => setEditingTransaction(t)}
                      className="cursor-pointer border-b border-outline-variant last:border-0 hover:bg-on-surface/5"
                    >
                      <td className="py-2 pr-2 text-on-surface-variant">
                        <div className="whitespace-nowrap">{formatDate(t.date)}</div>
                        {/* On a phone there's no room for separate type/subcategory/notes
                            columns next to the amount -- they fold into one line here. */}
                        <div className="max-w-[9rem] truncate text-xs sm:hidden">
                          {[
                            t.type !== "expense" && t.type !== "income" ? t.type : null,
                            t.category_name && t.category_name !== category.name ? t.category_name : null,
                            t.notes,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </div>
                      </td>
                      <td className="hidden py-2 pr-2 sm:table-cell">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${GRIPR_TYPE_BADGE[t.type]}`}>
                          {t.type}
                        </span>
                      </td>
                      <td className="py-2 pr-2">
                        <AccountBadge name={t.account_name ?? ""} account={accountsById.get(t.account_id)} />
                      </td>
                      <td className="hidden py-2 pr-2 text-on-surface-variant sm:table-cell">
                        {t.category_name && t.category_name !== category.name ? t.category_name : ""}
                      </td>
                      <td className="hidden max-w-[10rem] truncate py-2 pr-2 text-on-surface-variant sm:table-cell">{t.notes}</td>
                      <td
                        className={`whitespace-nowrap py-2 pr-2 text-right tabular-nums font-medium ${
                          t.type === "transfer" ? "text-on-surface-variant" : pnlColorClass(griprSignedAmount(t))
                        }`}
                      >
                        {t.type === "transfer" ? formatEur(t.amount) : formatEur(griprSignedAmount(t))}
                      </td>
                      <td className="py-2 text-right whitespace-nowrap">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingTransaction(t);
                          }}
                          className="hidden text-on-surface-variant hover:text-on-surface sm:inline"
                          title="Edit"
                          aria-label="Edit"
                        >
                          <Pencil className="h-4 w-4" strokeWidth={2} />
                        </button>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            const ok = await confirm({
                              title: "Delete transaction?",
                              description: `This ${t.type} transaction from ${formatDate(t.date)} will be permanently removed.`,
                            });
                            if (ok) deleteTransactionMutation.mutate(t.id);
                          }}
                          className="text-error hover:opacity-80 sm:ml-3"
                          title="Delete"
                          aria-label="Delete"
                        >
                          <Trash2 className="h-4 w-4" strokeWidth={2} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {totalPages > 1 && (
            <div className="mt-2 flex items-center justify-end gap-2 text-sm text-on-surface-variant">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="rounded-full border border-outline px-3 py-1 disabled:opacity-40"
              >
                Prev
              </button>
              <span>
                {page + 1} / {totalPages}
              </span>
              <button
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-full border border-outline px-3 py-1 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}

          <div className="mt-5 flex flex-col gap-4 rounded-2xl border border-outline-variant p-4">
            <h3 className="text-sm font-semibold text-on-surface">Category settings</h3>

            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">Subcategories</span>
              {subcategories.length === 0 ? (
                <span className="text-sm text-on-surface-variant">
                  None yet — add one to tag transactions more finely without adding a budget line.
                </span>
              ) : (
                <ul className="flex flex-col gap-1">
                  {subcategories.map((sub) => (
                    <li
                      key={sub.id}
                      className={`flex items-center justify-between gap-2 rounded px-1 py-0.5 text-sm ${sub.is_archived ? "text-on-surface-variant/50" : "text-on-surface"}`}
                    >
                      <span className="flex min-w-0 items-center gap-1">
                        <InlineEditText
                          value={sub.name}
                          onSave={(name) => updateCategoryMutation.mutate({ id: sub.id, patch: { name } })}
                          title="Edit subcategory name"
                          textClassName={`truncate text-sm ${sub.is_archived ? "text-on-surface-variant/50" : "text-on-surface"}`}
                        />
                        {sub.is_archived && <span className="text-xs"> (archived)</span>}
                      </span>
                      <span className="flex shrink-0 gap-3 text-on-surface-variant">
                        <button
                          type="button"
                          onClick={() =>
                            updateCategoryMutation.mutate({ id: sub.id, patch: { is_archived: !sub.is_archived } })
                          }
                          className="hover:text-on-surface"
                          title={sub.is_archived ? "Unarchive" : "Archive"}
                          aria-label={sub.is_archived ? `Unarchive ${sub.name}` : `Archive ${sub.name}`}
                        >
                          {sub.is_archived ? (
                            <ArchiveRestore className="h-4 w-4" strokeWidth={2} />
                          ) : (
                            <Archive className="h-4 w-4" strokeWidth={2} />
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => confirmDelete(sub, 0)}
                          className="text-error/70 hover:text-error"
                          title="Delete"
                          aria-label={`Delete ${sub.name}`}
                        >
                          <Trash2 className="h-4 w-4" strokeWidth={2} />
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (newSubName.trim()) createSubMutation.mutate(newSubName.trim());
                }}
                className="flex gap-2"
              >
                <input
                  aria-label="New subcategory name"
                  placeholder="New subcategory"
                  value={newSubName}
                  onChange={(e) => setNewSubName(e.target.value)}
                  className={`min-w-0 flex-1 ${inputClass}`}
                />
                <button
                  type="submit"
                  disabled={!newSubName.trim() || createSubMutation.isPending}
                  className="rounded-full border border-outline px-3 py-1 text-xs font-medium text-primary hover:bg-primary/10 disabled:opacity-40"
                >
                  Add
                </button>
              </form>
            </div>

            {isExpense && (
              <div className="flex flex-col gap-1 text-sm">
                <label
                  htmlFor={loanSelectId}
                  className="text-xs font-medium uppercase tracking-wide text-on-surface-variant"
                >
                  Pays off a loan
                </label>
                <select
                  id={loanSelectId}
                  aria-describedby={`${loanSelectId}-help`}
                  value={category.linked_loan_account_id ?? ""}
                  disabled={updateCategoryMutation.isPending}
                  onChange={(e) =>
                    updateCategoryMutation.mutate({
                      id: category.id,
                      patch: { linked_loan_account_id: e.target.value ? Number(e.target.value) : null },
                    })
                  }
                  className={inputClass}
                >
                  <option value="">— not linked —</option>
                  {linkedLoanMissing && <option value={category.linked_loan_account_id ?? ""}>a deleted account</option>}
                  {loanAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
                <span id={`${loanSelectId}-help`} className="text-xs text-on-surface-variant">
                  {loanAccounts.length === 0
                    ? "No loan-type accounts exist yet — add one on Accounts first."
                    : "An expense filed under this category automatically lowers the linked loan's balance by the same amount."}
                </span>
              </div>
            )}

            <div className="flex flex-wrap gap-2 border-t border-outline-variant pt-3">
              <button
                type="button"
                onClick={() =>
                  updateCategoryMutation.mutate({ id: category.id, patch: { is_archived: !category.is_archived } })
                }
                className="flex items-center gap-1.5 rounded-full border border-outline px-3 py-1.5 text-sm font-medium text-on-surface hover:bg-on-surface/5"
                title={
                  category.is_archived
                    ? "Show it on Budget again"
                    : "Hide it from Budget; its transactions and history stay"
                }
              >
                {category.is_archived ? (
                  <ArchiveRestore className="h-4 w-4" strokeWidth={2} />
                ) : (
                  <Archive className="h-4 w-4" strokeWidth={2} />
                )}
                {category.is_archived ? "Unarchive" : "Archive"}
              </button>
              <button
                type="button"
                onClick={() => confirmDelete(category, subcategories.length)}
                className="flex items-center gap-1.5 rounded-full border border-outline px-3 py-1.5 text-sm font-medium text-error hover:bg-error/10"
              >
                <Trash2 className="h-4 w-4" strokeWidth={2} />
                Delete
              </button>
            </div>
          </div>
        </div>

        <div className="flex justify-end border-t border-outline-variant p-4">
          <button
            onClick={onClose}
            className="rounded-full border border-outline px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10"
          >
            Close
          </button>
        </div>
      </ModalOverlay>

      {(addingTransaction || editingTransaction !== undefined) && (
        <GriprTransactionForm
          key={refundOf ? `refund-${refundOf.id}` : (editingTransaction?.id ?? "new")}
          accounts={accounts}
          categories={categories}
          initial={editingTransaction}
          refundOf={refundOf}
          onAddRefund={(expense) => {
            setEditingTransaction(undefined);
            setAddingTransaction(true);
            setRefundOf(expense);
          }}
          defaultCategoryId={filteredCategoryId}
          isSubmitting={createTransactionMutation.isPending || updateTransactionMutation.isPending}
          onCancel={() => {
            setAddingTransaction(false);
            setEditingTransaction(undefined);
            setRefundOf(undefined);
          }}
          onSubmit={(input) => {
            if (editingTransaction) {
              updateTransactionMutation.mutate({ id: editingTransaction.id, input });
            } else {
              createTransactionMutation.mutate(input);
            }
          }}
        />
      )}

      {confirmDialog}
    </>
  );
}
