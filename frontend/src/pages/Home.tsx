import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { PerformanceRange, Position } from "../api/types";
import AllocationPieChart from "../components/AllocationPieChart";
import ClosedPositions from "../components/ClosedPositions";
import { readCollapsibleState } from "../components/CollapsibleCard";
import PerformanceChart from "../components/PerformanceChart";
import PositionDetailPanel from "../components/PositionDetailPanel";
import PositionsTable from "../components/PositionsTable";
import SummaryCards from "../components/SummaryCards";
import GainrTopRow from "../components/GainrTopRow";
import { PageTitle } from "../components/ui/kit";
import { usePortfolio } from "../hooks/usePortfolio";

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
  const [searchParams, setSearchParams] = useSearchParams();

  const summaryQuery = useQuery({
    queryKey: ["summary", portfolioId],
    queryFn: () => api.getSummary(portfolioId!),
    enabled: portfolioId !== null,
  });
  const positionsQuery = useQuery({
    queryKey: ["positions", portfolioId],
    queryFn: () => api.getPositions(portfolioId!),
    enabled: portfolioId !== null,
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
  });

  const toggleBenchmark = (key: string) =>
    setActiveBenchmarks((keys) => (keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key]));

  // The page kit's header: on a phone, the module and portfolio pills (the shared header holding
  // them is hidden there); on every width, the page title.
  const header = (
    <div className="flex flex-col gap-4">
      <div className="sm:hidden">
        <GainrTopRow />
      </div>
      <PageTitle subtitle={portfolioName ? `${portfolioName} portfolio` : undefined}>Home</PageTitle>
    </div>
  );

  if (summaryQuery.isError) {
    return (
      <div className="flex flex-col gap-4">
        {header}
        <ErrorBanner message="Could not load portfolio summary. Is the backend running?" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 sm:gap-6">
      {header}
      {summaryQuery.data ? (
        <SummaryCards summary={summaryQuery.data} />
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-2xl bg-ui-tile" />
          ))}
        </div>
      )}

      <PerformanceChart
        performance={performanceQuery.data}
        range={range}
        onRangeChange={setRange}
        isLoading={performanceQuery.isLoading}
        benchmarks={benchmarksQuery.data ?? []}
        activeBenchmarks={activeBenchmarks}
        onToggleBenchmark={toggleBenchmark}
        onOpenChange={setChartOpen}
      />

      <AllocationPieChart positions={positionsQuery.data} isLoading={positionsQuery.isLoading} />

      <PositionsTable
        positions={positionsQuery.data}
        isLoading={positionsQuery.isLoading}
        onSelect={setSelected}
      />

      <ClosedPositions positions={closedQuery.data} isLoading={closedQuery.isLoading} />

      <PositionDetailPanel position={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-ui-late-soft px-4 py-3.5 text-[15px] font-semibold text-ui-late">{message}</div>
  );
}
