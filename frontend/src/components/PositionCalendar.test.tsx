import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { CalendarEvent, PositionCalendar } from "../api/types";
import { addDaysIso, todayIsoDate } from "../utils/format";
import PositionCalendarSection, { NextEventLine } from "./PositionCalendar";

vi.mock("../api/client", () => ({
  api: {
    getPositionCalendar: vi.fn(),
    createPositionEvent: vi.fn(),
    updatePositionEvent: vi.fn(),
    deletePositionEvent: vi.fn(),
  },
}));

const inDays = (n: number) => addDaysIso(todayIsoDate(), n);

function event(overrides: Partial<CalendarEvent>): CalendarEvent {
  return {
    id: null, source: "yahoo", kind: "earnings", date: inDays(29), end_date: null, title: "Earnings",
    is_estimate: false, time_of_day: null, eps_estimate: null, revenue_estimate: null, notes: null, ...overrides,
  };
}

const amazon: PositionCalendar = {
  currency: "USD",
  upcoming: [
    event({ time_of_day: "after_close", eps_estimate: "1.97667", revenue_estimate: "201980771440" }),
    event({ id: 5, source: "manual", kind: "investor_day", date: inDays(49), title: "Investor Day", notes: "Watch AWS margins" }),
  ],
  past: [],
  results: [
    { report_date: "2026-07-30", eps_estimate: "1.83", eps_actual: "5.75", surprise_pct: "214.21" },
    { report_date: "2026-02-05", eps_estimate: "1.95", eps_actual: "1.95", surprise_pct: "0.00" },
    { report_date: "2025-02-06", eps_estimate: "1.48", eps_actual: "1.40", surprise_pct: "-5.41" },
  ],
};

function renderWith(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("PositionCalendarSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getPositionCalendar).mockResolvedValue(amazon);
    vi.mocked(api.createPositionEvent).mockResolvedValue(event({}));
    vi.mocked(api.deletePositionEvent).mockResolvedValue(undefined);
  });

  it("lists upcoming events with timing, expectations and a countdown", async () => {
    renderWith(<PositionCalendarSection assetId={1} enabled />);
    const earnings = (await screen.findByText("Earnings")).closest("li")!;
    expect(within(earnings).getByText("after market close")).toBeInTheDocument();
    expect(within(earnings).getByText(/Expected: EPS .*1[.,]98 · revenue/)).toBeInTheDocument();
    expect(within(earnings).getByText("in 4 weeks")).toBeInTheDocument();

    const own = screen.getByText("Investor Day").closest("li")!;
    expect(within(own).getByText("added by you")).toBeInTheDocument();
    expect(within(own).getByText("Watch AWS margins")).toBeInTheDocument();
  });

  it("shows past results as beat, in line or miss", async () => {
    renderWith(<PositionCalendarSection assetId={1} enabled />);
    expect(await screen.findByText("beat +214%")).toBeInTheDocument();
    expect(screen.getByText("in line")).toBeInTheDocument();
    expect(screen.getByText("miss −5%")).toBeInTheDocument();
  });

  it("explains an empty calendar for funds and crypto", async () => {
    vi.mocked(api.getPositionCalendar).mockResolvedValue({ currency: null, upcoming: [], past: [], results: [] });
    renderWith(<PositionCalendarSection assetId={1} enabled />);
    expect(await screen.findByText(/doesn't publish company events for funds, crypto or commodities/)).toBeInTheDocument();
  });

  it("adds an own event, defaulting the title to its type", async () => {
    renderWith(<PositionCalendarSection assetId={1} enabled />);
    await userEvent.click(await screen.findByRole("button", { name: "+ Add event" }));
    await userEvent.selectOptions(screen.getByLabelText("Type"), "agm");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(api.createPositionEvent).toHaveBeenCalledWith(1, { date: todayIsoDate(), kind: "agm", title: "Shareholder meeting", notes: null }),
    );
  });

  it("deletes an own event after confirming, and never offers to delete Yahoo's", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderWith(<PositionCalendarSection assetId={1} enabled />);
    expect(await screen.findByText("Earnings")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete Earnings" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Delete Investor Day" }));
    await waitFor(() => expect(api.deletePositionEvent).toHaveBeenCalledWith(1, 5));
  });
});

describe("NextEventLine", () => {
  it("names the soonest upcoming event", async () => {
    vi.mocked(api.getPositionCalendar).mockResolvedValue(amazon);
    renderWith(<NextEventLine assetId={1} enabled />);
    expect(await screen.findByText("Earnings")).toBeInTheDocument();
    expect(screen.getByText(/in 4 weeks/)).toBeInTheDocument();
  });

  it("renders nothing when nothing is coming up", async () => {
    vi.mocked(api.getPositionCalendar).mockResolvedValue({ currency: null, upcoming: [], past: [], results: [] });
    const { container } = renderWith(<NextEventLine assetId={1} enabled />);
    await waitFor(() => expect(api.getPositionCalendar).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
