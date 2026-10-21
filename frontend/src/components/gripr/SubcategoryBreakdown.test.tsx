import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { griprApi } from "../../api/griprClient";
import SubcategoryBreakdown from "./SubcategoryBreakdown";

vi.mock("../../api/griprClient", () => ({ griprApi: { getSubcategoryBreakdown: vi.fn() } }));

function renderIt(props: Partial<React.ComponentProps<typeof SubcategoryBreakdown>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SubcategoryBreakdown categoryId={1} period="2026-10-01" color="#2a78d6" {...props} />
    </QueryClientProvider>,
  );
}

describe("SubcategoryBreakdown", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows each subcategory with its share, and what is filed on the category itself", async () => {
    vi.mocked(griprApi.getSubcategoryBreakdown).mockResolvedValue([
      { category_id: 11, name: "Markt", amount: "40.00" },
      { category_id: 1, name: "Boodschappen", amount: "10.00" },
    ]);

    renderIt();

    expect(await screen.findByText("Markt")).toBeInTheDocument();
    expect(screen.getByText(/80%/)).toBeInTheDocument();
    expect(screen.getByText("Not in a subcategory")).toBeInTheDocument();
  });

  it("hands a clicked subcategory to onSelect", async () => {
    vi.mocked(griprApi.getSubcategoryBreakdown).mockResolvedValue([{ category_id: 11, name: "Markt", amount: "40.00" }]);
    const onSelect = vi.fn();

    renderIt({ onSelect });
    await userEvent.click(await screen.findByRole("button", { name: /Markt/ }));

    expect(onSelect).toHaveBeenCalledWith(11);
  });

  it("explains an empty split and an unsorted one", async () => {
    vi.mocked(griprApi.getSubcategoryBreakdown).mockResolvedValue([{ category_id: 1, name: "Boodschappen", amount: "10.00" }]);

    renderIt();

    expect(await screen.findByText(/Nothing is filed under a subcategory yet/)).toBeInTheDocument();
  });

  it("says so when it can't load", async () => {
    vi.mocked(griprApi.getSubcategoryBreakdown).mockRejectedValue(new Error("boom"));

    renderIt();

    expect(await screen.findByText(/Couldn't load the subcategories/)).toBeInTheDocument();
  });
});
