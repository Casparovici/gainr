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
import InfoHeading from "../ui/InfoTip";
import { t } from "../../i18n";

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
  /** Assets this transfer depreciates: the asset and the amount of the transfer that is its share. */
  depreciations: { account_id: string; amount: string }[];
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
    depreciations: (r?.depreciations ?? []).map((d) => ({ account_id: String(d.account_id), amount: apiToDecimalInput(d.amount) })),
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
  // A car, say: an asset whose value is set by hand. A transfer into the depreciation fund can be
  // what it loses (docs/adr/0034).
  const depreciableAssets = accounts.filter((a) => a.type === "asset" && a.balance_mode === "manual" && !a.is_archived);
  const setDepreciation = (i: number, patch: Partial<FormState["depreciations"][number]>) =>
    update({ depreciations: form.depreciations.map((d, j) => (j === i ? { ...d, ...patch } : d)) });
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
      depreciations: isTransfer
        ? form.depreciations
            .filter((d) => d.account_id && decimalInputToApi(d.amount))
            .map((d) => ({ account_id: Number(d.account_id), amount: decimalInputToApi(d.amount) ?? "0" }))
        : [],
    });
  };

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-md rounded-[28px] bg-surface p-6 shadow-xl">
        <h2 className="text-lg font-medium text-on-surface">{initial ? t("Edit recurring") : t("New recurring")}</h2>
        <form onSubmit={handleSubmit} className="mt-4 grid grid-cols-2 gap-3">
          <div className="col-span-2">
            {field(t("Name"), <input required autoFocus value={form.name} onChange={(e) => update({ name: e.target.value })} className={inputClass} placeholder={t("Netflix, Salary, Mortgage…")} />)}
          </div>

          {field(
            t("Type"),
            <select
              value={form.type}
              onChange={(e) =>
                update({ type: e.target.value as GriprTransactionType, top_category_id: "", sub_category_id: "", counter_account_id: "" })
              }
              className={inputClass}
            >
              {GRIPR_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {t(o.label)}
                </option>
              ))}
            </select>,
          )}
          {field(
            t("Amount (EUR)"),
            <input inputMode="decimal" required value={form.amount} onChange={(e) => update({ amount: e.target.value })} className={inputClass} />,
          )}

          {field(
            isTransfer ? t("From account") : t("Account"),
            <select value={form.account_id} onChange={(e) => update({ account_id: e.target.value })} className={inputClass} required>
              <option value="">{t("— select —")}</option>
              {accountsByUsage.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>,
          )}

          {isTransfer ? (
            field(
              t("To account"),
              <select value={form.counter_account_id} onChange={(e) => update({ counter_account_id: e.target.value })} className={inputClass} required>
                <option value="">{t("— select —")}</option>
                {accountsByUsage.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>,
            )
          ) : (
            field(
              t("Category"),
              <select
                value={form.top_category_id}
                onChange={(e) => update({ top_category_id: e.target.value, sub_category_id: "" })}
                className={inputClass}
              >
                <option value="">{t("— none —")}</option>
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
              t("Subcategory"),
              <select
                value={form.sub_category_id}
                onChange={(e) => update({ sub_category_id: e.target.value })}
                className={inputClass}
                disabled={subCategories.length === 0}
              >
                <option value="">{subCategories.length ? t("— general —") : t("— no subcategories —")}</option>
                {subCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>,
            )}

          {field(
            t("Repeats"),
            <div className="flex items-center gap-1.5">
              <span className="shrink-0 text-sm text-on-surface-variant">{t("every")}</span>
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
                <option value="weekly">{t("week(s)")}</option>
                <option value="monthly">{t("month(s)")}</option>
                <option value="yearly">{t("year(s)")}</option>
              </select>
            </div>,
          )}
          {field(
            t("Starts on"),
            <input type="date" required value={form.start_date} onChange={(e) => update({ start_date: e.target.value })} className={inputClass} />,
          )}
          {field(
            t("Ends on (optional)"),
            <input type="date" value={form.end_date} onChange={(e) => update({ end_date: e.target.value })} className={inputClass} />,
          )}

          {isTransfer && depreciableAssets.length > 0 && (
            <div className="col-span-2 flex flex-col gap-2">
              <InfoHeading
                label={t("Depreciates")}
                title={<span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{t("Depreciates")}</span>}
              >{t("For a transfer into a depreciation fund: how much of it is an asset losing value. When it books, that asset's value drops by this amount, so the fund and the car's value move together.")}</InfoHeading>
              {form.depreciations.map((d, i) => (
                <div key={i} className="flex items-center gap-2">
                  <select
                    aria-label={t("Asset")}
                    value={d.account_id}
                    onChange={(e) => setDepreciation(i, { account_id: e.target.value })}
                    className={`${inputClass} min-w-0 flex-1`}
                  >
                    <option value="">{t("— asset —")}</option>
                    {depreciableAssets.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                  <input
                    aria-label={t("Amount")}
                    inputMode="decimal"
                    placeholder={t("€ per transfer")}
                    value={d.amount}
                    onChange={(e) => setDepreciation(i, { amount: e.target.value })}
                    className={`${inputClass} w-28`}
                  />
                  <button
                    type="button"
                    aria-label={t("Remove")}
                    onClick={() => update({ depreciations: form.depreciations.filter((_, j) => j !== i) })}
                    className="shrink-0 px-1 text-on-surface-variant hover:text-error"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => update({ depreciations: [...form.depreciations, { account_id: "", amount: "" }] })}
                className="self-start text-sm font-medium text-primary hover:underline"
              >{t("+ Add asset")}</button>
            </div>
          )}

          <div className="col-span-2">
            {field(t("Notes"), <input value={form.notes} onChange={(e) => update({ notes: e.target.value })} className={inputClass} />)}
          </div>

          <div className="col-span-2 mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-full border border-outline px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10"
            >{t("Cancel")}</button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:opacity-90 disabled:opacity-50"
            >
              {isSubmitting ? t("Saving…") : t("Save")}
            </button>
          </div>
        </form>
    </ModalOverlay>
  );
}
