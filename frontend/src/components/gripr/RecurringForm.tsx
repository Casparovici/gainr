import { useState } from "react";

import type {
  GriprAccount,
  GriprCategory,
  GriprRecurrenceFrequency,
  GriprRecurring,
  GriprRecurringInput,
  GriprTransactionType,
} from "../../api/griprTypes";
import { apiToDecimalInput, decimalInputToApi, todayIsoDate } from "../../utils/format";
import { GRIPR_TYPE_OPTIONS, griprCategoryKindFor } from "../../utils/griprTransactionType";
import ModalOverlay from "../ModalOverlay";

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
  name: string;
  type: GriprTransactionType;
  account_id: string;
  counter_account_id: string;
  top_category_id: string;
  sub_category_id: string;
  amount: string;
  frequency: GriprRecurrenceFrequency;
  interval: string;
  start_date: string;
  end_date: string;
  notes: string;
}

function toFormState(r: GriprRecurring | undefined, categories: GriprCategory[], defaultAccountId?: number): FormState {
  let topCategoryId = "";
  let subCategoryId = "";
  if (r?.category_id != null) {
    const category = categories.find((c) => c.id === r.category_id);
    if (category?.parent_id != null) {
      topCategoryId = String(category.parent_id);
      subCategoryId = String(category.id);
    } else if (category) {
      topCategoryId = String(category.id);
    }
  }
  return {
    name: r?.name ?? "",
    type: r?.type ?? "expense",
    account_id: r?.account_id != null ? String(r.account_id) : defaultAccountId != null ? String(defaultAccountId) : "",
    counter_account_id: r?.counter_account_id != null ? String(r.counter_account_id) : "",
    top_category_id: topCategoryId,
    sub_category_id: subCategoryId,
    amount: apiToDecimalInput(r?.amount),
    frequency: r?.frequency ?? "monthly",
    interval: r?.interval != null ? String(r.interval) : "1",
    start_date: r?.start_date ?? todayIsoDate(),
    end_date: r?.end_date ?? "",
    notes: r?.notes ?? "",
  };
}

export default function RecurringForm({
  accounts,
  categories,
  initial,
  onCancel,
  onSubmit,
  isSubmitting,
}: {
  accounts: GriprAccount[];
  categories: GriprCategory[];
  initial: GriprRecurring | undefined;
  onCancel: () => void;
  onSubmit: (input: GriprRecurringInput) => void;
  isSubmitting: boolean;
}) {
  const [form, setForm] = useState<FormState>(toFormState(initial, categories));
  const update = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  const isTransfer = form.type === "transfer";
  const accountsByUsage = [...accounts].sort((a, b) => b.usage_count - a.usage_count || a.name.localeCompare(b.name));
  const topCategories = categories
    .filter((c) => c.kind === griprCategoryKindFor(form.type) && c.parent_id === null)
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
      name: form.name,
      type: form.type,
      account_id: Number(form.account_id),
      counter_account_id: isTransfer && form.counter_account_id ? Number(form.counter_account_id) : null,
      category_id: !isTransfer ? categoryId : null,
      amount: decimalInputToApi(form.amount) ?? "0",
      frequency: form.frequency,
      interval: Math.max(1, Number(form.interval) || 1),
      start_date: form.start_date,
      end_date: form.end_date || null,
      notes: form.notes || null,
    });
  };

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-md rounded-[28px] bg-surface p-6 shadow-xl">
        <h2 className="text-lg font-medium text-on-surface">{initial ? "Edit recurring" : "New recurring"}</h2>
        <form onSubmit={handleSubmit} className="mt-4 grid grid-cols-2 gap-3">
          <div className="col-span-2">
            {field("Name", <input required autoFocus value={form.name} onChange={(e) => update({ name: e.target.value })} className={inputClass} placeholder="Netflix, Salary, Mortgage…" />)}
          </div>

          {field(
            "Type",
            <select
              value={form.type}
              onChange={(e) =>
                update({ type: e.target.value as GriprTransactionType, top_category_id: "", sub_category_id: "", counter_account_id: "" })
              }
              className={inputClass}
            >
              {GRIPR_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>,
          )}
          {field(
            "Amount (EUR)",
            <input inputMode="decimal" required value={form.amount} onChange={(e) => update({ amount: e.target.value })} className={inputClass} />,
          )}

          {field(
            isTransfer ? "From account" : "Account",
            <select value={form.account_id} onChange={(e) => update({ account_id: e.target.value })} className={inputClass} required>
              <option value="">— select —</option>
              {accountsByUsage.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>,
          )}

          {isTransfer ? (
            field(
              "To account",
              <select value={form.counter_account_id} onChange={(e) => update({ counter_account_id: e.target.value })} className={inputClass} required>
                <option value="">— select —</option>
                {accountsByUsage.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>,
            )
          ) : (
            field(
              "Category",
              <select
                value={form.top_category_id}
                onChange={(e) => update({ top_category_id: e.target.value, sub_category_id: "" })}
                className={inputClass}
              >
                <option value="">— none —</option>
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
              "Subcategory",
              <select
                value={form.sub_category_id}
                onChange={(e) => update({ sub_category_id: e.target.value })}
                className={inputClass}
                disabled={subCategories.length === 0}
              >
                <option value="">{subCategories.length ? "— general —" : "— no subcategories —"}</option>
                {subCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>,
            )}

          {field(
            "Repeats",
            <div className="flex items-center gap-1.5">
              <span className="shrink-0 text-sm text-on-surface-variant">every</span>
              <input
                type="number"
                min={1}
                required
                value={form.interval}
                onChange={(e) => update({ interval: e.target.value })}
                className={`${inputClass} w-14`}
              />
              <select
                value={form.frequency}
                onChange={(e) => update({ frequency: e.target.value as GriprRecurrenceFrequency })}
                className={`${inputClass} flex-1`}
              >
                <option value="weekly">week(s)</option>
                <option value="monthly">month(s)</option>
                <option value="yearly">year(s)</option>
              </select>
            </div>,
          )}
          {field(
            "Starts on",
            <input type="date" required value={form.start_date} onChange={(e) => update({ start_date: e.target.value })} className={inputClass} />,
          )}
          {field(
            "Ends on (optional)",
            <input type="date" value={form.end_date} onChange={(e) => update({ end_date: e.target.value })} className={inputClass} />,
          )}

          <div className="col-span-2">
            {field("Notes", <input value={form.notes} onChange={(e) => update({ notes: e.target.value })} className={inputClass} />)}
          </div>

          <div className="col-span-2 mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-full border border-outline px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:opacity-90 disabled:opacity-50"
            >
              {isSubmitting ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
    </ModalOverlay>
  );
}
