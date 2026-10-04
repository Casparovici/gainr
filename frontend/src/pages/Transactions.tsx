import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import type { Transaction, TransactionInput } from "../api/types";
import TransactionFilters, { EMPTY_FILTERS, type TransactionFilterState } from "../components/TransactionFilters";
import GainrTopRow from "../components/GainrTopRow";
import MobileFab from "../components/MobileFab";
import TransactionForm from "../components/TransactionForm";
import Trading212Sync from "../components/Trading212Sync";
import { PageTitle, primaryButtonClass, secondaryButtonClass } from "../components/ui/kit";
import { usePortfolio } from "../hooks/usePortfolio";
import { formatCurrency, formatDate, formatEur, formatQuantity } from "../utils/format";

const PAGE_SIZE = 50;

type SortField = "date" | "type" | "total_eur";

export default function Transactions() {
  const queryClient = useQueryClient();
  const { portfolioId, portfolios } = usePortfolio();
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState<SortField>("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [editing, setEditing] = useState<Transaction | undefined | null>(null); // null = closed, undefined = creating
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

  const createMutation = useMutation({
    mutationFn: (input: TransactionInput) => api.createTransaction(input),
    onSuccess: () => {
      invalidateAll();
      setEditing(null);
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: TransactionInput }) => api.updateTransaction(id, input),
    onSuccess: () => {
      invalidateAll();
      setEditing(null);
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

  const total = transactionsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const sortIndicator = (field: SortField) => (sortBy === field ? (sortDir === "asc" ? " ▲" : " ▼") : "");

  return (
    <div className="flex flex-col gap-4">
      <GainrTopRow>
        <a
          href={`/api/transactions/export.csv?portfolio_id=${portfolioId}`}
          download
          className={`${secondaryButtonClass} no-underline`}
          aria-label="Export CSV"
        >
          <span className="sm:hidden">CSV</span>
          <span className="hidden sm:inline">Export CSV</span>
        </a>
        <button onClick={() => setEditing(undefined)} className={`${primaryButtonClass} hidden h-11 sm:inline-flex`}>
          Add transaction
        </button>
      </GainrTopRow>
      <PageTitle>Transactions</PageTitle>
      {portfolioId !== null && (
        <Trading212Sync portfolioId={portfolioId} portfolioName={portfolios.find((p) => p.id === portfolioId)?.name ?? "this portfolio"} />
      )}

      <TransactionFilters filters={filters} onChange={applyFilters} brokers={brokersQuery.data ?? []} />

      <div className="rounded-lg border border-slate-200 bg-white">
        {/* Tablet and up: a table. Below that, no column arrangement fits eight columns without
            side-to-side scrolling, so every field stacks into a card instead — nothing hidden,
            just reflowed. */}
        <div className="hidden overflow-x-auto sm:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="cursor-pointer select-none px-4 py-2 font-medium" onClick={() => toggleSort("date")}>
                  Date{sortIndicator("date")}
                </th>
                <th className="cursor-pointer select-none px-4 py-2 font-medium" onClick={() => toggleSort("type")}>
                  Type{sortIndicator("type")}
                </th>
                <th className="px-4 py-2 font-medium">Asset</th>
                <th className="px-4 py-2 font-medium text-right">Quantity</th>
                <th className="px-4 py-2 font-medium text-right">Price</th>
                <th className="cursor-pointer select-none px-4 py-2 font-medium text-right" onClick={() => toggleSort("total_eur")}>
                  Total (EUR){sortIndicator("total_eur")}
                </th>
                <th className="px-4 py-2 font-medium">Broker</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {transactionsQuery.isLoading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-6 text-center text-slate-400">
                    Loading…
                  </td>
                </tr>
              ) : transactionsQuery.data?.items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-6 text-center text-slate-400">
                    No transactions
                  </td>
                </tr>
              ) : (
                transactionsQuery.data?.items.map((t) => (
                  <tr
                    key={t.id}
                    onClick={() => setEditing(t)}
                    className="cursor-pointer border-b border-slate-50 last:border-0 hover:bg-slate-50"
                  >
                    <td className="px-4 py-2 whitespace-nowrap">{formatDate(t.date)}</td>
                    <td className="px-4 py-2">{t.type}</td>
                    <td className="px-4 py-2">{t.asset_name ?? "—"}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{formatQuantity(t.quantity)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{t.price ? formatCurrency(t.price, t.native_currency) : "—"}</td>
                    <td className="px-4 py-2 text-right tabular-nums font-medium">{formatEur(t.total_eur)}</td>
                    <td className="px-4 py-2 text-slate-500">{t.broker ?? "—"}</td>
                    <td className="whitespace-nowrap px-4 py-2 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditing(t);
                        }}
                        className="text-slate-500 hover:text-slate-900"
                        title="Edit"
                        aria-label="Edit"
                      >
                        <Pencil className="h-4 w-4" strokeWidth={2} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm(`Delete this ${t.type} transaction from ${t.date}?`)) deleteMutation.mutate(t.id);
                        }}
                        className="ml-3 text-red-500 hover:text-red-700"
                        title="Delete"
                        aria-label="Delete"
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

        <div className="divide-y divide-slate-100 sm:hidden">
          {transactionsQuery.isLoading ? (
            <div className="px-4 py-6 text-center text-slate-400">Loading…</div>
          ) : transactionsQuery.data?.items.length === 0 ? (
            <div className="px-4 py-6 text-center text-slate-400">No transactions</div>
          ) : (
            transactionsQuery.data?.items.map((t) => (
              <div
                key={t.id}
                onClick={() => setEditing(t)}
                className="flex cursor-pointer items-start justify-between gap-3 px-4 py-3 hover:bg-slate-50"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
                    <span className="font-medium text-slate-900">{t.type}</span>
                    <span className="text-slate-400">{formatDate(t.date)}</span>
                  </div>
                  <div className="mt-0.5 truncate text-sm text-slate-700">{t.asset_name ?? "—"}</div>
                  {(t.quantity || t.price || t.broker) && (
                    <div className="mt-0.5 truncate text-xs text-slate-400">
                      {t.quantity && formatQuantity(t.quantity)}
                      {t.quantity && t.price && " × "}
                      {t.price && formatCurrency(t.price, t.native_currency)}
                      {(t.quantity || t.price) && t.broker && " · "}
                      {t.broker}
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <span className="tabular-nums text-sm font-medium text-slate-900">{formatEur(t.total_eur)}</span>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditing(t);
                      }}
                      className="text-slate-500 hover:text-slate-900"
                      title="Edit"
                      aria-label="Edit"
                    >
                      <Pencil className="h-4 w-4" strokeWidth={2} />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Delete this ${t.type} transaction from ${t.date}?`)) deleteMutation.mutate(t.id);
                      }}
                      className="text-red-500 hover:text-red-700"
                      title="Delete"
                      aria-label="Delete"
                    >
                      <Trash2 className="h-4 w-4" strokeWidth={2} />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-sm text-slate-500">
          <span>
            {total} transactions — page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="rounded-md border border-slate-300 px-2.5 py-1 disabled:opacity-40"
            >
              Prev
            </button>
            <button
              disabled={page + 1 >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-md border border-slate-300 px-2.5 py-1 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {editing !== null && portfolioId !== null && (
        <TransactionForm
          assets={assetsQuery.data ?? []}
          brokers={brokersQuery.data ?? []}
          initial={editing}
          portfolioId={portfolioId}
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

      <MobileFab label="Add transaction" onClick={() => setEditing(undefined)} />
    </div>
  );
}
