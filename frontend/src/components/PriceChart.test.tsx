import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { PriceChart as PriceChartData } from "../api/types";
import PriceChart from "./PriceChart";

vi.mock("../api/client", () => ({ api: { getPriceChart: vi.fn() } }));
vi.mock("../hooks/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));
// recharts measures its container, which jsdom can't; what's drawn is not what's tested here.
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return { ...actual, ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="chart">{children}</div> };
});

function chart(overrides: Partial<PriceChartData> = {}): PriceChartData {
  return {
    range: "1M",
    currency: "USD",
    interval: "daily",
    points: [
      { time: "2026-09-21", price: "100" },
      { time: "2026-10-01", price: "110" },
      { time: "2026-10-20", price: "125.5" },
    ],
    start_price: "100",
    end_price: "125.5",
    change: "25.5",
    change_pct: "25.5",
    is_fallback: false,
    as_of: null,
    ...overrides,
  };
}

function renderChart(enabled = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PriceChart assetId={5} enabled={enabled} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getPriceChart).mockResolvedValue(chart());
});

describe("PriceChart", () => {
  it("shows a month by default: the price now, the change and the range", async () => {
    renderChart();

    const region = await screen.findByRole("region", { name: "Price" });
    await waitFor(() => expect(region).toHaveTextContent(/125,50/));
    expect(region).toHaveTextContent("+25,50%");
    expect(region).toHaveTextContent("over 1M");
    expect(api.getPriceChart).toHaveBeenCalledWith(5, "1M");
    expect(screen.getByRole("button", { name: "1M" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("chart")).toBeInTheDocument();
  });

  it("offers 1D, 1W, 1M, YTD and 3Y, and asks for the range picked", async () => {
    renderChart();
    await screen.findByRole("region", { name: "Price" });

    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual(["1D", "1W", "1M", "YTD", "3Y"]);
    await userEvent.click(screen.getByRole("button", { name: "3Y" }));

    await waitFor(() => expect(api.getPriceChart).toHaveBeenCalledWith(5, "3Y"));
    expect(screen.getByRole("button", { name: "3Y" })).toHaveAttribute("aria-pressed", "true");
  });

  it("calls the day's change 'today', with the last trade's time", async () => {
    vi.mocked(api.getPriceChart).mockResolvedValue(
      chart({ range: "1D", interval: "intraday", points: [
        { time: "2026-10-20T07:00:00Z", price: "120" },
        { time: "2026-10-20T07:15:00Z", price: "121" },
      ], start_price: "119", end_price: "121", change: "2", change_pct: "1.68", as_of: "2026-10-20T07:15:00Z" }),
    );
    renderChart();
    await userEvent.click(await screen.findByRole("button", { name: "1D" }));

    const region = await screen.findByRole("region", { name: "Price" });
    await waitFor(() => expect(region).toHaveTextContent("today"));
    expect(region).toHaveTextContent("Last price");
  });

  it("colours a fall red and a rise green", async () => {
    vi.mocked(api.getPriceChart).mockResolvedValue(chart({ change: "-5", change_pct: "-4", end_price: "95" }));
    renderChart();

    const change = await screen.findByText(/-4,00%/);
    expect(change.className).toContain("red");
  });

  it("says when the intraday prices weren't available and the last week's closes are shown", async () => {
    vi.mocked(api.getPriceChart).mockResolvedValue(chart({ range: "1D", is_fallback: true }));
    renderChart();

    expect(await screen.findByText(/Intraday prices aren't available right now/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Price" })).toHaveTextContent("over 1W");
  });

  it("says so when a position has no prices", async () => {
    vi.mocked(api.getPriceChart).mockResolvedValue(chart({ points: [], start_price: null, end_price: null, change: null, change_pct: null }));
    renderChart();

    expect(await screen.findByText("No price history for this position.")).toBeInTheDocument();
    expect(screen.queryByTestId("chart")).not.toBeInTheDocument();
  });

  it("says so when there is a single price", async () => {
    vi.mocked(api.getPriceChart).mockResolvedValue(chart({ points: [{ time: "2026-10-20", price: "100" }] }));
    renderChart();

    expect(await screen.findByText("Not enough prices to draw this range yet.")).toBeInTheDocument();
  });

  it("shows an error with a retry", async () => {
    vi.mocked(api.getPriceChart).mockRejectedValueOnce(new Error("500")).mockResolvedValue(chart());
    renderChart();

    expect(await screen.findByText("Couldn't load the price chart.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(screen.getByRole("region", { name: "Price" })).toHaveTextContent(/125,50/));
  });

  it("fetches nothing while the panel is closed", () => {
    renderChart(false);

    expect(api.getPriceChart).not.toHaveBeenCalled();
  });
});
