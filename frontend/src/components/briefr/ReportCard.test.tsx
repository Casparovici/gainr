import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { briefrApi } from "../../api/briefrClient";
import type { BriefrReport, BriefrReportDetail } from "../../api/briefrTypes";
import { notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import ReportCard, { reportAsNoteBody } from "./ReportCard";

vi.mock("../../api/briefrClient", () => ({ briefrApi: { getReport: vi.fn() } }));
vi.mock("../../api/notrClient", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/notrClient")>()),
  notrApi: { createNote: vi.fn() },
}));

const report: BriefrReport = {
  id: 1,
  agent: "holdings-scan",
  run_at: new Date(2026, 9, 19, 2, 14).toISOString(),
  title: "Nightly scan",
  summary: null,
  attention: "act",
  is_read: true,
  is_archived: false,
  counts: { act: 1, watch: 1, ignore: 0 },
};

const detail: BriefrReportDetail = {
  ...report,
  source_path: "reports/holdings-scan/2026-10-19.md",
  body: "## What happened\n\nASML lowered its **guidance**.",
  items: [
    { id: 10, symbol: "ASML", asset_id: 7, verdict: "act", headline: "Q3 guidance lowered", detail: "Second cut\nthis year.", sources: [], recipe: null },
    { id: 11, symbol: "XYZ", asset_id: null, verdict: "watch", headline: "Not held", detail: null, sources: [], recipe: null },
    { id: 12, symbol: "ASML", asset_id: 7, verdict: "ignore", headline: "Old news", detail: null, sources: [], recipe: null },
  ],
};

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ReportCard report={report} now={new Date(2026, 9, 19, 8, 0)} open onToggle={() => {}} onMarkUnread={() => {}} onArchive={() => {}} isBusy={false} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(briefrApi.getReport).mockResolvedValue(detail);
});

describe("reportAsNoteBody", () => {
  it("says where the note came from, lists the findings and keeps the write-up", () => {
    expect(reportAsNoteBody(detail)).toBe(
      [
        "*Saved from briefr report of 2026-10-19*",
        "- **ASML** Q3 guidance lowered: Second cut this year.\n- **XYZ** Not held\n- **ASML** Old news",
        "## What happened\n\nASML lowered its **guidance**.",
      ].join("\n\n"),
    );
  });
});

describe("Save as note", () => {
  it("creates a note linked to the resolved positions and offers to open it", async () => {
    vi.mocked(notrApi.createNote).mockResolvedValue({ id: 42 } as NotrNote);
    renderCard();
    await userEvent.click(await screen.findByRole("button", { name: "Save as note" }));
    expect(notrApi.createNote).toHaveBeenCalledWith({
      title: "Nightly scan",
      body: reportAsNoteBody(detail),
      asset_ids: [7],
    });
    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open note" })).toHaveAttribute("href", "/notr/42");
  });

  it("says so when the note can't be saved, and lets you try again", async () => {
    vi.mocked(notrApi.createNote).mockRejectedValueOnce(new Error("500")).mockResolvedValue({ id: 5 } as NotrNote);
    renderCard();
    await userEvent.click(await screen.findByRole("button", { name: "Save as note" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't save the note. Try again.");
    await userEvent.click(screen.getByRole("button", { name: "Save as note" }));
    expect(await screen.findByRole("link", { name: "Open note" })).toHaveAttribute("href", "/notr/5");
  });
});
