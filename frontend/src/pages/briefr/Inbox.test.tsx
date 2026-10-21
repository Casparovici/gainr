import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { briefrApi } from "../../api/briefrClient";
import type { BriefrReport, BriefrReportDetail } from "../../api/briefrTypes";
import BriefrInbox from "./Inbox";

vi.mock("../../api/briefrClient", () => ({
  briefrApi: { listReports: vi.fn(), getReport: vi.fn(), setRead: vi.fn(), setArchived: vi.fn(), listAgents: vi.fn() },
}));
// The top row's switcher, bell and gear have their own tests and their own queries.
vi.mock("../../components/ModuleSwitcher", () => ({ default: () => null }));
vi.mock("../../components/ModuleIndicators", () => ({ default: () => null }));
vi.mock("../../components/ModuleSettingsButton", () => ({ default: () => null }));

// A fixed moment, passed in -- the page never reads the clock in these tests.
const NOW = new Date(2026, 9, 19, 8, 0);

const report = (over: Partial<BriefrReport>): BriefrReport => ({
  id: 1,
  agent: "holdings-scan",
  run_at: new Date(2026, 9, 19, 2, 14).toISOString(),
  title: "Nightly scan",
  summary: "ASML guidance cut.",
  attention: "act",
  is_read: false,
  is_archived: false,
  counts: { act: 1, watch: 1, ignore: 0 },
  ...over,
});

const detail: BriefrReportDetail = {
  ...report({}),
  source_path: "reports/holdings-scan/2026-10-19.md",
  body: "## What happened\n\nASML lowered its **guidance**.",
  items: [
    { id: 10, symbol: "ASML", asset_id: 7, verdict: "act", headline: "Q3 guidance lowered", detail: "Second cut this year.", sources: ["https://www.reuters.com/asml"], recipe: null },
    { id: 11, symbol: "XYZ", asset_id: null, verdict: "watch", headline: "Not held", detail: null, sources: [], recipe: null },
  ],
};

function renderInbox(archived = false) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[archived ? "/briefr/archive" : "/briefr"]}>
        <BriefrInbox archived={archived} now={NOW} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BriefrInbox", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(briefrApi.listAgents).mockResolvedValue([]);
  });

  it("says it's loading until the reports arrive", () => {
    vi.mocked(briefrApi.listReports).mockReturnValue(new Promise(() => {}));
    renderInbox();
    expect(screen.getByRole("status")).toHaveTextContent("Loading reports…");
  });

  it("offers a retry when the reports can't be loaded", async () => {
    vi.mocked(briefrApi.listReports).mockRejectedValueOnce(new Error("500")).mockResolvedValue([]);
    renderInbox();
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Inbox zero")).toBeInTheDocument();
  });

  it("lists the reports with their level, agent, time, summary and findings count", async () => {
    vi.mocked(briefrApi.listReports).mockResolvedValue([
      report({}),
      report({ id: 2, agent: "app-builder", title: "PR #31", attention: "info", is_read: true, summary: null, counts: { act: 0, watch: 0, ignore: 0 }, run_at: new Date(2026, 9, 18, 3, 0).toISOString() }),
    ]);
    renderInbox();

    const [first, second] = await screen.findAllByRole("article");
    expect(within(first).getByText("Act")).toBeInTheDocument();
    expect(within(first).getByText("Holdings scan")).toBeInTheDocument();
    expect(within(first).getByText("Today 02:14")).toBeInTheDocument();
    expect(within(first).getByText("ASML guidance cut.")).toBeInTheDocument();
    expect(within(first).getByText("1 act · 1 watch")).toBeInTheDocument();
    expect(within(first).getByRole("img", { name: "Unread" })).toBeInTheDocument();
    expect(within(second).getByText("Yesterday 03:00")).toBeInTheDocument();
    expect(within(second).getByText("No findings")).toBeInTheDocument();
    expect(within(second).queryByRole("img", { name: "Unread" })).not.toBeInTheDocument();
    expect(screen.getByText("1 unread · 1 to act on")).toBeInTheDocument();
    expect(briefrApi.listReports).toHaveBeenCalledWith({ archived: false, agent: null, attention: null });
  });

  it("opens a report to its findings and write-up, and marks it read", async () => {
    vi.mocked(briefrApi.listReports).mockResolvedValue([report({})]);
    vi.mocked(briefrApi.getReport).mockResolvedValue(detail);
    vi.mocked(briefrApi.setRead).mockResolvedValue(report({ is_read: true }));
    renderInbox();

    await userEvent.click(await screen.findByRole("button", { name: /Nightly scan/ }));

    expect(await screen.findByText("Q3 guidance lowered")).toBeInTheDocument();
    expect(briefrApi.setRead).toHaveBeenCalledWith(1, true);
    expect(screen.getByRole("link", { name: "ASML" })).toHaveAttribute("href", "/gainr?position=7");
    expect(screen.queryByRole("link", { name: "XYZ" })).not.toBeInTheDocument();
    const source = screen.getByRole("link", { name: /reuters\.com/ });
    expect(source).toHaveAttribute("href", "https://www.reuters.com/asml");
    expect(source).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText("What happened")).toBeInTheDocument();
    expect(screen.getByText("guidance").tagName).toBe("STRONG");
  });

  it("archives an open report", async () => {
    vi.mocked(briefrApi.listReports).mockResolvedValue([report({ is_read: true })]);
    vi.mocked(briefrApi.getReport).mockResolvedValue(detail);
    vi.mocked(briefrApi.setArchived).mockResolvedValue(report({ is_archived: true }));
    renderInbox();

    await userEvent.click(await screen.findByRole("button", { name: /Nightly scan/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Archive" }));

    expect(briefrApi.setArchived).toHaveBeenCalledWith(1, true);
    expect(briefrApi.setRead).not.toHaveBeenCalled();
  });

  it("filters by agent and by attention", async () => {
    vi.mocked(briefrApi.listAgents).mockResolvedValue([
      { agent: "app-builder", last_run_at: "2026-10-19T01:00:00Z", report_count: 1, unread_count: 0 },
      { agent: "holdings-scan", last_run_at: "2026-10-19T00:14:00Z", report_count: 3, unread_count: 1 },
    ]);
    vi.mocked(briefrApi.listReports).mockResolvedValue([]);
    renderInbox();

    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Agent" }), "holdings-scan");
    await userEvent.click(screen.getByRole("button", { name: "Watch" }));

    expect(briefrApi.listReports).toHaveBeenLastCalledWith({ archived: false, agent: "holdings-scan", attention: "watch" });
    expect(await screen.findByText("Nothing matches")).toBeInTheDocument();
  });

  it("shows the archive, where a report can go back to the inbox", async () => {
    vi.mocked(briefrApi.listReports).mockResolvedValue([report({ is_read: true, is_archived: true })]);
    vi.mocked(briefrApi.getReport).mockResolvedValue(detail);
    vi.mocked(briefrApi.setArchived).mockResolvedValue(report({ is_read: true }));
    renderInbox(true);

    expect(await screen.findByRole("heading", { name: "Archive" })).toBeInTheDocument();
    expect(briefrApi.listReports).toHaveBeenCalledWith({ archived: true, agent: null, attention: null });
    await userEvent.click(await screen.findByRole("button", { name: /Nightly scan/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Move to inbox" }));
    expect(briefrApi.setArchived).toHaveBeenCalledWith(1, false);
  });

  it("says when the archive is empty", async () => {
    vi.mocked(briefrApi.listReports).mockResolvedValue([]);
    renderInbox(true);
    expect(await screen.findByText("Nothing archived")).toBeInTheDocument();
  });
});
