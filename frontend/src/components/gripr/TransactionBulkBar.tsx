import { useMemo, useState } from "react";

import type { GriprAccount, GriprCategory } from "../../api/griprTypes";
import { t } from "../../i18n";

const selectClass =
  "min-w-0 rounded-lg border border-outline bg-surface px-2.5 py-1.5 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary";
const actionClass =
  "shrink-0 rounded-full border border-outline px-3 py-1.5 text-sm font-medium text-on-surface hover:bg-on-surface/10 disabled:opacity-40";

/** What to do with the selected transactions: file them under a (sub)category, move them to
 * another account, or delete them. Each action applies to the whole selection; the page says
 * afterwards how many it changed and how many it had to skip. */
export default function TransactionBulkBar({
  count,
  categories,
  accounts,
  busy,
  onSetCategory,
  onSetAccount,
  onDelete,
  onClear,
}: {
  count: number;
  categories: GriprCategory[];
  accounts: GriprAccount[];
  busy: boolean;
  onSetCategory: (categoryId: number) => void;
  onSetAccount: (accountId: number) => void;
  onDelete: () => void;
  onClear: () => void;
}) {
  const [categoryId, setCategoryId] = useState("");
  const [accountId, setAccountId] = useState("");

  // Each top-level category followed by its subcategories, grouped by kind -- the same tree the
  // transaction form offers, flattened into one native select.
  const groups = useMemo(() => {
    const active = categories.filter((c) => !c.is_archived);
    const byName = (a: GriprCategory, b: GriprCategory) => a.name.localeCompare(b.name);
    return (["expense", "income"] as const).map((kind) => ({
      kind,
      options: active
        .filter((c) => c.kind === kind && c.parent_id === null)
        .sort(byName)
        .flatMap((top) => [
          { id: top.id, label: top.name },
          ...active
            .filter((c) => c.parent_id === top.id)
            .sort(byName)
            .map((sub) => ({ id: sub.id, label: `${top.name} › ${sub.name}` })),
        ]),
    }));
  }, [categories]);

  return (
    <div className="sticky bottom-20 z-10 flex flex-wrap items-center gap-2 rounded-2xl border border-outline-variant bg-surface-container-high px-3 py-2.5 shadow-md sm:bottom-4">
      <span className="mr-1 text-sm font-medium text-on-surface">{t("{count} selected", { count })}</span>
      <span className="flex min-w-0 items-center gap-1.5">
        <select aria-label={t("Category for the selection")} value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className={selectClass}>
          <option value="">{t("Category…")}</option>
          {groups.map((g) => (
            <optgroup key={g.kind} label={g.kind === "expense" ? t("Expense") : t("Income")}>
              {g.options.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <button type="button" disabled={busy || !categoryId} onClick={() => onSetCategory(Number(categoryId))} className={actionClass}>{t("File")}</button>
      </span>
      <span className="flex min-w-0 items-center gap-1.5">
        <select aria-label={t("Account for the selection")} value={accountId} onChange={(e) => setAccountId(e.target.value)} className={selectClass}>
          <option value="">{t("Account…")}</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <button type="button" disabled={busy || !accountId} onClick={() => onSetAccount(Number(accountId))} className={actionClass}>{t("Move")}</button>
      </span>
      <button type="button" disabled={busy} onClick={onDelete} className={`${actionClass} text-error`}>{t("Delete")}</button>
      <button type="button" onClick={onClear} className="ml-auto shrink-0 text-sm text-on-surface-variant hover:text-on-surface">{t("Clear")}</button>
    </div>
  );
}
