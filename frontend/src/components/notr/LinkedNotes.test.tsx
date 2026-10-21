import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import LinkedNotes from "./LinkedNotes";

vi.mock("../../api/client", () => ({ api: { listAssets: vi.fn().mockResolvedValue([]) } }));
vi.mock("../../api/gardnrClient", () => ({ gardnrApi: { listPlants: vi.fn().mockResolvedValue([]) } }));
vi.mock("../../api/listrClient", () => ({ listrApi: { listRecipes: vi.fn().mockResolvedValue([]) } }));
vi.mock("../../api/notrClient", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/notrClient")>()),
  notrApi: {
    listNotes: vi.fn(),
    createNote: vi.fn(),
    updateNote: vi.fn(),
    deleteNote: vi.fn(),
    toggleTask: vi.fn(),
    listLabels: vi.fn(),
    createLabel: vi.fn(),
    uploadImage: vi.fn(),
  },
}));

const note = (over: Partial<NotrNote>): NotrNote => ({
  id: 1,
  title: "",
  body: "",
  pinned: false,
  is_archived: false,
  created_at: "2026-10-19T09:00:00Z",
  updated_at: "2026-10-19T09:00:00Z",
  assets: [{ id: 7, ticker: "ASML", name: "ASML Holding" }],
  plants: [],
  recipes: [],
  labels: [],
  ...over,
});

function renderNotes(props: React.ComponentProps<typeof LinkedNotes>) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <LinkedNotes {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(notrApi.listLabels).mockResolvedValue([]);
});

describe("LinkedNotes", () => {
  it("lists the notes linked to the position, newest first as the server orders them", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([
      note({ id: 1, title: "Thesis", body: "Monopoly on EUV." }),
      note({ id: 2, title: "", body: "Q3 call notes\nGuidance cut" }),
    ]);
    renderNotes({ assetId: 7 });

    expect(await screen.findByRole("heading", { name: "Thesis" })).toBeInTheDocument();
    // An untitled note is called by its first line.
    expect(screen.getByRole("heading", { name: "Q3 call notes" })).toBeInTheDocument();
    expect(notrApi.listNotes).toHaveBeenCalledWith({ assetId: 7, plantId: undefined, recipeId: undefined });
  });

  it("says there are no notes and how to add one", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([]);
    renderNotes({ plantId: 4 });

    expect(await screen.findByText("No notes yet. Tap Add note to write the first.")).toBeInTheDocument();
    expect(notrApi.listNotes).toHaveBeenCalledWith({ assetId: undefined, plantId: 4, recipeId: undefined });
  });

  it("shows a loading state until the notes arrive", () => {
    vi.mocked(notrApi.listNotes).mockReturnValue(new Promise(() => {}));
    renderNotes({ recipeId: 9 });
    expect(screen.getByRole("status", { name: "Loading notes…" })).toBeInTheDocument();
  });

  it("offers a retry when the notes can't be loaded", async () => {
    vi.mocked(notrApi.listNotes).mockRejectedValueOnce(new Error("500")).mockResolvedValue([note({ title: "Back again" })]);
    renderNotes({ assetId: 7 });

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load the notes.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { name: "Back again" })).toBeInTheDocument();
  });

  it("adds a note that is already linked here", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([]);
    vi.mocked(notrApi.createNote).mockResolvedValue(note({ id: 3, body: "New thought" }));
    renderNotes({ assetId: 7 });

    await userEvent.click(await screen.findByRole("button", { name: "Add note" }));
    const dialog = screen.getByRole("dialog", { name: "New note" });
    // The caller fixes what the note is about, so there is no link picker.
    expect(within(dialog).queryByRole("searchbox")).not.toBeInTheDocument();
    await userEvent.type(within(dialog).getByRole("textbox", { name: "Note text" }), "New thought");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(notrApi.createNote).toHaveBeenCalledWith(expect.objectContaining({ body: "New thought", asset_ids: [7], plant_ids: [], recipe_ids: [] })),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("opens a note to read, ticks a checkbox and pins it", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([note({ id: 1, title: "To do", body: "- [ ] call broker\n- [x] read report" })]);
    vi.mocked(notrApi.toggleTask).mockResolvedValue(note({}));
    vi.mocked(notrApi.updateNote).mockResolvedValue(note({ pinned: true }));
    renderNotes({ assetId: 7 });

    await userEvent.click(await screen.findByRole("button", { name: /To do/ }));
    const dialog = screen.getByRole("dialog", { name: "To do" });
    const boxes = within(dialog).getAllByRole("checkbox");
    await userEvent.click(boxes[0]);

    await waitFor(() => expect(notrApi.toggleTask).toHaveBeenCalledWith(1, 0, true));
    expect(boxes[0]).toBeChecked();

    await userEvent.click(within(dialog).getByRole("button", { name: "Pin" }));
    await waitFor(() => expect(notrApi.updateNote).toHaveBeenCalledWith(1, { pinned: true }));
    expect(within(dialog).getByRole("link", { name: "Open in notr" })).toHaveAttribute("href", "/notr/1");
  });

  it("edits a note in place and deletes after confirming", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([note({ id: 1, title: "Old", body: "Words" })]);
    vi.mocked(notrApi.updateNote).mockResolvedValue(note({ title: "Newer" }));
    vi.mocked(notrApi.deleteNote).mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderNotes({ assetId: 7 });

    await userEvent.click(await screen.findByRole("button", { name: /Old/ }));
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const title = screen.getByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "Newer");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(notrApi.updateNote).toHaveBeenCalledWith(1, expect.objectContaining({ title: "Newer" })));

    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("pictures are deleted too"));
    await waitFor(() => expect(notrApi.deleteNote).toHaveBeenCalledWith(1));
    confirm.mockRestore();
  });
});
