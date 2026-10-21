import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { taskrApi } from "../api/taskrClient";
import type { Today } from "../api/taskrTypes";
import ModuleSwitcher, { moduleStatus } from "./ModuleSwitcher";

vi.mock("../api/taskrClient", () => ({ taskrApi: { getToday: vi.fn() } }));
// The theme switch has its own tests and needs the theme context.
vi.mock("./ThemeToggle", () => ({ default: () => <span>theme switch</span> }));

const today: Today = {
  date: "2026-10-20",
  agenda: { date_from: "2026-10-20", date_to: "2026-10-20", overdue: [], days: [] },
  portfolio: { portfolio_id: 1, name: "Main", value_eur: "100", day_change_eur: "1", day_change_pct: "0.56" },
  money: null,
  latest_unread_report: null,
  pinned_notes: [],
  meal: null,
  counts: { gripr_uncategorized: 6, gardnr_due: 0, trainr_today: 1, taskr_overdue: 0, listr_to_get: 9, briefr_unread: 4, notr_pinned: 3 },
};

describe("moduleStatus", () => {
  it("gives each module its count and line, and nothing before the data's in", () => {
    expect(moduleStatus("gripr", today)).toEqual({ count: 6, hint: "6 zonder categorie" });
    expect(moduleStatus("briefr", today)).toEqual({ count: 4, hint: "4 ongelezen" });
    expect(moduleStatus("notr", today)).toEqual({ count: 0, hint: "3 vastgezet" });
    expect(moduleStatus("notr", { ...today, counts: { ...today.counts, notr_pinned: 0 } })).toEqual({ count: 0, hint: null });
    expect(moduleStatus("listr", today)).toEqual({ count: 0, hint: "9 op de lijst" });
    expect(moduleStatus("gainr", today).hint).toMatch(/^\+0[,.]56% vandaag$/);
    expect(moduleStatus("vandaag", today).hint).toBe("2 dingen vragen aandacht");
    expect(moduleStatus("gripr", undefined)).toEqual({ count: 0, hint: null });
  });
});

describe("ModuleSwitcher on a phone", () => {
  it("opens a sheet of modules with their counts, without taskr, and the theme switch", async () => {
    vi.mocked(taskrApi.getToday).mockResolvedValue(today);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/gripr"]}>
          <ModuleSwitcher variant="pill" />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: /naar een andere module/ }));
    const nav = await screen.findByRole("navigation", { name: "Modules" });
    expect(nav).toHaveTextContent("Vandaag");
    expect(await screen.findByRole("link", { name: "gripr, 6 zonder categorie" })).toHaveAttribute("aria-current", "page");
    // notr sits after briefr, links to its notes and shows how many are pinned (no badge).
    const notr = screen.getByRole("link", { name: "notr, 3 vastgezet" });
    expect(notr).toHaveAttribute("href", "/notr");
    expect(screen.queryByRole("link", { name: /^taskr/ })).not.toBeInTheDocument();
    expect(screen.getByText("Thema")).toBeInTheDocument();
  });
});
