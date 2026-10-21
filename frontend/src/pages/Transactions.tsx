import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";
import type { Transaction, TransactionInput, TransactionType } from "../api/types";
import AttachmentBadge from "../components/AttachmentBadge";
import TransactionFilters, { EMPTY_FILTERS, type TransactionFilterState } from "../components/TransactionFilters";
import GainrTopRow from "../components/GainrTopRow";
import MobileFab from "../components/MobileFab";
import TransactionForm from "../components/TransactionForm";
import TransactionSheet from "../components/TransactionSheet";
import { PageTitle, primaryButtonClass, secondaryButtonClass } from "../components/ui/kit";
import { QueryError } from "../components/ui/QueryError";
import { positionPath } from "../config/modules";
import { usePortfolio } from "../hooks/usePortfolio";
import { warnFailedAttachments } from "../utils/attachments";
import { formatCurrency, formatDate, formatEur, formatQuantity } from "../utils/format";
import { countSummary, groupByMonth } from "../utils/groupByMonth";
import { msg, t as tr, tp } from "../i18n";

const LOAD_ERROR = msg("Couldn't load transactions.");

const PAGE_SIZE = 50;

type SortField = "date" | "type" | "total_eur";

// A letter tile per type on the phone list, tinted by what it does to the portfolio.
const TYPE_TILE: Partial<Record<TransactionType, { letter: string; className: string }>> = {
  Buy: { letter: "B", className: "bg-ui-brand-soft text-ui-brand-strong" },
  Sell: { letter: "S", className: "bg-ui-late-soft text-ui-late" },
  Dividend: { letter: "D", className: "bg-emerald-50 text-emerald-700" },
  Interest: { letter: "I", className: "bg-emerald-50 text-emerald-700" },
  Staking: { letter: "S", className: "bg-emerald-50 text-emerald-700" },
};

// "2 buys" -- each type's count, in words.
const TYPE_COUNTS: Record<TransactionType, [string, string]> = {
  Buy: [msg("{n} buy"), msg("{n} buys")],
  Sell: [msg("{n} sell"), msg("{n} sells")],
  Dividend: [msg("{n} dividend"), msg("{n} dividends")],
  Interest: [msg("{n} interest payment"), msg("{n} interest payments")],
  Deposit: [msg("{n} deposit"), msg("{n} deposits")],
  Withdraw: [msg("{n} withdrawal"), msg("{n} withdrawals")],
  "Broker Fee": [msg("{n} fee"), msg("{n} fees")],
  Staking: [msg("{n} staking reward"), msg("{n} staking rewards")],
  Transfer: [msg("{n} transfer"), msg("{n} transfers")],
};

function typeCount(type: TransactionType, n: number): string {
  const [one, many] = TYPE_COUNTS[type];
  return tp(n, one, many);
}

export default function Transactions() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { portfolioId } = usePortfolio();
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState<SortField>("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  // The form: null = closed, undefined = adding (from scratch, or from `template`), a
  // transaction = editing it.
  const [editing, setEditing] = useState<Transaction | undefined | null>(null);
  const [template, setTemplate] = useState<Transaction | undefined>(undefined);
  const [opened, setOpened] = useState<Transaction | null>(null);
  const [filters, setFilters] = useState<TransactionFilterState>(EMPTY_FILTERS);

  const assetsQuery = useQuery({ queryKey: ["assets"], queryFn: api.listAssets });
  const brokersQuery = useQuery({
    queryKey: ["transactions", "brokers", portfolioId],
    queryFn: () => api.listBrokers(portfolioId!),
    enabled: portfolioId !== null,
  });
  const transactionsQuery = useQuery({
    queryKey: ["transactions", portfolioId, page, sortBy, sortDir, filters],
    queryFn: () =>
      api.listTransactions({
        portfolioId: portfolioId!,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        sortBy,
        sortDir,
        type: filters.type || undefined,
        assetName: filters.assetName || undefined,
        broker: filters.broker || undefined,
        dateFrom: filters.dateFrom || undefined,
        dateTo: filters.dateTo || undefined,
      }),
    enabled: portfolioId !== null,
  });

  const applyFilters = (next: TransactionFilterState) => {
    setFilters(next);
    setPage(0);
  };

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["transactions"] });
    queryClient.invalidateQueries({ queryKey: ["summary"] });
    queryClient.invalidateQueries({ queryKey: ["positions"] });
    queryClient.invalidateQueries({ queryKey: ["performance"] });
  };

  const closeForm = () => {
    setEditing(null);
    setTemplate(undefined);
  };
  const startAdding = () => {
    setTemplate(undefined);
    setEditing(undefined);
  };

  const createMutation = useMutation({
    mutationFn: ({ input, files }: { input: TransactionInput; files: File[] }) =>
      api.createTransactionWithAttachments(input, files),
    onSuccess: ({ failed }) => {
      invalidateAll();
      closeForm();
      warnFailedAttachments(failed);
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: TransactionInput }) => api.updateTransaction(id, input),
    onSuccess: () => {
      invalidateAll();
      closeForm();
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteTransaction(id),
    onSuccess: () => invalidateAll(),
  });

  const toggleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
    setPage(0);
  };

  const items = transactionsQuery.data?.items ?? [];
  const total = transactionsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  // Months only make sense in date order; sorted by amount or type the list is one run.
  const groups =
    sortBy === "date" ? groupByMonth(items, (t) => t.date) : [{ key: "all", label: "", items }];
  const csvHref = `/api/transactions/export.csv?portfolio_id=${portfolioId}`;

  const sortIndicator = (field: SortField) => (sortBy === field ? (sortDir === "asc" ? " ▲" : " ▼") : "");
  const listState = transactionsQuery.isLoading ? (
    <div className="px-4 py-6 text-center text-ui-muted">{tr("Loading…")}</div>
  ) : transactionsQuery.isError ? (
    <QueryError className="px-4 py-6 text-center" message={tr(LOAD_ERROR)}
 onRetry={() => transactionsQuery.refetch()} />
  ) : items.length === 0 ? (
    <div className="px-4 py-6 text-center text-ui-muted">
      {Object.values(filters).some(Boolean) ? tr("Nothing matches these filters.") : tr("No transactions yet. Add your first one with the button below.")}
    </div>
  ) : null;

  return (
    <div className="flex flex-col gap-4">
      <GainrTopRow>
        <a href={csvHref} download className={`${secondaryButtonClass} hidden no-underline sm:inline-flex`}>{tr("Export CSV")}</a>
        <button onClick={startAdding} className={`${primaryButtonClass} hidden h-11 sm:inline-flex`}>{tr("Add transaction")}</button>
      </GainrTopRow>
      <PageTitle>{tr("Transactions")}</PageTitle>

      <TransactionFilters filters={filters} onChange={applyFilters} brokers={brokersQuery.data ?? []} />

      {/* Tablet and up: a table, sortable by its headers. A row opens the transaction's sheet,
          where Edit, Duplicate and Delete live -- no icons on every row. */}
      <div className="hidden overflow-hidden rounded-2xl border border-ui-border bg-ui-surface sm:block">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ui-line/60 text-left text-xs uppercase tracking-wide text-ui-muted">
                <th className="cursor-pointer select-none px-4 py-2.5 font-semibold" onClick={() => toggleSort("date")}>{tr("Date")}{sortIndicator("date")}
                </th>
                <th className="cursor-pointer select-none px-4 py-2.5 font-semibold" onClick={() => toggleSort("type")}>{tr("Type")}{sortIndicator("type")}
                </th>
                <th className="px-4 py-2.5 font-semibold">{tr("Asset")}</th>
                <th className="px-4 py-2.5 text-right font-semibold">{tr("Quantity")}</th>
                <th className="px-4 py-2.5 text-right font-semibold">{tr("Price")}</th>
                <th className="cursor-pointer select-none px-4 py-2.5 text-right font-semibold" onClick={() => toggleSort("total_eur")}>{tr("Total (EUR)")}{sortIndicator("total_eur")}
                </th>
                <th className="px-4 py-2.5 font-semibold">{tr("Broker")}</th>
              </tr>
            </thead>
            <tbody>
              {listState ? (
                <tr>
                  <td colSpan={7}>{listState}</td>
                </tr>
              ) : (
                items.map((t) => (
                  <tr key={t.id} onClick={() => setOpened(t)} className="cursor-pointer border-b border-ui-line/40 last:border-0 hover:bg-ui-tile/60">
                    <td className="whitespace-nowrap px-4 py-2.5">{formatDate(t.date)}</td>
                    <td className="px-4 py-2.5">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpened(t);
                        }}
                        className="text-left font-semibold text-ui-ink hover:underline"
                      >
                        {tr(t.type)}
                      </button>
                      <AttachmentBadge count={t.attachment_count} />
                    </td>
                    <td className="px-4 py-2.5">{t.asset_name ?? "—"}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{formatQuantity(t.quantity)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{t.price ? formatCurrency(t.price, t.native_currency) : "—"}</td>
                    <td className="px-4 py-2.5 text-right font-semibold tabular-nums">{formatEur(t.total_eur)}</td>
                    <td className="px-4 py-2.5 text-ui-muted">{t.broker ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* A phone: the month's transactions under its name and what happened in it. */}
      <div className="flex flex-col gap-4 sm:hidden">
        {listState ? (
          <div className="rounded-2xl border border-ui-border bg-ui-surface">{listState}</div>
        ) : (
          groups.map((group) => (
            <section key={group.key} aria-label={group.label || tr("Transactions")} className="flex flex-col gap-1.5">
              {group.label && (
                <div className="flex items-baseline justify-between gap-3 px-1">
                  <h2 className="m-0 font-display text-[17px] font-bold">{group.label}</h2>
                  <span className="truncate text-[13px] text-ui-muted">{countSummary(group.items, (t) => t.type, typeCount)}</span>
                </div>
              )}
              <ul className="m-0 list-none overflow-hidden rounded-2xl border border-ui-border bg-ui-surface p-0">
                {group.items.map((t) => {
                  const tile = TYPE_TILE[t.type] ?? { letter: "€", className: "bg-ui-tile text-ui-ink-soft" };
                  const detail = [
                    formatDate(t.date, { day: "numeric", month: "short" }),
                    t.quantity && t.price ? `${formatQuantity(t.quantity)} × ${formatCurrency(t.price, t.native_currency)}`
 : t.broker,
                  ]
                    .filter(Boolean)
                    .join(" · ");
                  return (
                    <li key={t.id} className="border-t border-ui-line/50 first:border-0">
                      <button type="button" onClick={() => setOpened(t)} className="flex w-full items-center gap-3 px-3.5 py-3 text-left hover:bg-ui-tile/60">
                        <span aria-hidden className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] text-[13px] font-bold ${tile.className}`}>
                          {tile.letter}
                        </span>
                        <span className="flex min-w-0 flex-1 flex-col">
                          <span className="truncate text-[15px] font-semibold text-ui-ink">
                            {t.asset_name ?? tr(t.type)}
                            <AttachmentBadge count={t.attachment_count} />
                          </span>
                          <span className="truncate text-[13px] text-ui-muted">
                            {t.asset_name ? `${tr(t.type)} · ` : ""}
                            {detail}
                          </span>
                        </span>
                        <span className="shrink-0 text-[15px] font-semibold tabular-nums text-ui-ink">{formatEur(t.total_eur)}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 px-1 text-sm text-ui-muted">
        <span>
          {total}{" "}{tr("transactions · page")}{" "}{page + 1}{" "}{tr("of {totalPages}", { totalPages: totalPages })}<a href={csvHref} download className="ml-3 font-semibold text-ui-brand-strong sm:hidden">{tr("Export CSV")}</a>
        </span>
        <div className="flex gap-2">
          <button disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))} className={`${secondaryButtonClass} h-10`}>{tr("Previous")}</button>
          <button disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)} className={`${secondaryButtonClass} h-10`}>{tr("Next")}</button>
        </div>
      </div>

      {opened && (
        <TransactionSheet
          transaction={opened}
          onClose={() => setOpened(null)}
          onEdit={() => {
            setTemplate(undefined);
            setEditing(opened);
            setOpened(null);
          }}
          onDuplicate={() => {
            setTemplate(opened);
            setEditing(undefined);
            setOpened(null);
          }}
          onDelete={() => {
            deleteMutation.mutate(opened.id);
            setOpened(null);
          }}
          onOpenPosition={opened.asset_id !== null ? () => navigate(positionPath(opened.asset_id!)) : undefined}
        />
      )}

      {editing !== null && portfolioId !== null && (
        <TransactionForm
          assets={assetsQuery.data ?? []}
          brokers={brokersQuery.data ?? []}
          initial={editing}
          template={template}
          portfolioId={portfolioId}
          isSubmitting={createMutation.isPending || updateMutation.isPending}
          onCancel={closeForm}
          onSubmit={(input, files) => {
            if (editing) {
              updateMutation.mutate({ id: editing.id, input });
            } else {
              createMutation.mutate({ input, files });
            }
          }}
        />
      )}

      <MobileFab label={tr("Add transaction")} onClick={startAdding} />
    </div>
  );
}
