import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import NotePage from "./NotePage";

vi.mock("../../api/client", () => ({ api: { listAssets: vi.fn().mockResolvedValue([]) } }));
vi.mock("../../api/gardnrClient", () => ({ gardnrApi: { listPlants: vi.fn().mockResolvedValue([]) } }));
vi.mock("../../api/listrClient", () => ({ listrApi: { listRecipes: vi.fn().mockResolvedValue([]) } }));
vi.mock("../../api/notrClient", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/notrClient")>()),
  notrApi: {
    getNote: vi.fn(),
    createNote: vi.fn(),
    updateNote: vi.fn(),
    deleteNote: vi.fn(),
    toggleTask: vi.fn(),
    listLabels: vi.fn(),
    createLabel: vi.fn(),
    uploadImage: vi.fn(),
  },
}));
vi.mock("../../components/ModuleSwitcher", () => ({ default: () => null }));
vi.mock("../../components/ModuleIndicators", () => ({ default: () => null }));
vi.mock("../../components/ModuleSettingsButton", () => ({ default: () => null }));

const note = (over: Partial<NotrNote> = {}): NotrNote => ({
  id: 5,
  title: "Shopping",
  body: "- [ ] milk\n- [x] bread",
  pinned: false,
  is_archived: false,
  created_at: "2026-10-19T09:00:00Z",
  updated_at: "2026-10-19T09:00:00Z",
  assets: [{ id: 7, ticker: "ASML", name: "ASML Holding" }],
  plants: [{ id: 4, name: "Tomato" }],
  recipes: [{ id: 9, title: "Pasta" }],
  labels: [{ id: 2, name: "Home", sort_order: 0, color: null, is_archived: false }],
  ...over,
});

function renderAt(path: string) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/notr" element={<p>notes list</p>} />
          <Route path="/notr/archive" element={<p>archive list</p>} />
          <Route path="/notr/new" element={<NotePage />} />
          <Route path="/notr/:id" element={<NotePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(notrApi.listLabels).mockResolvedValue([]);
  vi.mocked(notrApi.getNote).mockResolvedValue(note());
});

describe("NotePage reading", () => {
  it("shows the title, labels, body and links that go to their targets", async () => {
    renderAt("/notr/5");

    expect(await screen.findByRole("heading", { name: "Shopping" })).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("milk")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ASML" })).toHaveAttribute("href", "/gainr?position=7");
    expect(screen.getByRole("link", { name: "Tomato" })).toHaveAttribute("href", "/gardnr/plants");
    expect(screen.getByRole("link", { name: "Pasta" })).toHaveAttribute("href", "/listr/recept/9");
    expect(notrApi.getNote).toHaveBeenCalledWith(5);
  });

  it("ticks a checkbox through the server and shows it at once", async () => {
    vi.mocked(notrApi.toggleTask).mockResolvedValue(note({ body: "- [x] milk\n- [x] bread" }));
    renderAt("/notr/5");

    const [milk] = await screen.findAllByRole("checkbox");
    await userEvent.click(milk);

    await waitFor(() => expect(notrApi.toggleTask).toHaveBeenCalledWith(5, 0, true));
    // The text re-renders, so look the box up again.
    expect(screen.getAllByRole("checkbox")[0]).toBeChecked();
  });

  it("puts the checkbox back and says so when the server refuses", async () => {
    vi.mocked(notrApi.toggleTask).mockRejectedValue(new Error("500"));
    renderAt("/notr/5");

    const [milk] = await screen.findAllByRole("checkbox");
    await userEvent.click(milk);

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't tick that box. Try again.");
    await waitFor(() => expect(screen.getAllByRole("checkbox")[0]).not.toBeChecked());
  });

  it("pins from the actions sheet", async () => {
    vi.mocked(notrApi.updateNote).mockResolvedValue(note({ pinned: true }));
    renderAt("/notr/5");

    await userEvent.click(await screen.findByRole("button", { name: "More actions" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Pin" }));

    await waitFor(() => expect(notrApi.updateNote).toHaveBeenCalledWith(5, { pinned: true }));
  });

  it("archives and goes back to the list", async () => {
    vi.mocked(notrApi.updateNote).mockResolvedValue(note({ is_archived: true }));
    renderAt("/notr/5");

    await userEvent.click(await screen.findByRole("button", { name: "More actions" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Archive note" }));

    await waitFor(() => expect(notrApi.updateNote).toHaveBeenCalledWith(5, { is_archived: true }));
    expect(await screen.findByText("notes list")).toBeInTheDocument();
  });

  it("deletes after a confirmation that says what is lost, then returns to the list", async () => {
    vi.mocked(notrApi.deleteNote).mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderAt("/notr/5");

    await userEvent.click(await screen.findByRole("button", { name: "More actions" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }));

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("pictures are deleted too"));
    await waitFor(() => expect(notrApi.deleteNote).toHaveBeenCalledWith(5));
    expect(await screen.findByText("notes list")).toBeInTheDocument();
    confirm.mockRestore();
  });

  it("does not delete when the confirmation is declined", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderAt("/notr/5");

    await userEvent.click(await screen.findByRole("button", { name: "More actions" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }));

    expect(notrApi.deleteNote).not.toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("edits in place", async () => {
    vi.mocked(notrApi.updateNote).mockResolvedValue(note({ title: "Renamed" }));
    renderAt("/notr/5");

    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const title = screen.getByRole("textbox", { name: "Title" });
    expect(title).toHaveValue("Shopping");
    await userEvent.clear(title);
    await userEvent.type(title, "Renamed");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(notrApi.updateNote).toHaveBeenCalledWith(5, expect.objectContaining({ title: "Renamed", asset_ids: [7] })));
    // Back to reading.
    expect(await screen.findByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("says the note wasn't found for an unknown id", async () => {
    vi.mocked(notrApi.getNote).mockRejectedValue(new Error("404 Not Found: {}"));
    renderAt("/notr/999");

    expect(await screen.findByText("Note not found")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to notes" })).toHaveAttribute("href", "/notr");
  });

  it("offers a retry when the note can't be loaded", async () => {
    vi.mocked(notrApi.getNote).mockRejectedValueOnce(new Error("500 Server Error")).mockResolvedValue(note());
    renderAt("/notr/5");

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load this note.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { name: "Shopping" })).toBeInTheDocument();
  });

  it("links an archived note back to the archive", async () => {
    vi.mocked(notrApi.getNote).mockResolvedValue(note({ is_archived: true }));
    renderAt("/notr/5");

    await screen.findByRole("heading", { name: "Shopping" });
    expect(screen.getByRole("link", { name: "Notes" })).toHaveAttribute("href", "/notr/archive");
  });
});

describe("NotePage writing", () => {
  it("starts a note linked to what the URL says and opens it once saved", async () => {
    vi.mocked(notrApi.createNote).mockResolvedValue(note({ id: 21, title: "Fresh" }));
    vi.mocked(notrApi.getNote).mockResolvedValue(note({ id: 21, title: "Fresh" }));
    renderAt("/notr/new?asset=7&plant=4&recipe=9");

    expect(screen.getByRole("heading", { name: "New note" })).toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: "Note text" }), "A thought");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(notrApi.createNote).toHaveBeenCalledWith(expect.objectContaining({ body: "A thought", asset_ids: [7], plant_ids: [4], recipe_ids: [9] })),
    );
    expect(await screen.findByRole("heading", { name: "Fresh" })).toBeInTheDocument();
    expect(notrApi.getNote).toHaveBeenCalledWith(21);
  });

  it("ignores a preset that isn't an id", async () => {
    vi.mocked(notrApi.createNote).mockResolvedValue(note());
    renderAt("/notr/new?asset=abc");

    await userEvent.type(screen.getByRole("textbox", { name: "Note text" }), "Plain");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(notrApi.createNote).toHaveBeenCalledWith(expect.objectContaining({ asset_ids: [] })));
  });
});
