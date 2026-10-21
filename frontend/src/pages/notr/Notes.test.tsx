import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import Notes from "./Notes";

vi.mock("../../api/notrClient", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/notrClient")>()),
  notrApi: { listNotes: vi.fn(), listLabels: vi.fn() },
}));
// The top row's switcher, bell and gear have their own tests and their own queries.
vi.mock("../../components/ModuleSwitcher", () => ({ default: () => null }));
vi.mock("../../components/ModuleIndicators", () => ({ default: () => null }));
vi.mock("../../components/ModuleSettingsButton", () => ({ default: () => null }));

const note = (over: Partial<NotrNote>): NotrNote => ({
  id: 1,
  title: "",
  body: "",
  pinned: false,
  is_archived: false,
  created_at: "2026-10-19T09:00:00Z",
  updated_at: "2026-10-19T09:00:00Z",
  assets: [],
  plants: [],
  recipes: [],
  labels: [],
  ...over,
});

const labels = [
  { id: 2, name: "Ideas", sort_order: 0, color: null, is_archived: false },
  { id: 3, name: "Garden", sort_order: 1, color: "#5E7F12", is_archived: false },
];

function renderNotes(archived = false) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/notr"]}>
        <Routes>
          <Route path="/notr" element={<Notes archived={archived} />} />
          <Route path="/notr/new" element={<p>new note page</p>} />
          <Route path="/notr/:id" element={<p>note page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(notrApi.listLabels).mockResolvedValue([]);
});

describe("Notes", () => {
  it("shows loading skeletons until the notes arrive", () => {
    vi.mocked(notrApi.listNotes).mockReturnValue(new Promise(() => {}));
    renderNotes();
    expect(screen.getByRole("status", { name: "Loading notes…" })).toBeInTheDocument();
  });

  it("lists notes as cards, with the first line standing in for a missing title", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([
      note({ id: 1, title: "Tomato plan", body: "Plant in May", labels: [labels[1]] }),
      note({ id: 2, body: "Call the plumber\nAbout the leak" }),
    ]);
    renderNotes();

    expect(await screen.findByRole("heading", { name: "Tomato plan" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Call the plumber" })).toBeInTheDocument();
    expect(screen.getByText("About the leak")).toBeInTheDocument();
    expect(screen.getByText("2 notes")).toBeInTheDocument();
    expect(notrApi.listNotes).toHaveBeenCalledWith({ archived: false, q: "", labelId: undefined });
  });

  it("opens a note when its card is tapped", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([note({ id: 12, title: "Tap me" })]);
    renderNotes();

    await userEvent.click(await screen.findByRole("link", { name: /Tap me/ }));

    expect(screen.getByText("note page")).toBeInTheDocument();
  });

  it("groups pinned notes above the rest", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([
      note({ id: 1, title: "Important", pinned: true }),
      note({ id: 2, title: "Casual" }),
    ]);
    renderNotes();

    expect(await screen.findByRole("heading", { name: "Pinned" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Others" })).toBeInTheDocument();
  });

  it("searches after a pause in typing", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([note({ title: "Anything" })]);
    renderNotes();
    await screen.findByRole("heading", { name: "Anything" });

    await userEvent.type(screen.getByRole("searchbox", { name: "Search notes" }), "plumber");

    await waitFor(() => expect(notrApi.listNotes).toHaveBeenLastCalledWith({ archived: false, q: "plumber", labelId: undefined }));
    // Not once per keystroke.
    expect(vi.mocked(notrApi.listNotes).mock.calls.filter(([f]) => f?.q && f.q !== "plumber")).toHaveLength(0);
  });

  it("filters by label and clears the filter on a second tap", async () => {
    vi.mocked(notrApi.listLabels).mockResolvedValue(labels);
    vi.mocked(notrApi.listNotes).mockResolvedValue([note({ title: "A note" })]);
    renderNotes();

    const garden = await screen.findByRole("button", { name: "Garden" });
    await userEvent.click(garden);
    await waitFor(() => expect(notrApi.listNotes).toHaveBeenLastCalledWith({ archived: false, q: "", labelId: 3 }));
    expect(garden).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(garden);
    await waitFor(() => expect(notrApi.listNotes).toHaveBeenLastCalledWith({ archived: false, q: "", labelId: undefined }));
  });

  it("tells a new reader how to write the first note", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([]);
    renderNotes();

    expect(await screen.findByText("No notes yet")).toBeInTheDocument();
    expect(screen.getByText("Tap + New note to write the first one.")).toBeInTheDocument();
  });

  it("says nothing matched when a search finds nothing", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValueOnce([note({ title: "Seen" })]).mockResolvedValue([]);
    renderNotes();
    await screen.findByRole("heading", { name: "Seen" });

    await userEvent.type(screen.getByRole("searchbox", { name: "Search notes" }), "zzz");

    expect(await screen.findByText("No notes match your search or label.")).toBeInTheDocument();
    expect(screen.queryByText("Tap + New note to write the first one.")).not.toBeInTheDocument();
  });

  it("shows the archive with its own title and empty state", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([]);
    renderNotes(true);

    expect(await screen.findByText("Nothing archived")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Archive" })).toBeInTheDocument();
    expect(notrApi.listNotes).toHaveBeenCalledWith({ archived: true, q: "", labelId: undefined });
    expect(screen.queryByRole("button", { name: "New note" })).not.toBeInTheDocument();
  });

  it("offers a retry when the notes can't be loaded", async () => {
    vi.mocked(notrApi.listNotes).mockRejectedValueOnce(new Error("500")).mockResolvedValue([note({ title: "Recovered" })]);
    renderNotes();

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load your notes.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { name: "Recovered" })).toBeInTheDocument();
  });

  it("starts a new note from the button", async () => {
    vi.mocked(notrApi.listNotes).mockResolvedValue([]);
    renderNotes();
    await screen.findByText("No notes yet");

    // The header button (tablet and up) and the phone's floating button both exist.
    await userEvent.click(screen.getAllByRole("button", { name: "New note" })[0]);

    expect(screen.getByText("new note page")).toBeInTheDocument();
  });
});
