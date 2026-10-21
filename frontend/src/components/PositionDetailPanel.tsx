import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import AssetLogo from "./AssetLogo";
import CollapsibleCard from "./CollapsibleCard";
import NewsSourcesEditor from "./NewsSourcesEditor";
import LinkedNotes from "./notr/LinkedNotes";
import PositionCalendarSection, { NextEventLine } from "./PositionCalendar";
import PriceChart from "./PriceChart";
import TargetWeightInput from "./TargetWeightInput";
import AttachmentBadge from "./AttachmentBadge";
import TransactionForm from "./TransactionForm";
import { api } from "../api/client";
import { usePortfolio } from "../hooks/usePortfolio";
import type {
  AssetFinancials,
  DltJudgment,
  FinancialPeriod,
  KeyMetrics,
  Position,
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
  formatTime,
  formatWeight,
  pnlColorClass,
  toNumber,
} from "../utils/format";
import { warnFailedAttachments } from "../utils/attachments";
import PositionMetricsSection from "./PositionMetrics";
import { msg, t as tr } from "../i18n";

type Tab = "overview" | "financials" | "metrics" | "transactions" | "notes" | "calendar";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: msg("Overview") },
  { id: "financials", label: msg("Financials") },
  { id: "metrics", label: msg("Metrics") },
  { id: "transactions", label: msg("Transactions") },
  { id: "notes", label: msg("Notes") },
  { id: "calendar", label: msg("Calendar") },
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
      <option value="">{tr("No rating")}</option>
      <option value="attractive">{tr("Attractive")}</option>
      <option value="neutral">{tr("Neutral")}</option>
      <option value="critical">{tr("Critical")}</option>
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
        title={tr("News")}
        meta={
          <span className="text-xs text-slate-400">{tr("past {value} days", { value: query.data?.window_days ?? 7 })}{query.data ? ` · ${query.data.items.length}` : ""}
          </span>
        }
      >
        {query.data && <NewsSourcesEditor assetId={assetId} sources={query.data.sources} />}
        <div className="space-y-3">
          {query.isLoading ? (
            <Placeholder>{tr("Loading news…")}</Placeholder>
          ) : query.isError ? (
            <Placeholder>{tr("Couldn't load news for this holding.")}</Placeholder>
          ) : !query.data || query.data.items.length === 0 ? (
            <Placeholder>
              {query.data?.sources.length
                ? tr("No stories in the past week.")
                : tr("No stories in the past week. For a fund or commodity, add a market, sector or industry above.")}
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
    mutationFn: ({ input, files }: { input: TransactionInput; files: File[] }) =>
      api.createTransactionWithAttachments(input, files),
    // A Transfer moves cash between brokers, not just numbers on this one panel -- the
    // Transactions page's own list and its broker filter both need to see it too.
    onSuccess: ({ failed }) => {
      for (const key of [["summary"], ["transactions"], ["brokers"], ["cash-movements"]]) {
        queryClient.invalidateQueries({ queryKey: key });
      }
      setShowTransferForm(false);
      warnFailedAttachments(failed);
    },
  });

  const byBroker = summaryQuery.data?.cash_by_broker_eur ?? {};
  const entries = Object.entries(byBroker).sort(([, a], [, b]) => Number(b) - Number(a));

  return (
    <div className="mt-6">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-slate-700">{tr("Cash by broker")}</h3>
        <button
          type="button"
          onClick={() => setShowTransferForm(true)}
          className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
        >{tr("Transfer")}</button>
      </div>

      {createMutation.error && (
        <p className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{tr("Couldn't save that transfer: {message}", { message: createMutation.error.message })}</p>
      )}

      <div className="mt-2">
        {summaryQuery.isLoading ? (
          <Placeholder>{tr("Loading…")}</Placeholder>
        ) : entries.length === 0 ? (
          <Placeholder>{tr("No broker recorded on any cash movement yet.")}</Placeholder>
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
              onSubmit={(input, files) => createMutation.mutate({ input, files })}
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
    { label: tr("Revenue"), render: (p) => <span className="tabular-nums text-slate-900">{money(p.revenue)}</span> },
    {
      label: tr("Revenue growth"),
      render: (p) => (
        <span className={`tabular-nums ${pnlColorClass(p.revenue_growth_pct)}`}>{formatPct(p.revenue_growth_pct, 1)}</span>
      ),
    },
    {
      label: tr("Free cash flow"),
      render: (p) => (
        <span className={`tabular-nums ${(toNumber(p.free_cash_flow) ?? 0) < 0 ? "text-red-600" : "text-slate-900"}`}>
          {money(p.free_cash_flow)}
        </span>
      ),
    },
    {
      label: tr("Net income"),
      render: (p) => (
        <span className={`tabular-nums ${(toNumber(p.net_income) ?? 0) < 0 ? "text-red-600" : "text-slate-900"}`}>
          {money(p.net_income)}
        </span>
      ),
    },
    {
      label: tr("Net margin"),
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
            label: tr("Cost/income"),
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
              <th className="py-2 pr-3 text-left font-medium">{tr("Figure")}</th>
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

      <p className="mt-3 text-xs leading-relaxed text-slate-400">{tr("As reported")}{financials.currency ? ` ${tr("in {currency}", { currency: financials.currency })}` : ""}{" "}{tr("— not converted to euros, so these don't line up with the values above. Growth is against the comparable prior period: the year before for a full year, the same quarter a year earlier for a quarter.")}{periods.length > 0 && ` ${tr("Latest period ends {date}.", { date: formatDate(periods[0].period_end) })}`}

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
      title: tr("Valuation"),
      tiles: [
        { label: tr("P/E (TTM)"), value: formatRatio(metrics.pe_ratio) },
        { label: tr("Forward P/E"), value: formatRatio(metrics.forward_pe_ratio) },
        { label: "P/FCF", value: formatRatio(metrics.price_to_fcf) },
        { label: "EV/EBITDA", value: formatRatio(metrics.ev_to_ebitda) },
      ],
    },
    {
      title: tr("Profitability"),
      tiles: [
        { label: tr("Gross margin"), value: formatPct(metrics.gross_margin_pct, 1, false) },
        { label: tr("Operating margin"), value: formatPct(metrics.operating_margin_pct, 1, false) },
        {
          label: tr("Net margin"),
          value: formatPct(metrics.net_margin_pct, 1, false),
          negative: (toNumber(metrics.net_margin_pct) ?? 0) < 0,
        },
      ],
    },
    {
      title: tr("Balance sheet"),
      tiles: [
        {
          label: tr("Return on equity"),
          value: formatPct(metrics.return_on_equity_pct, 1, false),
          negative: (toNumber(metrics.return_on_equity_pct) ?? 0) < 0,
        },
        { label: tr("Debt / equity"), value: formatRatio(metrics.debt_to_equity) },
        {
          label: (toNumber(metrics.net_cash) ?? 0) < 0 ? tr("Net debt") : tr("Net cash"),
          value: formatCompactCurrency(
            metrics.net_cash === null ? null : Math.abs(toNumber(metrics.net_cash) ?? 0).toString(),
            currency,
          ),
          negative: (toNumber(metrics.net_cash) ?? 0) < 0,
        },
      ],
    },
    {
      title: tr("Dividend"),
      tiles: [
        { label: tr("Dividend yield"), value: formatPct(metrics.dividend_yield_pct, 2, false) },
        { label: tr("Payout ratio"), value: formatPct(metrics.payout_ratio_pct, 1, false) },
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
      <p className="text-xs leading-relaxed text-slate-400">{tr("A snapshot as of the last quote, not tied to a reporting period — separate from the figures below.")}</p>
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

  if (query.isLoading) return <Placeholder>{tr("Loading financials…")}</Placeholder>;
  if (query.isError) return <Placeholder>{tr("Couldn't load financials for this holding.")}</Placeholder>;
  if (!query.data || (!query.data.quarter && query.data.annual.length === 0)) {
    return <Placeholder>{tr("No reported financials — funds and crypto don't file statements.")}</Placeholder>;
  }
  return (
    <div>
      {query.data.key_metrics && <KeyMetricsGrid metrics={query.data.key_metrics} currency={query.data.currency} />}
      <FinancialsTable financials={query.data} />
    </div>
  );
}

/** The Cash card's ledger: every deposit, withdrawal, dividend, interest payment, fee and transfer
 * behind the balance -- buys and sells are left out, they live on their positions. Read-only on
 * purpose: these rows are edited on the Transactions page. */
function CashMovementsSection({ enabled }: { enabled: boolean }) {
  const { portfolioId } = usePortfolio();
  const query = useQuery({
    queryKey: ["cash-movements", portfolioId],
    queryFn: () =>
      api.listTransactions({
        portfolioId: portfolioId!,
        cashMovements: true,
        limit: TRANSACTION_LIMIT,
        sortBy: "date",
        sortDir: "desc",
      }),
    enabled: enabled && portfolioId !== null,
  });

  return (
    <div>
      <h3 className="text-sm font-medium text-slate-700">{tr("Cash movements")}{query.data ? ` (${query.data.total})` : ""}
      </h3>
      <div className="mt-2">
        {query.isLoading ? (
          <Placeholder>{tr("Loading cash movements…")}</Placeholder>
        ) : query.isError ? (
          <Placeholder>{tr("Couldn't load the cash movements.")}</Placeholder>
        ) : !query.data || query.data.items.length === 0 ? (
          <Placeholder>{tr("No cash movements recorded.")}</Placeholder>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-2 font-medium">{tr("Date")}</th>
                <th className="py-2 pr-2 font-medium">{tr("Type")}</th>
                <th className="py-2 pr-2 font-medium">{tr("Broker")}</th>
                <th className="py-2 text-right font-medium">{tr("Total")}</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((txn) => (
                <tr key={txn.id} className="border-b border-slate-50 last:border-0">
                  <td className="whitespace-nowrap py-2 pr-2 text-slate-600">
                    {formatDate(txn.date, { year: "2-digit", month: "short", day: "numeric" })}
                  </td>
                  <td className="py-2 pr-2 text-slate-900">
                    {tr(txn.type)}
                    {txn.asset_name && <span className="text-slate-500"> · {txn.asset_name}</span>}
                    <AttachmentBadge count={txn.attachment_count} />
                  </td>
                  <td className="py-2 pr-2 text-slate-600">
                    {txn.to_broker ? `${txn.broker ?? "—"} → ${txn.to_broker}` : (txn.broker ?? "—")}

                  </td>
                  <td className="py-2 text-right tabular-nums font-medium text-slate-900">{formatEur(txn.total_eur)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <p className="mt-3 text-xs leading-relaxed text-slate-400">{tr("Everything that moves cash except buying and selling. Edit these on the Transactions page.")}</p>
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
    for (const key of [["asset-transactions"], ["transactions"], ["cash-movements"], ["positions"], ["summary"], ["performance"]]) {
      queryClient.invalidateQueries({ queryKey: key });
    }
    setEditing(null);
  };

  const createMutation = useMutation({
    mutationFn: ({ input, files }: { input: TransactionInput; files: File[] }) =>
      api.createTransactionWithAttachments(input, files),
    onSuccess: ({ failed }) => {
      invalidateAll();
      warnFailedAttachments(failed);
    },
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
        <h3 className="text-sm font-medium text-slate-700">{tr("Transactions")}{query.data ? ` (${query.data.total})` : ""}
        </h3>
        <button
          type="button"
          onClick={() => setEditing({ transaction: undefined })}
          className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
        >{tr("+ Add")}</button>
      </div>

      {error && (
        <p className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{tr("Couldn't save that transaction: {message}", { message: error.message })}</p>
      )}

      <div className="mt-2">
        {query.isLoading ? (
          <Placeholder>{tr("Loading transactions…")}</Placeholder>
        ) : query.isError ? (
          <Placeholder>{tr("Couldn't load transactions for this holding.")}</Placeholder>
        ) : !query.data || query.data.items.length === 0 ? (
          <Placeholder>{tr("No transactions recorded for this holding.")}</Placeholder>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-2 font-medium">{tr("Date")}</th>
                <th className="py-2 pr-2 font-medium">{tr("Type")}</th>
                <th className="py-2 pr-2 text-right font-medium">{tr("Quantity")}</th>
                <th className="py-2 pr-2 text-right font-medium">{tr("Price")}</th>
                <th className="py-2 text-right font-medium">{tr("Total")}</th>
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
                      {tr(txn.type)}
                    </button>
                    <AttachmentBadge count={txn.attachment_count} />
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

      <p className="mt-3 text-xs leading-relaxed text-slate-400">{tr("Click a transaction to edit it. Positions and performance are derived from this ledger, so a change here moves every figure on the page.")}</p>

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
              onSubmit={(input, files) =>
                editing.transaction
                  ? updateMutation.mutate({ id: editing.transaction.id, input })
                  : createMutation.mutate({ input, files })
              }
            />
          </div>,
          document.body,
        )}
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

  // Only some holdings have a checklist (see fundamentals_metrics.py); the tab appears for those.
  const metricsQuery = useQuery({
    queryKey: ["asset-metrics", shown?.asset_id],
    queryFn: () => api.getAssetMetrics(shown!.asset_id),
    enabled: open && !!shown && shown.asset_id > 0,
    staleTime: 60 * 60 * 1000,
  });

  if (!shown) return null;

  const isCash = shown.ticker === "CASH";
  const hasMetrics = (metricsQuery.data?.metrics.length ?? 0) > 0;

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
        aria-label={tr("{name} details", { name: shown.name })}
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
              {isCash ? tr("Cash balance") : shown.ticker}
              {!isCash &&
                shown.price_date &&
                ` · ${tr("priced {date}", { date: formatDate(shown.price_date) })}${shown.price_quoted_at ? `, ${formatTime(shown.price_quoted_at)}` : ""}`}

            </div>
          </div>
          <button
            ref={closeButton}
            onClick={onClose}
            aria-label={tr("Close")}
            className="-mr-1 rounded-md p-1.5 text-xl leading-none text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
          >
            ×
          </button>
        </header>

        {/* Scrolls sideways rather than wrapping when five tabs don't fit a phone-width panel. */}
        <nav className="flex gap-3 overflow-x-auto border-b border-slate-200 px-4 sm:gap-4 sm:px-5" aria-label={tr("Position detail sections")}>
          {/* Cash is a derived row, not a company -- it has no events to show. */}
          {TABS.filter((t) => !(isCash && (t.id === "calendar" || t.id === "notes")) && (t.id !== "metrics" || hasMetrics)).map((t) => (
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
              {tr(t.label)}
            </button>
          ))}
        </nav>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {tab === "overview" ? (
            <>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <Stat label={tr("Quantity")} value={isCash ? "—" : formatQuantity(shown.quantity)} />
                <Stat
                  label={tr("Price")}
                  value={isCash ? "—" : formatCurrency(shown.current_price_native, shown.native_currency)}
                />
                <Stat label={tr("Value")} value={formatEur(shown.market_value_eur)} />
              </div>

              {!isCash && <PriceChart assetId={shown.asset_id} enabled={open && shown.asset_id > 0} />}

              {!isCash && (
                <dl className="mt-3 grid grid-cols-1 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-2">
                  <div className="flex justify-between">
                    <dt className="text-slate-500">{tr("Cost basis")}</dt>
                    <dd className="tabular-nums text-slate-700">{formatEur(shown.cost_basis_eur)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">{tr("Weight")}</dt>
                    <dd className="tabular-nums text-slate-700">{formatWeight(shown.weight_pct)}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="text-slate-500">{tr("Target weight")}</dt>
                    <dd>
                      <TargetWeightInput position={shown} />
                    </dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="text-slate-500">{tr("DLT rating")}</dt>
                    <dd>
                      <DltRatingInput assetId={shown.asset_id} value={shown.dlt_judgment} />
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">{tr("Unrealized")}</dt>
                    <dd className={`tabular-nums ${pnlColorClass(shown.unrealized_pnl_eur)}`}>
                      {formatEur(shown.unrealized_pnl_eur)} ({formatPct(shown.unrealized_pnl_pct)})
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">{tr("Realized")}</dt>
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
          ) : tab === "metrics" ? (
            metricsQuery.data && hasMetrics ? <PositionMetricsSection data={metricsQuery.data} /> : <Placeholder>{tr("No metrics for this holding.")}</Placeholder>
          ) : tab === "transactions" && isCash ? (
            <CashMovementsSection enabled={open} />
          ) : tab === "transactions" ? (
            <TransactionsSection
              assetId={shown.asset_id}
              nativeCurrency={shown.native_currency}
              enabled={open && shown.asset_id > 0}
            />
          ) : tab === "notes" ? (
            <LinkedNotes assetId={shown.asset_id} />
          ) : (
            <PositionCalendarSection assetId={shown.asset_id} enabled={open && shown.asset_id > 0} />
          )}
        </div>
      </aside>
    </>
  );
}
