import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import AssetLogo from "./AssetLogo";
import CollapsibleCard from "./CollapsibleCard";
import LabelPicker, { LabelChips } from "./LabelPicker";
import NewsSourcesEditor from "./NewsSourcesEditor";
import NoteBody from "./NoteBody";
import PositionCalendarSection, { NextEventLine } from "./PositionCalendar";
import TargetWeightInput from "./TargetWeightInput";
import TransactionForm from "./TransactionForm";
import { api } from "../api/client";
import { usePortfolio } from "../hooks/usePortfolio";
import type {
  AssetFinancials,
  DltJudgment,
  FinancialPeriod,
  KeyMetrics,
  Position,
  PositionNote,
  PositionNoteInput,
  Transaction,
  TransactionInput,
} from "../api/types";
import {
  formatCompactCurrency,
  formatCurrency,
  formatDate,
  formatEur,
  formatPct,
  formatQuantity,
  formatRatio,
  formatRelativeTime,
  formatWeight,
  pnlColorClass,
  toNumber,
} from "../utils/format";

type Tab = "overview" | "financials" | "transactions" | "notes" | "calendar";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "financials", label: "Financials" },
  { id: "transactions", label: "Transactions" },
  { id: "notes", label: "Notes" },
  { id: "calendar", label: "Calendar" },
];

// Enough to cover any single holding's history without paging inside a side panel.
const TRANSACTION_LIMIT = 200;

function Stat({ label, value, sub, subClass }: { label: string; value: string; sub?: string; subClass?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-0.5 truncate text-lg font-semibold tabular-nums text-slate-900" title={value}>
        {value}
      </div>
      {sub && <div className={`text-xs tabular-nums ${subClass ?? "text-slate-500"}`}>{sub}</div>}
    </div>
  );
}

function Placeholder({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-400">{children}</div>;
}

// Same badge colours PositionsTable's DLT column uses, as text rather than a filled pill --
// this is an editable control, not a read-only label.
const DLT_TEXT_COLOR: Record<DltJudgment, string> = {
  attractive: "text-emerald-700",
  neutral: "text-slate-600",
  critical: "text-red-700",
};

/** DLT's buy/hold/avoid call is normally refreshed by hand from a screenshot
 * (scripts/update_dlt_ratings.py) since there's no API -- this lets the same value be corrected
 * or cleared from the app itself. "No rating" (cleared back to null) is a real, distinct choice
 * from "Neutral": the two only look the same in the read-only badge elsewhere. */
function DltRatingInput({ assetId, value }: { assetId: number; value: DltJudgment | null }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (next: DltJudgment | null) => api.updateAsset(assetId, { dlt_judgment: next }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["positions"] }),
  });

  return (
    <select
      value={value ?? ""}
      onChange={(e) => mutation.mutate(e.target.value === "" ? null : (e.target.value as DltJudgment))}
      disabled={mutation.isPending}
      className={`rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-xs font-medium focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 disabled:opacity-50 ${
        value ? DLT_TEXT_COLOR[value] : "text-slate-400"
      }`}
    >
      <option value="">No rating</option>
      <option value="attractive">Attractive</option>
      <option value="neutral">Neutral</option>
      <option value="critical">Critical</option>
    </select>
  );
}

function NewsSection({ assetId, enabled }: { assetId: number; enabled: boolean }) {
  const query = useQuery({
    queryKey: ["asset-news", assetId],
    queryFn: () => api.getAssetNews(assetId),
    enabled,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="mt-6">
      <CollapsibleCard
        storageKey={`news-${assetId}`}
        title="News"
        meta={
          <span className="text-xs text-slate-400">
            past {query.data?.window_days ?? 7} days
            {query.data ? ` · ${query.data.items.length}` : ""}
          </span>
        }
      >
        {query.data && <NewsSourcesEditor assetId={assetId} sources={query.data.sources} />}
        <div className="space-y-3">
          {query.isLoading ? (
            <Placeholder>Loading news…</Placeholder>
          ) : query.isError ? (
            <Placeholder>Couldn't load news for this holding.</Placeholder>
          ) : !query.data || query.data.items.length === 0 ? (
            <Placeholder>
              {query.data?.sources.length
                ? "No stories in the past week."
                : "No stories in the past week. For a fund or commodity, add a market, sector or industry above."}
            </Placeholder>
          ) : (
            query.data.items.map((item) => (
              <article key={`${item.source ?? "own"}-${item.url}`} className="border-b border-slate-100 pb-3 last:border-0">
                <a
                  href={item.url}
                  target="_blank"
                  // noreferrer alongside noopener: these links point at pages this app doesn't
                  // control, and there's no reason to tell them where the click came from.
                  rel="noopener noreferrer"
                  className="text-sm font-medium leading-snug text-slate-900 hover:text-blue-700 hover:underline"
                >
                  {item.title}
                </a>
                <div className="mt-0.5 text-xs text-slate-400">
                  {item.source && (
                    <span className="mr-1.5 rounded bg-slate-100 px-1.5 py-px font-medium text-slate-600">{item.source}</span>
                  )}
                  {item.publisher}
                  {item.publisher && " · "}
                  {formatRelativeTime(item.published_at)}
                </div>
                {item.summary && <p className="mt-1 text-sm leading-relaxed text-slate-600">{item.summary}</p>}
              </article>
            ))
          )}
        </div>
      </CollapsibleCard>
    </div>
  );
}

function CashByBrokerSection({ enabled }: { enabled: boolean }) {
  const queryClient = useQueryClient();
  const { portfolioId } = usePortfolio();
  const [showTransferForm, setShowTransferForm] = useState(false);

  const summaryQuery = useQuery({
    queryKey: ["summary", portfolioId],
    queryFn: () => api.getSummary(portfolioId!),
    enabled: enabled && portfolioId !== null,
  });
  const assetsQuery = useQuery({ queryKey: ["assets"], queryFn: api.listAssets, enabled, staleTime: Infinity });
  const brokersQuery = useQuery({
    queryKey: ["brokers", portfolioId],
    queryFn: () => api.listBrokers(portfolioId!),
    enabled: enabled && portfolioId !== null,
    staleTime: Infinity,
  });

  const createMutation = useMutation({
    mutationFn: (input: TransactionInput) => api.createTransaction(input),
    // A Transfer moves cash between brokers, not just numbers on this one panel -- the
    // Transactions page's own list and its broker filter both need to see it too.
    onSuccess: () => {
      for (const key of [["summary"], ["transactions"], ["brokers"]]) {
        queryClient.invalidateQueries({ queryKey: key });
      }
      setShowTransferForm(false);
    },
  });

  const byBroker = summaryQuery.data?.cash_by_broker_eur ?? {};
  const entries = Object.entries(byBroker).sort(([, a], [, b]) => Number(b) - Number(a));

  return (
    <div className="mt-6">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-slate-700">Cash by broker</h3>
        <button
          type="button"
          onClick={() => setShowTransferForm(true)}
          className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
        >
          Transfer
        </button>
      </div>

      {createMutation.error && (
        <p className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          Couldn't save that transfer: {createMutation.error.message}
        </p>
      )}

      <div className="mt-2">
        {summaryQuery.isLoading ? (
          <Placeholder>Loading…</Placeholder>
        ) : entries.length === 0 ? (
          <Placeholder>No broker recorded on any cash movement yet.</Placeholder>
        ) : (
          <dl className="divide-y divide-slate-50 text-sm">
            {entries.map(([broker, amount]) => (
              <div key={broker} className="flex items-center justify-between py-1.5">
                <dt className="text-slate-600">{broker}</dt>
                <dd className="tabular-nums font-medium text-slate-900">{formatEur(amount)}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {showTransferForm &&
        portfolioId !== null &&
        createPortal(
          // Portaled out of App's `.module-gainr` root -- re-scoped so the page kit's colours and font apply.
          <div className="module-gainr contents">
            <TransactionForm
              assets={assetsQuery.data ?? []}
              brokers={brokersQuery.data ?? []}
              initial={undefined}
              defaultType="Transfer"
              portfolioId={portfolioId}
              isSubmitting={createMutation.isPending}
              onCancel={() => setShowTransferForm(false)}
              onSubmit={(input) => createMutation.mutate(input)}
            />
          </div>,
          document.body,
        )}
    </div>
  );
}

function FinancialsTable({ financials }: { financials: AssetFinancials }) {
  // One quarter then three years, left to right — most recent first, the way a filing is read.
  const periods: FinancialPeriod[] = [...(financials.quarter ? [financials.quarter] : []), ...financials.annual];
  const money = (value: string | null) => formatCompactCurrency(value, financials.currency);

  const rows: { label: string; render: (p: FinancialPeriod) => React.ReactNode }[] = [
    { label: "Revenue", render: (p) => <span className="tabular-nums text-slate-900">{money(p.revenue)}</span> },
    {
      label: "Revenue growth",
      render: (p) => (
        <span className={`tabular-nums ${pnlColorClass(p.revenue_growth_pct)}`}>{formatPct(p.revenue_growth_pct, 1)}</span>
      ),
    },
    {
      label: "Free cash flow",
      render: (p) => (
        <span className={`tabular-nums ${(toNumber(p.free_cash_flow) ?? 0) < 0 ? "text-red-600" : "text-slate-900"}`}>
          {money(p.free_cash_flow)}
        </span>
      ),
    },
    {
      label: "Net income",
      render: (p) => (
        <span className={`tabular-nums ${(toNumber(p.net_income) ?? 0) < 0 ? "text-red-600" : "text-slate-900"}`}>
          {money(p.net_income)}
        </span>
      ),
    },
    {
      label: "Net margin",
      render: (p) => (
        <span className={`tabular-nums ${(toNumber(p.net_margin_pct) ?? 0) < 0 ? "text-red-600" : "text-slate-900"}`}>
          {formatPct(p.net_margin_pct, 1, false)}
        </span>
      ),
    },
    // Only a bank gets this figure (the backend leaves it empty for anyone else), so the row
    // only appears when at least one period has it.
    ...(periods.some((p) => p.cost_income_pct !== null)
      ? [
          {
            label: "Cost/income",
            render: (p: FinancialPeriod) => (
              <span className="tabular-nums text-slate-900">{formatPct(p.cost_income_pct, 1, false)}</span>
            ),
          },
        ]
      : []),
  ];

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <th className="py-2 pr-3 text-left font-medium">Figure</th>
              {periods.map((p) => (
                <th key={p.label} className="whitespace-nowrap px-1.5 py-2 text-right font-medium">
                  {p.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b border-slate-50 last:border-0">
                <td className="whitespace-nowrap py-2.5 pr-3 text-slate-600">{row.label}</td>
                {periods.map((p) => (
                  <td key={p.label} className="whitespace-nowrap px-1.5 py-2.5 text-right">
                    {row.render(p)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs leading-relaxed text-slate-400">
        As reported{financials.currency ? ` in ${financials.currency}` : ""} — not converted to euros, so these don't
        line up with the values above. Growth is against the comparable prior period: the year before for a full year,
        the same quarter a year earlier for a quarter.
        {periods.length > 0 && ` Latest period ends ${formatDate(periods[0].period_end)}.`}
      </p>
    </div>
  );
}

function MetricTile({ label, value, negative }: { label: string; value: string; negative?: boolean }) {
  return (
    <div className="flex flex-col justify-center rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      {/* Fixed to two lines' worth of height so a tile with a short one-line label (e.g.
          "Net margin") matches one whose label wraps (e.g. "Operating margin") — otherwise
          every group's row is only as tall as its longest label, and tiles look mismatched. */}
      <div className="line-clamp-2 min-h-[2.2em] text-[11px] font-medium uppercase leading-tight tracking-wide text-slate-500">
        {label}
      </div>
      <div className={`mt-0.5 text-sm font-semibold tabular-nums ${negative ? "text-red-600" : "text-slate-900"}`}>
        {value}
      </div>
    </div>
  );
}

function KeyMetricsGrid({ metrics, currency }: { metrics: KeyMetrics; currency: string | null }) {
  const groups: { title: string; tiles: { label: string; value: string; negative?: boolean }[] }[] = [
    {
      title: "Valuation",
      tiles: [
        { label: "P/E (TTM)", value: formatRatio(metrics.pe_ratio) },
        { label: "Forward P/E", value: formatRatio(metrics.forward_pe_ratio) },
        { label: "P/FCF", value: formatRatio(metrics.price_to_fcf) },
        { label: "EV/EBITDA", value: formatRatio(metrics.ev_to_ebitda) },
      ],
    },
    {
      title: "Profitability",
      tiles: [
        { label: "Gross margin", value: formatPct(metrics.gross_margin_pct, 1, false) },
        { label: "Operating margin", value: formatPct(metrics.operating_margin_pct, 1, false) },
        {
          label: "Net margin",
          value: formatPct(metrics.net_margin_pct, 1, false),
          negative: (toNumber(metrics.net_margin_pct) ?? 0) < 0,
        },
      ],
    },
    {
      title: "Balance sheet",
      tiles: [
        {
          label: "Return on equity",
          value: formatPct(metrics.return_on_equity_pct, 1, false),
          negative: (toNumber(metrics.return_on_equity_pct) ?? 0) < 0,
        },
        { label: "Debt / equity", value: formatRatio(metrics.debt_to_equity) },
        {
          label: (toNumber(metrics.net_cash) ?? 0) < 0 ? "Net debt" : "Net cash",
          value: formatCompactCurrency(
            metrics.net_cash === null ? null : Math.abs(toNumber(metrics.net_cash) ?? 0).toString(),
            currency,
          ),
          negative: (toNumber(metrics.net_cash) ?? 0) < 0,
        },
      ],
    },
    {
      title: "Dividend",
      tiles: [
        { label: "Dividend yield", value: formatPct(metrics.dividend_yield_pct, 2, false) },
        { label: "Payout ratio", value: formatPct(metrics.payout_ratio_pct, 1, false) },
      ],
    },
  ];

  return (
    <div className="mb-5 space-y-4">
      {groups.map((group) => (
        <div key={group.title}>
          <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-400">{group.title}</div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {group.tiles.map((tile) => (
              <MetricTile key={tile.label} {...tile} />
            ))}
          </div>
        </div>
      ))}
      <p className="text-xs leading-relaxed text-slate-400">
        A snapshot as of the last quote, not tied to a reporting period — separate from the figures below.
      </p>
    </div>
  );
}

function FinancialsSection({ assetId, enabled }: { assetId: number; enabled: boolean }) {
  const query = useQuery({
    queryKey: ["asset-financials", assetId],
    queryFn: () => api.getAssetFinancials(assetId),
    enabled,
    staleTime: 60 * 60 * 1000,
  });

  if (query.isLoading) return <Placeholder>Loading financials…</Placeholder>;
  if (query.isError) return <Placeholder>Couldn't load financials for this holding.</Placeholder>;
  if (!query.data || (!query.data.quarter && query.data.annual.length === 0)) {
    return <Placeholder>No reported financials — funds and crypto don't file statements.</Placeholder>;
  }
  return (
    <div>
      {query.data.key_metrics && <KeyMetricsGrid metrics={query.data.key_metrics} currency={query.data.currency} />}
      <FinancialsTable financials={query.data} />
    </div>
  );
}

function TransactionsSection({
  assetId,
  nativeCurrency,
  enabled,
}: {
  assetId: number;
  nativeCurrency: string;
  enabled: boolean;
}) {
  const queryClient = useQueryClient();
  const { portfolioId } = usePortfolio();
  // null = closed; undefined inside the object = adding rather than editing.
  const [editing, setEditing] = useState<{ transaction: Transaction | undefined } | null>(null);

  const query = useQuery({
    queryKey: ["asset-transactions", portfolioId, assetId],
    queryFn: () =>
      api.listTransactions({ portfolioId: portfolioId!, assetId, limit: TRANSACTION_LIMIT, sortBy: "date", sortDir: "desc" }),
    enabled: enabled && portfolioId !== null,
  });
  const assetsQuery = useQuery({ queryKey: ["assets"], queryFn: api.listAssets, enabled, staleTime: Infinity });
  const brokersQuery = useQuery({
    queryKey: ["brokers", portfolioId],
    queryFn: () => api.listBrokers(portfolioId!),
    enabled: enabled && portfolioId !== null,
    staleTime: Infinity,
  });

  /** Positions, the summary and the chart are all derived from the ledger, so editing one
   * transaction moves every number on the page — not just this list. */
  const invalidateAll = () => {
    for (const key of [["asset-transactions"], ["transactions"], ["positions"], ["summary"], ["performance"]]) {
      queryClient.invalidateQueries({ queryKey: key });
    }
    setEditing(null);
  };

  const createMutation = useMutation({
    mutationFn: (input: TransactionInput) => api.createTransaction(input),
    onSuccess: invalidateAll,
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: TransactionInput }) => api.updateTransaction(id, input),
    onSuccess: invalidateAll,
  });
  const isSubmitting = createMutation.isPending || updateMutation.isPending;
  const error = createMutation.error ?? updateMutation.error;

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-slate-700">
          Transactions{query.data ? ` (${query.data.total})` : ""}
        </h3>
        <button
          type="button"
          onClick={() => setEditing({ transaction: undefined })}
          className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
        >
          + Add
        </button>
      </div>

      {error && (
        <p className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          Couldn't save that transaction: {error.message}
        </p>
      )}

      <div className="mt-2">
        {query.isLoading ? (
          <Placeholder>Loading transactions…</Placeholder>
        ) : query.isError ? (
          <Placeholder>Couldn't load transactions for this holding.</Placeholder>
        ) : !query.data || query.data.items.length === 0 ? (
          <Placeholder>No transactions recorded for this holding.</Placeholder>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-2 font-medium">Date</th>
                <th className="py-2 pr-2 font-medium">Type</th>
                <th className="py-2 pr-2 text-right font-medium">Quantity</th>
                <th className="py-2 pr-2 text-right font-medium">Price</th>
                <th className="py-2 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((txn) => (
                <tr
                  key={txn.id}
                  onClick={() => setEditing({ transaction: txn })}
                  className="cursor-pointer border-b border-slate-50 last:border-0 hover:bg-slate-50"
                >
                  <td className="whitespace-nowrap py-2 pr-2 text-slate-600">
                    {formatDate(txn.date, { year: "2-digit", month: "short", day: "numeric" })}
                  </td>
                  <td className="py-2 pr-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditing({ transaction: txn });
                      }}
                      className="text-slate-900 hover:text-blue-700 hover:underline"
                    >
                      {txn.type}
                    </button>
                  </td>
                  <td className="py-2 pr-2 text-right tabular-nums text-slate-600">
                    {txn.quantity ? formatQuantity(txn.quantity) : "—"}
                  </td>
                  <td className="py-2 pr-2 text-right tabular-nums text-slate-600">
                    {txn.price ? formatCurrency(txn.price, txn.native_currency ?? nativeCurrency) : "—"}
                  </td>
                  <td className="py-2 text-right tabular-nums font-medium text-slate-900">{formatEur(txn.total_eur)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="mt-3 text-xs leading-relaxed text-slate-400">
        Click a transaction to edit it. Positions and performance are derived from this ledger,
        so a change here moves every figure on the page.
      </p>

      {/* Portalled to the body: the panel is transformed while it slides, and a transform
          makes it the containing block for fixed children — the modal would otherwise be
          trapped inside the panel rather than covering the screen. */}
      {editing !== null &&
        portfolioId !== null &&
        createPortal(
          // Portaled out of App's `.module-gainr` root -- re-scoped so the page kit's colours and font apply.
          <div className="module-gainr contents">
            <TransactionForm
              assets={assetsQuery.data ?? []}
              brokers={brokersQuery.data ?? []}
              initial={editing.transaction}
              defaultAssetId={assetId}
              portfolioId={portfolioId}
              isSubmitting={isSubmitting}
              onCancel={() => setEditing(null)}
              onSubmit={(input) =>
                editing.transaction
                  ? updateMutation.mutate({ id: editing.transaction.id, input })
                  : createMutation.mutate(input)
              }
            />
          </div>,
          document.body,
        )}
    </div>
  );
}

const noteInputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

function NoteForm({
  initial,
  onCancel,
  onSubmit,
  isSubmitting,
}: {
  initial: PositionNote | undefined;
  onCancel: () => void;
  onSubmit: (input: PositionNoteInput) => void;
  isSubmitting: boolean;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [body, setBody] = useState(initial?.body ?? "");
  const [labelIds, setLabelIds] = useState<number[]>(initial?.labels.map((l) => l.id) ?? []);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ title, body, label_ids: labelIds });
      }}
      className="mt-2 flex flex-col gap-2 rounded-md border border-slate-200 p-3"
    >
      <input
        required
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title"
        className={noteInputClass}
      />
      <textarea
        required
        rows={4}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="What's on your mind? **bold**, *italic*, ~~strikethrough~~, `code`, # headings, - bullets and 1. numbered lists are supported."
        className={`${noteInputClass} resize-y`}
      />
      <LabelPicker selectedIds={labelIds} onChange={setLabelIds} />
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {isSubmitting ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}

function NotesSection({ assetId, enabled }: { assetId: number; enabled: boolean }) {
  const queryClient = useQueryClient();
  // null = closed; undefined inside the object = adding rather than editing.
  const [editing, setEditing] = useState<{ note: PositionNote | undefined } | null>(null);

  const query = useQuery({
    queryKey: ["position-notes", assetId],
    queryFn: () => api.listPositionNotes(assetId),
    enabled,
  });

  const invalidate = () => {
    // Broad, not just this asset: a note can be about several positions, and the Journal shows
    // the same rows.
    queryClient.invalidateQueries({ queryKey: ["position-notes"] });
    queryClient.invalidateQueries({ queryKey: ["journal-notes"] });
    setEditing(null);
  };
  const createMutation = useMutation({
    mutationFn: (input: PositionNoteInput) => api.createPositionNote(assetId, input),
    onSuccess: invalidate,
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: Partial<PositionNoteInput> }) =>
      api.updatePositionNote(assetId, id, input),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deletePositionNote(assetId, id),
    // A shared note disappears from its other positions and the Journal too.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["position-notes"] });
      queryClient.invalidateQueries({ queryKey: ["journal-notes"] });
    },
  });
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-slate-700">Notes{query.data ? ` (${query.data.length})` : ""}</h3>
        {editing === null && (
          <button
            type="button"
            onClick={() => setEditing({ note: undefined })}
            className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
          >
            + Add
          </button>
        )}
      </div>

      {editing && (
        <NoteForm
          initial={editing.note}
          isSubmitting={isSubmitting}
          onCancel={() => setEditing(null)}
          onSubmit={(input) =>
            editing.note ? updateMutation.mutate({ id: editing.note.id, input }) : createMutation.mutate(input)
          }
        />
      )}

      <div className="mt-2 space-y-3">
        {query.isLoading ? (
          <Placeholder>Loading notes…</Placeholder>
        ) : query.isError ? (
          <Placeholder>Couldn't load notes for this holding.</Placeholder>
        ) : !query.data || query.data.length === 0 ? (
          editing === null && <Placeholder>No notes yet — keep a journal on why you hold this.</Placeholder>
        ) : (
          query.data.map((note) => (
            <article key={note.id} className="border-b border-slate-100 pb-3 last:border-0">
              <div className="flex items-baseline justify-between gap-2">
                <h4 className="truncate text-sm font-medium text-slate-900">{note.title}</h4>
                <span className="shrink-0 text-xs text-slate-400">{formatRelativeTime(note.created_at)}</span>
              </div>
              <div className="mt-1">
                <NoteBody note={note} />
              </div>
              {note.assets.length > 1 && (
                <p className="mt-1 text-xs text-slate-500">
                  Also about{" "}
                  {note.assets
                    .filter((a) => a.id !== assetId)
                    .map((a) => a.ticker)
                    .join(", ")}
                </p>
              )}
              {note.labels.length > 0 && (
                <div className="mt-1.5">
                  <LabelChips labels={note.labels} />
                </div>
              )}
              <div className="mt-1.5 flex gap-3 text-xs">
                <button type="button" onClick={() => setEditing({ note })} className="text-slate-500 hover:text-slate-900" title="Edit" aria-label="Edit">
                  <Pencil className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const others = note.assets.filter((a) => a.id !== assetId).map((a) => a.ticker);
                    const also = others.length > 0 ? ` It's also about ${others.join(", ")} and will be removed there too.` : "";
                    if (confirm(`Delete "${note.title}"?${also}`)) deleteMutation.mutate(note.id);
                  }}
                  className="text-red-500 hover:text-red-700"
                  title="Delete"
                  aria-label="Delete"
                >
                  <Trash2 className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </div>
  );
}

export default function PositionDetailPanel({ position, onClose }: { position: Position | null; onClose: () => void }) {
  // The panel keeps rendering the last holding while it slides out, so the content doesn't
  // blank a frame before it's gone.
  const [shown, setShown] = useState<Position | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const closeButton = useRef<HTMLButtonElement>(null);
  const open = position !== null;

  useEffect(() => {
    if (!position) return;
    setShown(position);
    setTab("overview");
    closeButton.current?.focus();
  }, [position]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!shown) return null;

  const isCash = shown.ticker === "CASH";

  return (
    <>
      <div
        onClick={onClose}
        aria-hidden
        className={`fixed inset-0 z-40 bg-slate-900/20 transition-opacity duration-200 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`${shown.name} details`}
        aria-hidden={!open}
        className={`fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-2xl transition-transform duration-200 ease-out sm:max-w-xl ${
          open ? "translate-x-0" : "pointer-events-none translate-x-full"
        }`}
      >
        <header className="flex items-start gap-3 border-b border-slate-200 px-5 py-4">
          <AssetLogo assetId={shown.asset_id} name={shown.name} ticker={shown.ticker} size={36} />
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-base font-semibold text-slate-900">{shown.name}</h2>
            <div className="text-xs text-slate-500">
              {isCash ? "Cash balance" : shown.ticker}
              {!isCash && shown.price_date && ` · priced ${formatDate(shown.price_date)}`}
            </div>
          </div>
          <button
            ref={closeButton}
            onClick={onClose}
            aria-label="Close"
            className="-mr-1 rounded-md p-1.5 text-xl leading-none text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
          >
            ×
          </button>
        </header>

        {/* Scrolls sideways rather than wrapping when five tabs don't fit a phone-width panel. */}
        <nav className="flex gap-3 overflow-x-auto border-b border-slate-200 px-4 sm:gap-4 sm:px-5" aria-label="Position detail sections">
          {/* Cash is a derived row, not a company -- it has no events to show. */}
          {TABS.filter((t) => !(isCash && t.id === "calendar")).map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id}
              className={`-mb-px shrink-0 border-b-2 py-2.5 text-sm font-medium transition-colors ${
                tab === t.id
                  ? "border-slate-900 text-slate-900"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {tab === "overview" ? (
            <>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <Stat label="Quantity" value={isCash ? "—" : formatQuantity(shown.quantity)} />
                <Stat
                  label="Price"
                  value={isCash ? "—" : formatCurrency(shown.current_price_native, shown.native_currency)}
                />
                <Stat label="Value" value={formatEur(shown.market_value_eur)} />
              </div>

              {!isCash && (
                <dl className="mt-3 grid grid-cols-1 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-2">
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Cost basis</dt>
                    <dd className="tabular-nums text-slate-700">{formatEur(shown.cost_basis_eur)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Weight</dt>
                    <dd className="tabular-nums text-slate-700">{formatWeight(shown.weight_pct)}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="text-slate-500">Target weight</dt>
                    <dd>
                      <TargetWeightInput position={shown} />
                    </dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="text-slate-500">DLT rating</dt>
                    <dd>
                      <DltRatingInput assetId={shown.asset_id} value={shown.dlt_judgment} />
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Unrealized</dt>
                    <dd className={`tabular-nums ${pnlColorClass(shown.unrealized_pnl_eur)}`}>
                      {formatEur(shown.unrealized_pnl_eur)} ({formatPct(shown.unrealized_pnl_pct)})
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Realized</dt>
                    <dd className={`tabular-nums ${pnlColorClass(shown.realized_pnl_eur)}`}>
                      {(toNumber(shown.realized_pnl_eur) ?? 0) === 0 ? "—" : formatEur(shown.realized_pnl_eur)}
                    </dd>
                  </div>
                </dl>
              )}

              {!isCash && <NextEventLine assetId={shown.asset_id} enabled={open && shown.asset_id > 0} />}

              {isCash && <CashByBrokerSection enabled={open} />}

              <NewsSection assetId={shown.asset_id} enabled={open && shown.asset_id > 0} />
            </>
          ) : tab === "financials" ? (
            <FinancialsSection assetId={shown.asset_id} enabled={open && shown.asset_id > 0} />
          ) : tab === "transactions" ? (
            <TransactionsSection
              assetId={shown.asset_id}
              nativeCurrency={shown.native_currency}
              enabled={open && shown.asset_id > 0}
            />
          ) : tab === "notes" ? (
            <NotesSection assetId={shown.asset_id} enabled={open && shown.asset_id > 0} />
          ) : (
            <PositionCalendarSection assetId={shown.asset_id} enabled={open && shown.asset_id > 0} />
          )}
        </div>
      </aside>
    </>
  );
}
