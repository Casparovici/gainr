import { Archive, ArchiveRestore, Pencil, Trash2 } from "lucide-react";
import { createPortal } from "react-dom";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { griprApi } from "../../api/griprClient";
import {
  GRIPR_ACCOUNT_TYPES,
  type GriprAccount,
  type GriprAccountType,
  type GriprCategory,
  type GriprTransaction,
  type GriprTransactionInput,
} from "../../api/griprTypes";
import { usePortfolio } from "../../hooks/usePortfolio";
import { buildCategoryColorMap } from "../../utils/categoryColor";
import { warnFailedAttachments } from "../../utils/attachments";
import { decimalInputToApi, formatDate, formatEur, pnlColorClass, toNumber } from "../../utils/format";
import { GRIPR_TYPE_BADGE, griprSignedAmount, griprTypeLabel } from "../../utils/griprTransactionType";
import { ACCOUNT_TYPE_NAMES, resolveAccountColor } from "../../utils/accountColor";
import ColorPicker from "../ColorPicker";
import InfoHeading from "../ui/InfoTip";
import SyncButton from "../ui/SyncButton";
import { QueryError } from "../ui/QueryError";
import ModalOverlay from "../ModalOverlay";
import InlineEditText from "../InlineEditText";
import BankLogoPicker from "./BankLogoPicker";
import GriprButton from "./GriprButton";
import GriprTransactionForm from "./GriprTransactionForm";
import { useConfirmDialog } from "./useConfirmDialog";
import { t as tr, tp } from "../../i18n";

const PAGE_SIZE = 10;

const inputClass =
  "rounded-md border border-outline px-2.5 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

// Same manual/transactional split AccountForm uses when creating an account.
const MANUAL_TYPES: GriprAccountType[] = ["loan", "credit", "asset"];

export default function AccountDetailDialog({
  account,
  accounts,
  categories,
  onClose,
}: {
  account: GriprAccount;
  accounts: GriprAccount[];
  categories: GriprCategory[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const [type, setType] = useState<GriprAccountType>(account.type);
  const [reconciling, setReconciling] = useState(false);
  const [reconcileValue, setReconcileValue] = useState("");
  const [page, setPage] = useState(0);
  const [addingTransaction, setAddingTransaction] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<GriprTransaction | undefined>(undefined);
  // Set = the "add" form is a new refund for this expense ("Got money back").
  const [refundOf, setRefundOf] = useState<GriprTransaction | undefined>(undefined);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["gripr-accounts"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-transactions"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-receivables"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-account-transactions"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-budgets"] });
  };

  const updateAccountMutation = useMutation({
    mutationFn: (input: Partial<GriprAccount>) => griprApi.updateAccount(account.id, input),
    onSuccess: invalidate,
  });
  // A pot sits inside a real account, one level deep: never itself, never another pot, and an
  // account that already holds pots can't become one (the backend enforces the same).
  const holdsPots = accounts.some((a) => a.held_in_account_id === account.id);
  const potParents = holdsPots
    ? []
    : accounts.filter((a) => a.id !== account.id && a.held_in_account_id === null && !a.is_archived && a.balance_mode === "transactional");

  const { portfolios } = usePortfolio();
  const portfolioLinksQuery = useQuery({
    queryKey: ["gripr-portfolio-links"],
    queryFn: () => griprApi.listPortfolioLinks(),
  });
  const myLink = portfolioLinksQuery.data?.find((l) => l.account_id === account.id);
  // Portfolios already mirrored by a *different* account can't also be picked here -- each side
  // of the bridge is one-to-one (see docs/adr/0021).
  const linkedElsewhere = new Set(
    (portfolioLinksQuery.data ?? []).filter((l) => l.account_id !== account.id).map((l) => l.portfolio_id)
  );
  const selectablePortfolios = portfolios.filter((p) => !linkedElsewhere.has(p.id));

  const invalidateWithLinks = () => {
    invalidate();
    queryClient.invalidateQueries({ queryKey: ["gripr-portfolio-links"] });
  };

  const portfolioLinkMutation = useMutation({
    mutationFn: (portfolioId: number | null) => griprApi.updatePortfolioLink(account.id, portfolioId),
    onSuccess: invalidateWithLinks,
  });

  const portfolioSyncMutation = useMutation({
    mutationFn: () => griprApi.syncPortfolioLinks(),
    onSuccess: invalidateWithLinks,
  });

  const transactionsQuery = useQuery({
    queryKey: ["gripr-account-transactions", account.id, page],
    queryFn: () =>
      griprApi.listTransactions({
        accountId: account.id,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        sortBy: "date",
        sortDir: "desc",
      }),
  });

  const createTransactionMutation = useMutation({
    mutationFn: ({ input, files }: { input: GriprTransactionInput; files: File[] }) =>
      griprApi.createTransactionWithAttachments(input, files),
    onSuccess: ({ failed }) => {
      invalidate();
      setAddingTransaction(false);
      setRefundOf(undefined);
      warnFailedAttachments(failed);
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

  const categoryColors = useMemo(() => buildCategoryColorMap(categories), [categories]);

  const manual = MANUAL_TYPES.includes(type);
  const total = transactionsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const currentBalance = toNumber(account.balance) ?? 0;
  // An account holding virtual pots (Trade Republic holding Onderhoud Auto and Reservering
  // Vakantie) really has its own balance *plus* theirs at the bank -- that total is what its app
  // shows, so it's the headline here and what a correction is checked against. The Accounts list
  // keeps them apart, so net worth counts each euro once.
  const pots = accounts.filter((a) => a.held_in_account_id === account.id);
  const atBank = currentBalance + pots.reduce((sum, p) => sum + (toNumber(p.balance) ?? 0), 0);
  const enteredBalance = reconcileValue ? toNumber(decimalInputToApi(reconcileValue) ?? "") : null;
  // The difference lands on this account's own, unallocated part: the pots hold what was set aside.
  const delta = enteredBalance !== null ? enteredBalance - atBank : null;

  const typeChanged = type !== account.type;

  // Portaled out of App's `.module-gripr` root, so the colour variables (and the page kit's
  // font) have to be re-scoped here or every `bg-surface`/`text-on-surface` resolves to nothing.
  return createPortal(
    <div className="module-gripr contents">
      <ModalOverlay onClose={onClose} cardClassName="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-[28px] bg-surface shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-outline-variant p-5">
          <div className="flex min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:items-end">
            {/* Logo and colour live here rather than on the Accounts page's rows, which stay
                quiet: they're set once, not checked daily. */}
            <div className="flex shrink-0 items-center gap-2">
              <BankLogoPicker
                value={account.bank_logo_key}
                onSelect={(bank_logo_key) => updateAccountMutation.mutate({ bank_logo_key })}
                size={36}
              />
              <ColorPicker
                value={account.color}
                onSelect={(color) => updateAccountMutation.mutate({ color })}
                trigger={
                  <span
                    className="block h-5 w-5 rounded-full ring-1 ring-outline-variant"
                    style={{ backgroundColor: resolveAccountColor(account) }}
                    title={tr("Account colour")}
                  />
                }
              />
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
              <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{tr("Name")}</span>
              <InlineEditText
                value={account.name}
                onSave={(name) => updateAccountMutation.mutate({ name })}
                title={tr("Edit name")}
                textClassName="truncate text-base font-medium text-on-surface"
              />
            </div>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{tr("Type")}</span>
              <select value={type} onChange={(e) => setType(e.target.value as GriprAccountType)} className={inputClass}>
                {GRIPR_ACCOUNT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {tr(ACCOUNT_TYPE_NAMES[t])}
                  </option>
                ))}
              </select>
            </label>
            {typeChanged && (
              <GriprButton onClick={() => updateAccountMutation.mutate({ type })} disabled={updateAccountMutation.isPending}>
                {updateAccountMutation.isPending ? tr("Saving…") : tr("Save")}
              </GriprButton>
            )}
          </div>
          <button onClick={onClose} className="shrink-0 text-on-surface-variant hover:text-on-surface">
            ✕
          </button>
        </div>

        <div className="overflow-y-auto p-5">
          <div className="rounded-2xl border border-outline-variant p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
                {manual
                  ? tr("Balance")
                  : pots.length > 0
                    ? tr("At {name}, pots included", { name: account.name })
                    : tr("Balance (from transactions)")}
              </span>
              {!manual && !reconciling && (
                <button
                  onClick={() => {
                    setReconcileValue("");
                    setReconciling(true);
                  }}
                  className="text-xs font-medium text-on-surface-variant hover:text-on-surface"
                >{tr("Correct balance")}</button>
              )}
            </div>

            {manual ? (
              <div className="mt-1 flex items-center gap-2">
                <input
                  inputMode="decimal"
                  defaultValue={String(toNumber(account.manual_balance) ?? 0).replace(".", ",")}
                  onBlur={(e) => {
                    const value = decimalInputToApi(e.target.value);
                    if (value !== null) updateAccountMutation.mutate({ manual_balance: value });
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") e.currentTarget.blur();
                  }}
                  className={`w-32 text-lg font-semibold tabular-nums ${inputClass}`}
                />
              </div>
            ) : pots.length > 0 ? (
              <>
                <div className={`mt-1 text-2xl font-semibold tabular-nums ${pnlColorClass(atBank)}`}>{formatEur(atBank)}</div>
                <ul aria-label={tr("Balance breakdown")} className="mt-2 flex flex-col gap-0.5 text-sm">
                  <li className="flex justify-between gap-3">
                    <span className="text-on-surface">{tr("Unallocated")}</span>
                    <span className={`tabular-nums ${pnlColorClass(account.balance)}`}>{formatEur(account.balance)}</span>
                  </li>
                  {pots.map((p) => (
                    <li key={p.id} className="flex justify-between gap-3">
                      <span className="text-on-surface-variant">{p.name}</span>
                      <span className={`tabular-nums ${pnlColorClass(p.balance)}`}>{formatEur(p.balance)}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <div className={`mt-1 text-2xl font-semibold tabular-nums ${pnlColorClass(account.balance)}`}>
                {formatEur(account.balance)}
              </div>
            )}

            <div className="mt-3 border-t border-outline-variant pt-3">
              {holdsPots ? (
                <p className="text-sm text-on-surface-variant">{tr("This account holds pots (see the breakdown above), so it can't be a pot inside another account itself.")}</p>
              ) : (
              <div className="flex flex-col gap-1 text-sm">
                <InfoHeading
                  label={tr("Virtual pot inside")}
                  title={<label htmlFor="account-held-in" className="text-on-surface">{tr("Virtual pot inside")}</label>}
                >{tr("For money set aside on paper that really sits in another account. The bank sync then counts spending from this pot as that account's own, and never mistakes money moved into the pot for a real payment.")}</InfoHeading>
                <select
                  id="account-held-in"
                  value={account.held_in_account_id ?? ""}
                  disabled={updateAccountMutation.isPending}
                  onChange={(e) => updateAccountMutation.mutate({ held_in_account_id: e.target.value === "" ? null : Number(e.target.value) })}
                  className={inputClass}
                >
                  <option value="">{tr("No — a real account")}</option>
                  {potParents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>
              )}
            </div>

            <div className="mt-3 border-t border-outline-variant pt-3">
              <div className="flex flex-col gap-1 text-sm">
                <InfoHeading
                  label={tr("Track a gainr portfolio")}
                  title={<label htmlFor="account-portfolio-link" className="text-on-surface">{tr("Track a gainr portfolio")}</label>}
                >{tr("This account's balance becomes that portfolio's total value, and transfers in or out of it book a matching deposit or withdrawal in its cash. Gains and losses only move the balance — they're never booked as transactions.")}</InfoHeading>
                <select
                  id="account-portfolio-link"
                  value={myLink?.portfolio_id ?? ""}
                  disabled={portfolioLinkMutation.isPending || portfolioLinksQuery.isLoading}
                  onChange={(e) => portfolioLinkMutation.mutate(e.target.value === "" ? null : Number(e.target.value))}
                  className={inputClass}
                >
                  <option value="">{tr("Not linked")}</option>
                  {selectablePortfolios.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              {myLink && (
                <div className="mt-2 flex items-center gap-2 text-xs text-on-surface-variant">
                  <SyncButton pending={portfolioSyncMutation.isPending} onClick={() => portfolioSyncMutation.mutate()} />
                  <span>{tr("Otherwise updates once a day, after prices refresh.")}</span>
                </div>
              )}
            </div>

            {reconciling && (
              <div className="mt-3 flex flex-col gap-2 border-t border-outline-variant pt-3">
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
                    {pots.length > 0
                      ? tr("Real balance (the total in your {name} app)", { name: account.name })
                      : tr("Real balance (from your bank)")}
                  </span>
                  <input
                    autoFocus
                    inputMode="decimal"
                    value={reconcileValue}
                    onChange={(e) => setReconcileValue(e.target.value)}
                    className={inputClass}
                  />
                </label>
                {delta !== null && delta !== 0 && (
                  <>
                    <p className="text-sm text-on-surface-variant">{tr("Difference:")}{" "}<span className={pnlColorClass(delta)}>{formatEur(delta)}</span>{" "}{tr("— is this a transaction we're missing, or just drift to correct?")}</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setReconciling(false);
                          setAddingTransaction(true);
                        }}
                        className="rounded-md border border-outline px-3 py-1.5 text-sm font-medium text-on-surface hover:bg-on-surface/5"
                      >{tr("Add a transaction")}</button>
                      <GriprButton
                        onClick={() => {
                          const newOpening = (toNumber(account.opening_balance) ?? 0) + delta;
                          updateAccountMutation.mutate({ opening_balance: newOpening.toFixed(2) });
                          setReconciling(false);
                        }}
                      >{tr("Just correct it")}</GriprButton>
                    </div>
                  </>
                )}
                <button
                  onClick={() => setReconciling(false)}
                  className="self-start text-xs text-on-surface-variant hover:text-on-surface"
                >{tr("Cancel")}</button>
              </div>
            )}
          </div>

          <div className="mt-5 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-on-surface">{tr("Transactions")}</h3>
            <button
              onClick={() => setAddingTransaction(true)}
              className="rounded-md border border-outline px-2.5 py-1 text-xs font-medium text-on-surface hover:bg-on-surface/5"
            >{tr("+ Add transaction")}</button>
          </div>

          <div className="mt-2 overflow-hidden rounded-2xl border border-outline-variant">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-outline-variant text-left text-xs uppercase tracking-wide text-on-surface-variant">
                    <th className="px-3 py-2 font-medium">{tr("Date")}</th>
                    <th className="hidden px-3 py-2 font-medium sm:table-cell">{tr("Type")}</th>
                    <th className="hidden px-3 py-2 font-medium sm:table-cell">{tr("Category")}</th>
                    <th className="px-3 py-2 text-right font-medium">{tr("Amount")}</th>
                    <th className="px-3 py-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {transactionsQuery.isLoading ? (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center text-on-surface-variant">{tr("Loading…")}</td>
                    </tr>
                  ) : transactionsQuery.isError ? (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center">
                        <QueryError message={tr("Couldn't load this account's transactions.")} onRetry={() => transactionsQuery.refetch()} />
                      </td>
                    </tr>
                  ) : transactionsQuery.data?.items.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center text-on-surface-variant">{tr("No transactions")}</td>
                    </tr>
                  ) : (
                    transactionsQuery.data?.items.map((t) => (
                      <tr
                        key={t.id}
                        onClick={() => setEditingTransaction(t)}
                        className="cursor-pointer border-b border-outline-variant last:border-0 hover:bg-on-surface/5"
                      >
                        <td className="px-3 py-2 text-on-surface-variant">
                          <div className="whitespace-nowrap">{formatDate(t.date)}</div>
                          {/* On a phone there's no room for separate Type/Category columns next to
                              the amount -- what they'd say folds into one line here instead. */}
                          <div className="flex max-w-[11rem] items-center gap-1.5 truncate text-xs sm:hidden">
                            {t.category_name ? (
                              <>
                                <span
                                  className="h-2 w-2 shrink-0 rounded-full"
                                  style={{ backgroundColor: categoryColors.get(t.category_id ?? -1) ?? "#94a3b8" }}
                                />
                                <span className="truncate">{t.category_name}</span>
                              </>
                            ) : t.counter_account_name ? (
                              <span className="truncate">
                                {t.account_id === account.id ? `→ ${t.counter_account_name}` : `← ${t.account_name}`}
                              </span>
                            ) : (
                              <span>{griprTypeLabel(t.type)}</span>
                            )}
                          </div>
                        </td>
                        <td className="hidden px-3 py-2 sm:table-cell">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${GRIPR_TYPE_BADGE[t.type]}`}>
                            {griprTypeLabel(t.type)}
                          </span>
                          {t.counter_account_name && (
                            <span className="ml-1 text-xs text-on-surface-variant">
                              {t.account_id === account.id ? `→ ${t.counter_account_name}` : `← ${t.account_name}`}
                            </span>
                          )}
                        </td>
                        <td className="hidden px-3 py-2 text-on-surface-variant sm:table-cell">
                          {t.category_name ? (
                            <span className="flex items-center gap-1.5">
                              <span
                                className="h-2 w-2 shrink-0 rounded-full"
                                style={{ backgroundColor: categoryColors.get(t.category_id ?? -1) ?? "#94a3b8" }}
                              />
                              {t.category_name}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td
                          className={`whitespace-nowrap px-3 py-2 text-right tabular-nums font-medium ${
                            t.type === "transfer" ? "text-on-surface-variant" : pnlColorClass(griprSignedAmount(t))
                          }`}
                        >
                          {t.type === "transfer" ? formatEur(t.amount) : formatEur(griprSignedAmount(t))}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingTransaction(t);
                            }}
                            className="hidden text-on-surface-variant hover:text-on-surface sm:inline"
                            title={tr("Edit")}
                            aria-label={tr("Edit")}
                          >
                            <Pencil className="h-4 w-4" strokeWidth={2} />
                          </button>
                          <button
                            onClick={async (e) => {
                              e.stopPropagation();
                              const ok = await confirm({
                                title: tr("Delete transaction?"),
                                description: tr("This {type} transaction from {date} will be permanently removed.", {
                                  type: griprTypeLabel(t.type).toLowerCase(),
                                  date: formatDate(t.date),
                                }),
                              });
                              if (ok) deleteTransactionMutation.mutate(t.id);
                            }}
                            className="text-error hover:opacity-80 sm:ml-3"
                            title={tr("Delete")}
                            aria-label={tr("Delete")}
                          >
                            <Trash2 className="h-4 w-4" strokeWidth={2} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-outline-variant px-3 py-2 text-xs text-on-surface-variant">
              <span>
                {tp(total, "{n} transaction — page {page} of {totalPages}", "{n} transactions — page {page} of {totalPages}", { page: page + 1, totalPages })}</span>
              <div className="flex gap-2">
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  className="rounded-md border border-outline px-2 py-0.5 disabled:opacity-40"
                >{tr("Prev")}</button>
                <button
                  disabled={page + 1 >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-outline px-2 py-0.5 disabled:opacity-40"
                >{tr("Next")}</button>
              </div>
            </div>
          </div>

          <div className="mt-5 flex items-center justify-between gap-3 border-t border-outline-variant pt-4">
            <span className="text-xs text-on-surface-variant">
              {account.is_archived
                ? tr("Archived: hidden from Accounts unless “Show archived” is on.")
                : tr("Archiving hides it from Accounts and pickers; its transactions and history stay.")}
            </span>
            <button
              type="button"
              onClick={() => updateAccountMutation.mutate({ is_archived: !account.is_archived })}
              disabled={updateAccountMutation.isPending}
              className="flex shrink-0 items-center gap-1.5 rounded-full border border-outline px-3 py-1.5 text-sm font-medium text-on-surface hover:bg-surface-container disabled:opacity-50"
            >
              {account.is_archived ? <ArchiveRestore className="h-4 w-4" strokeWidth={2} /> : <Archive className="h-4 w-4" strokeWidth={2} />}
              {account.is_archived ? tr("Unarchive") : tr("Archive")}
            </button>
          </div>
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
          defaultAccountId={account.id}
          isSubmitting={createTransactionMutation.isPending || updateTransactionMutation.isPending}
          onCancel={() => {
            setAddingTransaction(false);
            setEditingTransaction(undefined);
            setRefundOf(undefined);
          }}
          onSubmit={(input, files) => {
            if (editingTransaction) {
              updateTransactionMutation.mutate({ id: editingTransaction.id, input });
            } else {
              createTransactionMutation.mutate({ input, files });
            }
          }}
        />
      )}

      {confirmDialog}
    </div>,
    document.body,
  );
}
