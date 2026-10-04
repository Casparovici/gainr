import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { Position, PositionNote } from "../api/types";
import Journal from "./Journal";

vi.mock("../api/client", () => ({
  api: {
    listJournalNotes: vi.fn(),
    listPositionNoteLabels: vi.fn(),
    createPositionNoteLabel: vi.fn(),
    getPositions: vi.fn(),
    createJournalNote: vi.fn(),
    updateJournalNote: vi.fn(),
    deleteJournalNote: vi.fn(),
  },
}));
vi.mock("../hooks/usePortfolio", () => ({
  usePortfolio: () => ({ portfolioId: 1, portfolios: [{ id: 1, name: "Main" }], setPortfolioId: vi.fn(), isLoading: false }),
}));

function position(asset_id: number, ticker: string, name: string): Position {
  return { asset_id, ticker, name } as Position;
}

const sharedNote: PositionNote = {
  id: 7,
  assets: [
    { id: 1, ticker: "AMZN", name: "Amazon.com Inc" },
    { id: 9, ticker: "MSFT", name: "Microsoft Corp" },
  ],
  title: "Cloud capex",
  body: "Everyone is spending.",
  created_at: "2026-09-30T10:00:00Z",
  updated_at: "2026-09-30T10:00:00Z",
  labels: [],
};

function renderJournal() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Journal />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Journal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listJournalNotes).mockResolvedValue([sharedNote]);
    vi.mocked(api.listPositionNoteLabels).mockResolvedValue([]);
    vi.mocked(api.getPositions).mockResolvedValue([
      position(1, "AMZN", "Amazon.com Inc"),
      position(2, "GOOGL", "Alphabet Inc Class A"),
      position(0, "CASH", "Cash"),
    ]);
    vi.mocked(api.createJournalNote).mockResolvedValue(sharedNote);
    vi.mocked(api.updateJournalNote).mockResolvedValue(sharedNote);
  });

  it("shows every position a note is linked to", async () => {
    renderJournal();
    const tile = (await screen.findByText("Cloud capex")).closest("article")!;
    expect(within(tile).getByRole("link", { name: "AMZN" })).toHaveAttribute("href", "/?position=1");
    expect(within(tile).getByRole("link", { name: "MSFT" })).toHaveAttribute("href", "/?position=9");
  });

  it("links a new journal item to several positions via checkboxes", async () => {
    renderJournal();
    await userEvent.click(await screen.findByRole("button", { name: "+ Add journal item" }));
    await userEvent.type(screen.getByPlaceholderText("Title"), "Big tech");
    await userEvent.type(screen.getByPlaceholderText(/What's on your mind/), "Both cheap.");

    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    expect(screen.queryByRole("checkbox", { name: /CASH/ })).not.toBeInTheDocument();

    await userEvent.click(await screen.findByRole("checkbox", { name: /AMZN/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /GOOGL/ }));
    expect(screen.getByText("2 selected")).toBeInTheDocument();
    await userEvent.click(save);

    await waitFor(() =>
      expect(api.createJournalNote).toHaveBeenCalledWith({ title: "Big tech", body: "Both cheap.", label_ids: [], asset_ids: [1, 2] }),
    );
  });

  it("keeps a link to a position outside this portfolio when editing", async () => {
    renderJournal();
    const tile = (await screen.findByText("Cloud capex")).closest("article")!;
    await userEvent.click(within(tile).getByRole("button", { name: "Edit" }));

    const msft = await screen.findByRole("checkbox", { name: /MSFT/ });
    expect(msft).toBeChecked();
    expect(screen.getByText("(not in this portfolio)")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /AMZN/ })).toBeChecked();

    await userEvent.click(screen.getByRole("checkbox", { name: /GOOGL/ }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(api.updateJournalNote).toHaveBeenCalledWith(7, expect.objectContaining({ asset_ids: [1, 9, 2] })),
    );
  });
});
