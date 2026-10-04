import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import NewsSourcesEditor from "./NewsSourcesEditor";

vi.mock("../api/client", () => ({
  api: { getNewsSourceCatalog: vi.fn(), updateNewsSources: vi.fn() },
}));

const grid = [
  { key: "industry:utilities-renewable", label: "Utilities – Renewable" },
  { key: "industry:solar", label: "Solar" },
];

function renderEditor(sources = grid) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <NewsSourcesEditor assetId={3} sources={sources} />
    </QueryClientProvider>,
  );
}

describe("NewsSourcesEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getNewsSourceCatalog).mockResolvedValue({
      markets: [{ key: "ticker:GC=F", label: "Gold (futures)" }],
      sectors: [{ key: "sector:utilities", label: "Utilities" }],
      industries: [{ key: "industry:aerospace-defense", label: "Aerospace & Defense", sector: "Industrials" }],
    });
    vi.mocked(api.updateNewsSources).mockResolvedValue({ window_days: 7, items: [], sources: [] });
  });

  it("shows the current sources and removes one", async () => {
    renderEditor();
    expect(screen.getByText("Also from:")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Stop showing news from Solar" }));
    expect(api.updateNewsSources).toHaveBeenCalledWith(3, ["industry:utilities-renewable"]);
  });

  it("adds a source picked from the catalogue", async () => {
    renderEditor();
    await userEvent.click(screen.getByRole("button", { name: "+ Add source" }));
    const select = screen.getByLabelText("News source");
    await waitFor(() => expect(select).toBeEnabled());
    await userEvent.selectOptions(select, "industry:aerospace-defense");
    expect(api.updateNewsSources).toHaveBeenCalledWith(3, ["industry:utilities-renewable", "industry:solar", "industry:aerospace-defense"]);
  });

  it("adds any Yahoo symbol as a source", async () => {
    renderEditor([]);
    expect(screen.getByText("Only this holding's own news.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "+ Add source" }));
    const select = screen.getByLabelText("News source");
    await waitFor(() => expect(select).toBeEnabled());
    await userEvent.selectOptions(select, "__other_symbol__");
    await userEvent.type(screen.getByLabelText("Yahoo symbol"), "NVDA");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(api.updateNewsSources).toHaveBeenCalledWith(3, ["ticker:NVDA"]);
  });
});
