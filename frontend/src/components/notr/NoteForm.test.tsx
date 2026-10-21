import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { gardnrApi } from "../../api/gardnrClient";
import { listrApi } from "../../api/listrClient";
import { notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import NoteForm from "./NoteForm";

vi.mock("../../api/client", () => ({ api: { listAssets: vi.fn() } }));
vi.mock("../../api/gardnrClient", () => ({ gardnrApi: { listPlants: vi.fn() } }));
vi.mock("../../api/listrClient", () => ({ listrApi: { listRecipes: vi.fn() } }));
vi.mock("../../api/notrClient", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/notrClient")>()),
  notrApi: { createNote: vi.fn(), updateNote: vi.fn(), listLabels: vi.fn(), createLabel: vi.fn(), uploadImage: vi.fn() },
}));

const saved: NotrNote = {
  id: 5,
  title: "Saved",
  body: "text",
  pinned: false,
  is_archived: false,
  created_at: "2026-10-19T09:00:00Z",
  updated_at: "2026-10-19T09:00:00Z",
  assets: [],
  plants: [],
  recipes: [],
  labels: [],
};

const existing: NotrNote = {
  ...saved,
  title: "ASML thesis",
  body: "Monopoly on EUV.",
  assets: [{ id: 7, ticker: "ASML", name: "ASML Holding" }],
  labels: [{ id: 2, name: "Thesis", sort_order: 0, color: null, is_archived: false }],
};

function renderForm(props: Partial<React.ComponentProps<typeof NoteForm>> = {}) {
  const onSaved = vi.fn();
  const onCancel = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <NoteForm onSaved={onSaved} onCancel={onCancel} {...props} />
    </QueryClientProvider>,
  );
  return { onSaved, onCancel };
}

const bodyBox = () => screen.getByRole("textbox", { name: "Note text" });

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(notrApi.listLabels).mockResolvedValue([
    { id: 2, name: "Thesis", sort_order: 0, color: null, is_archived: false },
    { id: 3, name: "Idea", sort_order: 1, color: null, is_archived: false },
  ]);
  vi.mocked(notrApi.createNote).mockResolvedValue(saved);
  vi.mocked(notrApi.updateNote).mockResolvedValue(saved);
  vi.mocked(api.listAssets).mockResolvedValue([
    { id: 7, ticker: "ASML", name: "ASML Holding" },
    { id: 8, ticker: "CASH", name: "Cash" },
  ] as Awaited<ReturnType<typeof api.listAssets>>);
  vi.mocked(gardnrApi.listPlants).mockResolvedValue([
    { id: 4, name: "Tomato", area_name: "Greenhouse" },
  ] as Awaited<ReturnType<typeof gardnrApi.listPlants>>);
  vi.mocked(listrApi.listRecipes).mockResolvedValue([{ id: 9, title: "Pasta" }] as Awaited<ReturnType<typeof listrApi.listRecipes>>);
});

describe("NoteForm", () => {
  it("creates a note from the title, text, label and pin", async () => {
    const { onSaved } = renderForm();

    await userEvent.type(screen.getByRole("textbox", { name: "Title" }), "Groceries");
    await userEvent.type(bodyBox(), "Buy milk");
    await userEvent.click(await screen.findByRole("button", { name: "Idea" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Pin this note" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved));
    expect(notrApi.createNote).toHaveBeenCalledWith({
      title: "Groceries",
      body: "Buy milk",
      pinned: true,
      label_ids: [3],
      asset_ids: [],
      plant_ids: [],
      recipe_ids: [],
    });
  });

  it("cannot save an empty note", () => {
    renderForm();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("starts an edit from the note and saves it with its links", async () => {
    const { onSaved } = renderForm({ note: existing });

    expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue("ASML thesis");
    expect(bodyBox()).toHaveValue("Monopoly on EUV.");
    expect(screen.getByText("ASML")).toBeInTheDocument();

    await userEvent.type(bodyBox(), " More.");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(notrApi.updateNote).toHaveBeenCalledWith(5, {
      title: "ASML thesis",
      body: "Monopoly on EUV. More.",
      pinned: false,
      label_ids: [2],
      asset_ids: [7],
      plant_ids: [],
      recipe_ids: [],
    });
    expect(notrApi.createNote).not.toHaveBeenCalled();
  });

  it("leaves the links alone on an edit when the caller fixes them", async () => {
    renderForm({ note: existing, fixedLinks: true });

    expect(screen.queryByRole("searchbox", { name: "Link a position, plant or recipe" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(notrApi.updateNote).toHaveBeenCalled());
    const input = vi.mocked(notrApi.updateNote).mock.calls[0][1];
    expect(input).not.toHaveProperty("asset_ids");
  });

  it("links a position, a plant and a recipe from one search box, and removes a link", async () => {
    renderForm();
    const search = screen.getByRole("searchbox", { name: "Link a position, plant or recipe" });

    await userEvent.click(search);
    await userEvent.click(await screen.findByRole("button", { name: /ASML/ }));
    await userEvent.click(search);
    await userEvent.click(await screen.findByRole("button", { name: /Tomato/ }));
    await userEvent.click(search);
    await userEvent.click(await screen.findByRole("button", { name: /Pasta/ }));
    // The cash row is no position.
    await userEvent.click(search);
    expect(screen.queryByRole("button", { name: /CASH/ })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Remove Tomato" }));
    await userEvent.type(bodyBox(), "x");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(notrApi.createNote).toHaveBeenCalled());
    expect(notrApi.createNote).toHaveBeenCalledWith(expect.objectContaining({ asset_ids: [7], plant_ids: [], recipe_ids: [9] }));
  });

  it("needs a position when requireAsset is set", async () => {
    renderForm({ requireAsset: true });

    await userEvent.type(bodyBox(), "A thought");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();

    await userEvent.click(screen.getByRole("searchbox", { name: "Link a position, plant or recipe" }));
    await userEvent.click(await screen.findByRole("button", { name: /ASML/ }));

    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  describe("thesis template", () => {
    it("is offered for a new, empty note about a position, and fills in the skeleton", async () => {
      renderForm({ defaults: { asset_ids: [7] } });

      await userEvent.click(screen.getByRole("button", { name: "Start from the thesis template" }));

      expect(bodyBox()).toHaveValue("## Why I own it\n\n\n## What would make me sell\n\n\n## Risks\n\n");
      // Once there is text the button has done its job.
      expect(screen.queryByRole("button", { name: "Start from the thesis template" })).not.toBeInTheDocument();
    });

    it("is not offered without a position", () => {
      renderForm({ defaults: { plant_ids: [4] } });
      expect(screen.queryByRole("button", { name: "Start from the thesis template" })).not.toBeInTheDocument();
    });

    it("is not offered when the body already has text", () => {
      renderForm({ defaults: { asset_ids: [7], body: "Already started" } });
      expect(screen.queryByRole("button", { name: "Start from the thesis template" })).not.toBeInTheDocument();
    });

    it("is not offered when editing an existing note", () => {
      renderForm({ note: { ...existing, body: "" } });
      expect(screen.queryByRole("button", { name: "Start from the thesis template" })).not.toBeInTheDocument();
    });
  });

  it("says so when the note can't be saved, and keeps what was typed", async () => {
    vi.mocked(notrApi.createNote).mockRejectedValue(new Error("500"));
    const { onSaved } = renderForm();

    await userEvent.type(bodyBox(), "Keep me");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't save the note. Try again.");
    expect(bodyBox()).toHaveValue("Keep me");
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("cancels without saving", async () => {
    const { onCancel } = renderForm();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
    expect(notrApi.createNote).not.toHaveBeenCalled();
  });
});
