import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { PerformanceRange, Position } from "../api/types";
import AllocationByClass from "../components/AllocationByClass";
import ClosedPositions from "../components/ClosedPositions";
import { readCollapsibleState } from "../components/CollapsibleCard";
import PerformanceChart from "../components/PerformanceChart";
import PositionDetailPanel from "../components/PositionDetailPanel";
import PositionsTable from "../components/PositionsTable";
import RebalanceDialog from "../components/RebalanceDialog";
import GainrTopRow from "../components/GainrTopRow";
import HoldingsList from "../components/HoldingsList";
import HomeFigures from "../components/HomeFigures";
import HomeHero from "../components/HomeHero";
import { usePortfolio } from "../hooks/usePortfolio";
import { t } from "../i18n";

// The server refreshes live quotes once an hour (docs/adr/0047); polling a few times within that
// hour shows a new quote soon after it lands, at the cost of a local request, never a Yahoo one.
const LIVE_PRICE_REFETCH_MS = 15 * 60_000;

export default function Home() {
  const { portfolioId, portfolios } = usePortfolio();
  const portfolioName = portfolios.find((p) => p.id === portfolioId)?.name;
  const [range, setRange] = useState<PerformanceRange>("YTD");
  const [activeBenchmarks, setActiveBenchmarks] = useState<string[]>([]);
  // Seeded from the same stored value the chart's own card reads, so a chart left collapsed
  // doesn't fire the performance request — which on a cold cache is the one call that can
  // take half a minute while it backfills historical prices.
  const [chartOpen, setChartOpen] = useState(() => readCollapsibleState("performance-chart"));
  const [selected, setSelected] = useState<Position | null>(null);
  const [rebalancing, setRebalancing] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  const summaryQuery = useQuery({
    queryKey: ["summary", portfolioId],
    queryFn: () => api.getSummary(portfolioId!),
    enabled: portfolioId !== null,
    refetchInterval: LIVE_PRICE_REFETCH_MS,
  });
  const positionsQuery = useQuery({
    queryKey: ["positions", portfolioId],
    queryFn: () => api.getPositions(portfolioId!),
    enabled: portfolioId !== null,
    refetchInterval: LIVE_PRICE_REFETCH_MS,
  });

  // Deep link from the Journal tab ("view this position") -- opens the same detail panel a
  // table-row click does, then drops the param so it doesn't reopen on a later back/refresh.
  useEffect(() => {
    const assetId = searchParams.get("position");
    if (!assetId || !positionsQuery.data) return;
    const match = positionsQuery.data.find((p) => p.asset_id === Number(assetId));
    if (match) setSelected(match);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("position");
        return next;
      },
      { replace: true },
    );
  }, [searchParams, positionsQuery.data, setSearchParams]);
  const closedQuery = useQuery({
    queryKey: ["positions", "closed", portfolioId],
    queryFn: () => api.getClosedPositions(portfolioId!),
    enabled: portfolioId !== null,
  });
  const benchmarksQuery = useQuery({ queryKey: ["benchmarks"], queryFn: api.listBenchmarks, staleTime: Infinity });
  const performanceQuery = useQuery({
    queryKey: ["performance", portfolioId, range, activeBenchmarks],
    queryFn: () => api.getPerformance(portfolioId!, range, activeBenchmarks),
    placeholderData: (previous) => previous,
    enabled: chartOpen && portfolioId !== null,
    refetchInterval: LIVE_PRICE_REFETCH_MS,
  });

  const toggleBenchmark = (key: string) =>
    setActiveBenchmarks((keys) => (keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key]));

  // On a phone, the module and portfolio pills (the shared header holding them is hidden there).
  // The page's title is the portfolio's value itself; the heading is for screen readers.
  const header = (
    <>
      <GainrTopRow />
      <h1 className="sr-only">{t("Home")}{portfolioName ? `, ${portfolioName}` : ""}</h1>
    </>
  );

  if (summaryQuery.isError) {
    return (
      <div className="flex flex-col gap-4">
        {header}
        <ErrorBanner message={t("Could not load portfolio summary. Is the backend running?")} />
      </div>
    );
  }

  const holdingsProps = {
    positions: positionsQuery.data,
    isLoading: positionsQuery.isLoading,
    isError: positionsQuery.isError,
    onRetry: () => positionsQuery.refetch(),
    onSelect: setSelected,
    onRebalance: () => setRebalancing(true),
  };

  // Today first: the value and its move, then the figures behind it, the chart, and the holdings.
  // From a wide screen up the figures and the allocation move into a side column.
  return (
    <div className="flex flex-col gap-4 sm:gap-6">
      {header}
      <HomeHero summary={summaryQuery.data} positions={positionsQuery.data} portfolioName={portfolioName ?? null} />
      <div className="lg:hidden">
        <HomeFigures summary={summaryQuery.data} />
      </div>

      {/* From a wide screen up the figures and the allocation sit beside the chart, and the
          holdings table below gets the full width its columns need. */}
      <div className="flex flex-col gap-4 sm:gap-6 lg:grid lg:grid-cols-[minmax(0,1fr)_18.5rem] lg:items-start">
        <div className="min-w-0">
          <PerformanceChart
            performance={performanceQuery.data}
            range={range}
            onRangeChange={setRange}
            isLoading={performanceQuery.isLoading}
            isError={performanceQuery.isError}
            onRetry={() => performanceQuery.refetch()}
            benchmarks={benchmarksQuery.data ?? []}
            activeBenchmarks={activeBenchmarks}
            onToggleBenchmark={toggleBenchmark}
            onOpenChange={setChartOpen}
          />
        </div>

        <aside aria-label={t("Figures and allocation")} className="hidden flex-col gap-6 lg:flex">
          <HomeFigures summary={summaryQuery.data} layout="list" />
          <AllocationByClass positions={positionsQuery.data} />
        </aside>

        <div className="min-w-0 sm:hidden">
          <HoldingsList {...holdingsProps} />
        </div>
        <div className="hidden min-w-0 sm:block lg:col-span-2">
          <PositionsTable {...holdingsProps} />
        </div>

        <div className="lg:hidden">
          <AllocationByClass positions={positionsQuery.data} />
        </div>

        <div className="min-w-0 lg:col-span-2">
          <ClosedPositions
            positions={closedQuery.data}
            isLoading={closedQuery.isLoading}
            isError={closedQuery.isError}
            onRetry={() => closedQuery.refetch()}
          />
        </div>
      </div>

      <PositionDetailPanel position={selected} onClose={() => setSelected(null)} />
      {rebalancing && portfolioId !== null && <RebalanceDialog portfolioId={portfolioId} cashEur={summaryQuery.data?.cash_eur} onClose={() => setRebalancing(false)} />}
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-ui-late-soft px-4 py-3.5 text-[15px] font-semibold text-ui-late">{message}</div>
  );
}
