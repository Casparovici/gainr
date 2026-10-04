import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { gardnrApi } from "../../api/gardnrClient";
import GardnrBottomNav from "./GardnrBottomNav";

vi.mock("../../api/gardnrClient", () => ({ gardnrApi: { listPlants: vi.fn() } }));

function renderNav(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <GardnrBottomNav />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GardnrBottomNav", () => {
  it("marks the current section and counts overdue tasks on Vandaag", async () => {
    const overdue = { schedule_id: 1, action_type: "water" as const, custom_label: null, date: "2026-01-01", is_overdue: true };
    vi.mocked(gardnrApi.listPlants).mockResolvedValue([
      {
        id: 1, area_id: 1, area_name: "Achtertuin", name: "Hortensia", species: null, type: "plant", status: "thriving",
        is_archived: false, next_action: overdue, is_overdue: true, scheduled_actions: [overdue, { ...overdue, schedule_id: 2 }],
      },
    ]);
    renderNav("/gardnr/areas/1");

    expect(await screen.findByLabelText("2 te laat")).toHaveTextContent("2");
    expect(screen.getByRole("link", { name: /Tuinen/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /Vandaag/ })).not.toHaveAttribute("aria-current");
  });
});
