import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { griprApi } from "../../api/griprClient";
import PeriodSwitcher, { formatPeriodLabel } from "./PeriodSwitcher";

vi.mock("../../api/griprClient", () => ({
  griprApi: {
    getSettings: vi.fn(() => Promise.resolve({ period_start_day: 25 })),
    updateSettings: vi.fn((input: { period_start_day: number }) => Promise.resolve(input)),
    getBanks: vi.fn(() => Promise.resolve({ configured: false, connections: [], rules: [] })),
    listAccounts: vi.fn(() => Promise.resolve([])),
  },
}));

describe("formatPeriodLabel", () => {
  it("renders a plain month/year label when startDay is 1", () => {
    expect(formatPeriodLabel("2026-03-01", 1)).toBe("March 2026");
  });

  it("renders a date-range label for any other start day", () => {
    expect(formatPeriodLabel("2026-08-25", 25)).toBe("25 Aug – 24 Sept 2026");
  });

  it("renders the range's own year, not the start date's, across a year boundary", () => {
    expect(formatPeriodLabel("2026-12-25", 25)).toBe("25 Dec – 24 Jan 2027");
  });
});

function renderSwitcher(onChange: (periodStart: string) => void) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PeriodSwitcher periodStart="2026-09-25" startDay={25} onChange={onChange} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PeriodSwitcher", () => {
  it("shows the current period's label", () => {
    renderSwitcher(vi.fn());
    expect(screen.getByText("25 Sept – 24 Oct 2026")).toBeInTheDocument();
  });

  it("steps one period back when the previous button is clicked", async () => {
    const onChange = vi.fn();
    renderSwitcher(onChange);
    await userEvent.click(screen.getByLabelText("Previous period"));
    expect(onChange).toHaveBeenCalledWith("2026-08-25");
  });

  it("steps one period forward when the next button is clicked", async () => {
    const onChange = vi.fn();
    renderSwitcher(onChange);
    await userEvent.click(screen.getByLabelText("Next period"));
    expect(onChange).toHaveBeenCalledWith("2026-10-25");
  });

  it("opens gripr's settings from the gear button, every section folded until its title is tapped", async () => {
    renderSwitcher(vi.fn());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Settings"));

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    const period = screen.getByRole("button", { name: "Period" });
    expect(period).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "Banks" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByLabelText("Period start day")).not.toBeInTheDocument();

    await userEvent.click(period);
    expect(await screen.findByDisplayValue("25")).toHaveAccessibleName("Period start day");
  });

  it("lands on the period containing today after the start day changes", async () => {
    const onChange = vi.fn();
    renderSwitcher(onChange);
    await userEvent.click(screen.getByLabelText("Settings"));
    await userEvent.click(screen.getByRole("button", { name: "Period" }));
    const input = await screen.findByDisplayValue("25");

    await userEvent.clear(input);
    await userEvent.type(input, "1");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(griprApi.updateSettings).toHaveBeenCalledWith({ period_start_day: 1 });
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
    expect(onChange.mock.calls[0][0]).toMatch(/^\d{4}-\d{2}-01$/);
  });

  it("closes the settings with the close button", async () => {
    renderSwitcher(vi.fn());
    await userEvent.click(screen.getByLabelText("Settings"));
    await userEvent.click(screen.getByRole("button", { name: "Close settings" }));
    expect(screen.queryByRole("heading", { name: "Settings" })).not.toBeInTheDocument();
  });
});
