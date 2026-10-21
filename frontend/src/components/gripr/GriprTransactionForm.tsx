import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { griprApi } from "../../api/griprClient";
import type {
  GriprAccount,
  GriprCategory,
  GriprRefundOf,
  GriprTransaction,
  GriprTransactionInput,
  GriprTransactionType,
} from "../../api/griprTypes";
import { apiToDecimalInput, decimalInputToApi, formatDate, formatEur, todayIsoDate } from "../../utils/format";
import { GRIPR_TYPE_OPTIONS, griprCategoryKindFor } from "../../utils/griprTransactionType";
import ModalOverlay from "../ModalOverlay";
import TransactionAttachments from "../TransactionAttachments";
import { QueryError } from "../ui/QueryError";
import { t as tr } from "../../i18n";

const inputClass =
  "rounded-md border border-outline px-2.5 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

function field(label: string, input: React.ReactNode) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{label}</span>
      {input}
    </label>
  );
}

interface FormState {
  date: string;
  type: GriprTransactionType;
  account_id: string;
  counter_account_id: string;
  top_category_id: string;
  sub_category_id: string;
  amount: string;
  notes: string;
  /** Only meaningful while type is "refund": the expense it came back for. */
  refund_of: GriprRefundOf | null;
  /** Only meaningful while type is "expense": the part fronted for others, and who owes it. */
  expected_back: string;
  expected_from: string;
}

function splitCategory(categoryId: number | null | undefined, categories: GriprCategory[]) {
  const category = categoryId != null ? categories.find((c) => c.id === categoryId) : undefined;
  if (!category) return { category, top: "", sub: "" };
  if (category.parent_id != null) return { category, top: String(category.parent_id), sub: String(category.id) };
  return { category, top: String(category.id), sub: "" };
}

/** A new refund for `expense`: same category (it's that spending coming back), half the
 * amount -- the split-the-bill case this exists for -- and no account yet, since the money
 * often lands somewhere other than the account that paid. */
function refundFormState(expense: GriprTransaction, categories: GriprCategory[]): FormState {
  const { top, sub } = splitCategory(expense.category_id, categories);
  return {
    date: todayIsoDate(),
    type: "refund",
    account_id: "",
    counter_account_id: "",
    top_category_id: top,
    sub_category_id: sub,
    amount: apiToDecimalInput((parseFloat(expense.amount) / 2).toFixed(2)),
    notes: "",
    expected_back: "",
    expected_from: "",
    refund_of: {
      id: expense.id,
      date: expense.date,
      amount: expense.amount,
      account_name: expense.account_name,
      notes: expense.notes,
    },
  };
}

function toFormState(
  t: GriprTransaction | undefined,
  categories: GriprCategory[],
  defaultAccountId?: number,
  defaultCategoryId?: number,
): FormState {
  let type: GriprTransactionType = t?.type ?? "expense";
  const { category, top: topCategoryId, sub: subCategoryId } = splitCategory(
    t?.category_id ?? (t ? undefined : defaultCategoryId),
    categories,
  );
  if (!t && category) type = category.kind;
  return {
    date: t?.date ?? todayIsoDate(),
    type,
    account_id: t?.account_id != null ? String(t.account_id) : defaultAccountId != null ? String(defaultAccountId) : "",
    counter_account_id: t?.counter_account_id != null ? String(t.counter_account_id) : "",
    top_category_id: topCategoryId,
    sub_category_id: subCategoryId,
    amount: apiToDecimalInput(t?.amount),
    notes: t?.notes ?? "",
    refund_of: t?.refund_of ?? null,
    expected_back: apiToDecimalInput(t?.expected_back ?? undefined),
    expected_from: t?.expected_from ?? "",
  };
}

export default function GriprTransactionForm({
  accounts,
  categories,
  initial,
  defaultAccountId,
  defaultCategoryId,
  refundOf,
  onAddRefund,
  onDelete,
  onCancel,
  onSubmit,
  isSubmitting,
}: {
  accounts: GriprAccount[];
  categories: GriprCategory[];
  initial: GriprTransaction | undefined;
  defaultAccountId?: number;
  defaultCategoryId?: number;
  /** Opens the form as a new refund for this expense instead of a blank transaction. */
  refundOf?: GriprTransaction;
  /** Shown as "Got money back" while editing an expense: the parent reopens the form with
   * `refundOf` set to it. */
  onAddRefund?: (expense: GriprTransaction) => void;
  /** Shown as "Delete transaction…" while editing: the list's rows carry no delete button of
   * their own, so this is where a transaction is removed (the parent confirms first). */
  onDelete?: (transaction: GriprTransaction) => void;
  onCancel: () => void;
  /** `files` are the attachments picked on a new transaction, to upload once it exists; always
   * empty when editing, where attachments are added and removed on the spot. */
  onSubmit: (input: GriprTransactionInput, files: File[]) => void;
  isSubmitting: boolean;
}) {
  const [form, setForm] = useState<FormState>(
    refundOf ? refundFormState(refundOf, categories) : toFormState(initial, categories, defaultAccountId, defaultCategoryId),
  );
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const update = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  // Most-used first, so picking the account you almost always pick doesn't mean scrolling
  // through everything else in whatever order the accounts view happens to list them.
  const accountsByUsage = [...accounts].sort((a, b) => b.usage_count - a.usage_count || a.name.localeCompare(b.name));

  const isTransfer = form.type === "transfer";
  const isExpense = form.type === "expense";
  // Money coming in can be the repayment of something fronted: offered as a pick from what's
  // still owed, which turns it into a refund linked to that expense.
  const mayRepay = (form.type === "income" || form.type === "refund") && form.refund_of === null;
  const receivablesQuery = useQuery({ queryKey: ["gripr-receivables"], queryFn: () => griprApi.listReceivables(), enabled: mayRepay });
  const openReceivables = (receivablesQuery.data?.items ?? []).filter((r) => r.id !== initial?.id);
  // A linked refund always takes its expense's category (the backend enforces it too), so the
  // pickers are shown but locked rather than offering a choice that wouldn't stick.
  const isLinkedRefund = form.type === "refund" && form.refund_of !== null;
  const categoryKind = griprCategoryKindFor(form.type);
  const topCategories = categories
    .filter((c) => c.kind === categoryKind && c.parent_id === null)
    .sort((a, b) => a.name.localeCompare(b.name));
  const subCategories = categories
    .filter((c) => c.parent_id !== null && String(c.parent_id) === form.top_category_id)
    .sort((a, b) => a.name.localeCompare(b.name));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const categoryId = form.sub_category_id
      ? Number(form.sub_category_id)
      : form.top_category_id
        ? Number(form.top_category_id)
        : null;
    onSubmit({
      date: form.date,
      type: form.type,
      account_id: Number(form.account_id),
      counter_account_id: isTransfer && form.counter_account_id ? Number(form.counter_account_id) : null,
      category_id: !isTransfer ? categoryId : null,
      refund_of_id: form.type === "refund" && form.refund_of ? form.refund_of.id : null,
      amount: decimalInputToApi(form.amount) ?? "0",
      notes: form.notes || null,
      expected_back: isExpense && form.expected_back.trim() ? decimalInputToApi(form.expected_back) : null,
      expected_from: isExpense && form.expected_back.trim() ? form.expected_from.trim() || null : null,
    }, initial ? [] : pendingFiles);
  };

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-md rounded-[28px] bg-surface p-6 shadow-xl">
        <h2 className="text-lg font-medium text-on-surface">
          {initial ? tr("Edit transaction") : refundOf ? tr("Add refund") : tr("Add transaction")}
        </h2>
        <form onSubmit={handleSubmit} className="mt-4 grid grid-cols-2 gap-3">
          {field(
            tr("Date"),
            <input type="date" required value={form.date} onChange={(e) => update({ date: e.target.value })} className={inputClass} />,
          )}
          {field(
            tr("Type"),
            <select
              value={form.type}
              onChange={(e) =>
                update({
                  type: e.target.value as GriprTransactionType,
                  top_category_id: "",
                  sub_category_id: "",
                  counter_account_id: "",
                  refund_of: null,
                })
              }
              className={inputClass}
            >
              {GRIPR_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {tr(o.label)}
                </option>
              ))}
            </select>,
          )}

          {isLinkedRefund && form.refund_of && (
            <div className="col-span-2 flex items-start justify-between gap-3 rounded-xl bg-surface-container px-3 py-2 text-sm">
              <div className="min-w-0 text-on-surface-variant">
                <div className="text-xs font-medium uppercase tracking-wide">{tr("Money back for")}</div>
                <div className="truncate text-on-surface">
                  {form.refund_of.notes || tr("Expense")} · {formatEur(form.refund_of.amount)}
                </div>
                <div className="text-xs">
                  {formatDate(form.refund_of.date)}
                  {form.refund_of.account_name ? ` · ${tr("paid from {account}", { account: form.refund_of.account_name })}` : ""}
                </div>
              </div>
              <button
                type="button"
                onClick={() => update({ refund_of: null })}
                className="shrink-0 text-xs font-medium text-primary hover:underline"
                title={tr("Keep this refund, but count it on its own date instead of the expense's")}
              >{tr("Unlink")}</button>
            </div>
          )}

          {field(
            isTransfer ? tr("From account") : form.type === "refund" ? tr("Received in") : tr("Account"),
            <select value={form.account_id} onChange={(e) => update({ account_id: e.target.value })} className={inputClass} required>
              <option value="">{tr("— select —")}</option>
              {accountsByUsage.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>,
          )}

          {isTransfer ? (
            field(
              tr("To account"),
              <select value={form.counter_account_id} onChange={(e) => update({ counter_account_id: e.target.value })} className={inputClass} required>
                <option value="">{tr("— select —")}</option>
                {accountsByUsage.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>,
            )
          ) : (
            field(
              tr("Category"),
              <select
                value={form.top_category_id}
                onChange={(e) => update({ top_category_id: e.target.value, sub_category_id: "" })}
                className={inputClass}
                disabled={isLinkedRefund}
              >
                <option value="">{tr("— none —")}</option>
                {topCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>,
            )
          )}

          {!isTransfer &&
            field(
              tr("Subcategory"),
              <select
                value={form.sub_category_id}
                onChange={(e) => update({ sub_category_id: e.target.value })}
                className={inputClass}
                disabled={isLinkedRefund || subCategories.length === 0}
              >
                <option value="">{subCategories.length ? tr("— general —") : tr("— no subcategories —")}</option>
                {subCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>,
            )}

          {field(
            tr("Amount (EUR)"),
            <input inputMode="decimal" required value={form.amount} onChange={(e) => update({ amount: e.target.value })} className={inputClass} />,
          )}

          {isExpense && (
            <>
              {field(
                tr("Expecting back (EUR)"),
                <input
                  inputMode="decimal"
                  placeholder={tr("Fronted for others")}
                  value={form.expected_back}
                  onChange={(e) => update({ expected_back: e.target.value })}
                  className={inputClass}
                />,
              )}
              {field(
                tr("From"),
                <input
                  placeholder={tr("Who pays you back")}
                  value={form.expected_from}
                  disabled={!form.expected_back.trim()}
                  onChange={(e) => update({ expected_from: e.target.value })}
                  className={inputClass}
                />,
              )}
            </>
          )}

          {mayRepay && receivablesQuery.isError && (
            <QueryError
              className="col-span-2 text-sm"
              message={tr("Couldn't load what you're owed, so this can't be marked as money back yet.")}
              onRetry={() => receivablesQuery.refetch()}
            />
          )}
          {mayRepay && openReceivables.length > 0 && (
            <div className="col-span-2">
              {field(
                tr("Money back for…"),
                <select
                  value=""
                  onChange={(e) => {
                    const r = openReceivables.find((x) => String(x.id) === e.target.value);
                    if (!r) return;
                    update({
                      type: "refund",
                      top_category_id: "",
                      sub_category_id: "",
                      refund_of: { id: r.id, date: r.date, amount: r.amount, account_name: r.account_name, notes: r.notes },
                    });
                  }}
                  className={inputClass}
                >
                  <option value="">{tr("— not a repayment —")}</option>
                  {openReceivables.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.notes || r.category_name || tr("Expense")}
                      {r.expected_from ? ` (${r.expected_from})` : ""} · {formatEur(r.outstanding)}{" "}{tr("open · {date}", { date: formatDate(r.date) })}</option>
                  ))}
                </select>,
              )}
            </div>
          )}

          <div className="col-span-2">
            {field(tr("Notes"), <input value={form.notes} onChange={(e) => update({ notes: e.target.value })} className={inputClass} />)}
          </div>

          <div className="col-span-2">
            <TransactionAttachments
              variant="gripr"
              source={griprApi.transactionAttachments}
              transactionId={initial?.id ?? null}
              pending={pendingFiles}
              onPendingChange={setPendingFiles}
            />
          </div>

          <div className="col-span-2 mt-2 flex items-center justify-end gap-2">
            {initial?.type === "expense" && onAddRefund && (
              <button
                type="button"
                onClick={() => onAddRefund(initial)}
                className="mr-auto text-sm font-medium text-primary hover:underline"
              >{tr("Got money back")}</button>
            )}
            <button
              type="button"
              onClick={onCancel}
              className="rounded-full border border-outline px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10"
            >{tr("Cancel")}</button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:opacity-90 disabled:opacity-50"
            >
              {isSubmitting ? tr("Saving…") : tr("Save")}
            </button>
          </div>
          {initial && onDelete && (
            <button
              type="button"
              onClick={() => onDelete(initial)}
              className="col-span-2 justify-self-center rounded-full px-4 py-2 text-sm font-medium text-error hover:bg-error/10"
            >{tr("Delete transaction…")}</button>
          )}
        </form>
    </ModalOverlay>
  );
}
