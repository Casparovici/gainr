import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { notrApi } from "../api/notrClient";
import type { NotrLabel, NotrNote } from "../api/notrTypes";
import Journal from "./Journal";

vi.mock("../api/notrClient", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/notrClient")>()),
  notrApi: { listNotes: vi.fn(), listLabels: vi.fn(), deleteNote: vi.fn() },
}));
vi.mock("../hooks/usePortfolio", () => ({
  usePortfolio: () => ({ portfolioId: 1, portfolios: [{ id: 1, name: "Main" }], setPortfolioId: vi.fn(), isLoading: false }),
  useSelectedPortfolioId: () => 1,
}));
// The form has its own tests; here it only has to be opened with the right props.
vi.mock("../components/notr/NoteForm", () => ({
  default: ({ note, requireAsset, onCancel, onSaved }: { note?: NotrNote; requireAsset?: boolean; onCancel: () => void; onSaved: (n: NotrNote) => void }) => (
    <div data-testid="note-form" data-require-asset={String(!!requireAsset)} data-note={note?.id ?? "new"}>
      <button type="button" onClick={onCancel}>cancel form</button>
      <button type="button" onClick={() => onSaved({} as NotrNote)}>saved form</button>
    </div>
  ),
}));

const note = (over: Partial<NotrNote>): NotrNote => ({
  id: 7,
  title: "Cloud capex",
  body: "Everyone is **spending**.",
  pinned: false,
  is_archived: false,
  created_at: "2026-09-30T10:00:00Z",
  updated_at: "2026-09-30T10:00:00Z",
  assets: [
    { id: 1, ticker: "AMZN", name: "Amazon.com Inc" },
    { id: 9, ticker: "MSFT", name: "Microsoft Corp" },
  ],
  plants: [],
  recipes: [],
  labels: [],
  ...over,
});

const label = (id: number, name: string): NotrLabel => ({ id, name, sort_order: id, color: null, is_archived: false });

function renderJournal() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
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
    vi.mocked(notrApi.listNotes).mockResolvedValue([note({})]);
    vi.mocked(notrApi.listLabels).mockResolvedValue([]);
    vi.mocked(notrApi.deleteNote).mockResolvedValue(undefined);
  });
  afterEach(() => vi.restoreAllMocks());

  it("lists only the notes about positions, and shows every position a note is linked to", async () => {
    renderJournal();
    const tile = (await screen.findByText("Cloud capex")).closest("article")!;
    expect(notrApi.listNotes).toHaveBeenCalledWith({ positionsOnly: true });
    expect(within(tile).getByRole("link", { name: "AMZN" })).toHaveAttribute("href", "/gainr?position=1");
    expect(within(tile).getByRole("link", { name: "MSFT" })).toHaveAttribute("href", "/gainr?position=9");
    // The body is Markdown.
    expect(within(tile).getByText("spending").tagName).toBe("STRONG");
  });

  it("shows an untitled note by its body, and names it by the first line when deleting", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    vi.mocked(notrApi.listNotes).mockResolvedValue([note({ title: "", body: "## Why I own it\n\nCheap.", assets: [{ id: 1, ticker: "AMZN", name: "Amazon.com Inc" }] })]);
    renderJournal();
    const tile = (await screen.findByText("Cheap.")).closest("article")!;
    expect(within(tile).getAllByRole("heading")).toHaveLength(1);
    await userEvent.click(within(tile).getByRole("button", { name: "Delete" }));
    expect(confirmSpy).toHaveBeenCalledWith("Delete “Why I own it”?");
  });

  it("filters by label", async () => {
    vi.mocked(notrApi.listLabels).mockResolvedValue([label(1, "Thesis"), label(2, "Watch")]);
    vi.mocked(notrApi.listNotes).mockResolvedValue([
      note({ id: 1, title: "A thesis", labels: [label(1, "Thesis")] }),
      note({ id: 2, title: "Just watching", labels: [label(2, "Watch")] }),
    ]);
    renderJournal();
    await screen.findByText("A thesis");
    await userEvent.click(screen.getByRole("button", { name: "Watch" }));
    expect(screen.queryByText("A thesis")).not.toBeInTheDocument();
    expect(screen.getByText("Just watching")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Thesis" }));
    await userEvent.click(screen.getByRole("button", { name: "Watch" }));
    expect(screen.getByText("Just watching")).toBeInTheDocument();
  });

  it("opens the note form in a sheet, with a position required, to add and to edit", async () => {
    renderJournal();
    await userEvent.click(await screen.findByRole("button", { name: "+ Add journal item" }));
    const dialog = screen.getByRole("dialog", { name: "Add journal item" });
    expect(within(dialog).getByTestId("note-form")).toHaveAttribute("data-require-asset", "true");
    expect(within(dialog).getByTestId("note-form")).toHaveAttribute("data-note", "new");
    await userEvent.click(within(dialog).getByRole("button", { name: "saved form" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    const tile = screen.getByText("Cloud capex").closest("article")!;
    await userEvent.click(within(tile).getByRole("button", { name: "Edit" }));
    expect(screen.getByRole("dialog", { name: "Edit journal item" })).toBeInTheDocument();
    expect(screen.getByTestId("note-form")).toHaveAttribute("data-note", "7");
    await userEvent.click(screen.getByRole("button", { name: "cancel form" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("names the other positions in the delete confirmation, and deletes once confirmed", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderJournal();
    const tile = (await screen.findByText("Cloud capex")).closest("article")!;
    await userEvent.click(within(tile).getByRole("button", { name: "Delete" }));
    expect(confirmSpy).toHaveBeenCalledWith("Delete “Cloud capex”? It's linked to AMZN, MSFT.");
    await waitFor(() => expect(notrApi.deleteNote).toHaveBeenCalledWith(7));
  });

  it("does not delete when the confirmation is declined", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    renderJournal();
    const tile = (await screen.findByText("Cloud capex")).closest("article")!;
    await userEvent.click(within(tile).getByRole("button", { name: "Delete" }));
    expect(notrApi.deleteNote).not.toHaveBeenCalled();
  });

  it("says when there are no entries yet", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([]);
    renderJournal();
    expect(await screen.findByText(/No journal entries yet/)).toBeInTheDocument();
  });

  it("offers a retry when the journal can't be loaded", async () => {
    vi.mocked(notrApi.listNotes).mockRejectedValueOnce(new Error("500")).mockResolvedValue([note({})]);
    renderJournal();
    expect(await screen.findByText("Couldn't load the journal.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Cloud capex")).toBeInTheDocument();
  });
});
