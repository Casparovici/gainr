import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { taskrApi } from "../api/taskrClient";
import type { AgendaItem, Today } from "../api/taskrTypes";
import Vandaag, { attentionItems } from "./Vandaag";

vi.mock("../api/taskrClient", () => ({
  taskrApi: { getToday: vi.fn(), createTask: vi.fn(), updateTask: vi.fn(), setTaskCompleted: vi.fn(), deleteTask: vi.fn() },
}));
vi.mock("../components/ModuleSwitcher", () => ({ default: () => null }));
vi.mock("../components/ModuleIndicators", () => ({ default: () => null }));
vi.mock("../components/ModuleSettingsButton", () => ({ default: () => null }));

const TODAY = "2026-10-20";

const item = (over: Partial<AgendaItem>): AgendaItem => ({
  key: "taskr:task:1", source: "taskr", title: "Fiets naar de service", detail: null, due_date: TODAY,
  is_overdue: false, link: null, task_id: 1, ...over,
});

function today(over: Partial<Today> = {}): Today {
  return {
    date: TODAY,
    agenda: { date_from: TODAY, date_to: TODAY, overdue: [], days: [] },
    portfolio: null,
    money: null,
    latest_unread_report: null,
    meal: null,
    pinned_notes: [],
    counts: { gripr_uncategorized: 0, gardnr_due: 0, trainr_today: 0, taskr_overdue: 0, listr_to_get: 0, briefr_unread: 0, notr_pinned: 0 },
    ...over,
  };
}

function Where() {
  const location = useLocation();
  return <span data-testid="where">{location.pathname + location.search}</span>;
}

function renderPage(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={<Vandaag today={TODAY} />} />
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("attentionItems", () => {
  it("words what waits, late things first, and leaves out modules with nothing", () => {
    const items = attentionItems(
      today({
        counts: { gripr_uncategorized: 6, gardnr_due: 4, trainr_today: 1, taskr_overdue: 0, listr_to_get: 9, briefr_unread: 2, notr_pinned: 0 },
        agenda: { date_from: TODAY, date_to: TODAY, overdue: [item({ source: "gardnr", is_overdue: true })], days: [] },
        latest_unread_report: { id: 3, title: "Mon 19 Oct · Main: +0.56%", attention: "watch" },
      }),
    );
    expect(items.map((i) => [i.key, i.title, i.late ?? false])).toEqual([
      ["gardnr", "4 verzorgingen in de tuin", true],
      ["gripr", "6 betalingen zonder categorie", false],
      ["briefr", "Mon 19 Oct · Main: +0.56%", false],
    ]);
    expect(items[1].to).toBe("/gripr/transactions?category=uncategorized");
  });
});

describe("Vandaag", () => {
  it("says when nothing needs attention and nothing is planned", async () => {
    vi.mocked(taskrApi.getToday).mockResolvedValue(today());
    renderPage();
    expect(await screen.findByText(/Alles bij/)).toBeInTheDocument();
    expect(screen.getByText("Niets gepland vandaag.")).toBeInTheDocument();
    expect(screen.getByText(/niets vraagt aandacht/)).toBeInTheDocument();
  });

  it("shows the money, today's agenda and tonight's meal, each linking to its module", async () => {
    vi.mocked(taskrApi.getToday).mockResolvedValue(
      today({
        portfolio: { portfolio_id: 1, name: "Main", value_eur: "56807.05", day_change_eur: "314.2", day_change_pct: "0.56" },
        money: { safe_to_move_eur: "5287.72", expected_end_eur: "5599.93" },
        meal: { title: "Pasta pesto", is_cooked: false },
        agenda: { date_from: TODAY, date_to: TODAY, overdue: [], days: [{ date: TODAY, items: [item({})] }] },
        counts: { gripr_uncategorized: 0, gardnr_due: 0, trainr_today: 0, taskr_overdue: 0, listr_to_get: 2, briefr_unread: 0, notr_pinned: 0 },
      }),
    );
    renderPage();
    expect(await screen.findByRole("link", { name: /gainr · Main/ })).toHaveAttribute("href", "/gainr");
    expect(screen.getByRole("link", { name: /gripr · deze periode/ })).toHaveAttribute("href", "/gripr/overview");
    expect(screen.getByRole("link", { name: /Vanavond: Pasta pesto/ })).toHaveTextContent("2 dingen op de boodschappenlijst");
    expect(within(screen.getByRole("region", { name: "Op de agenda" })).getByText("Fiets naar de service")).toBeInTheDocument();
  });

  it("adds a task for today from the quick-add sheet", async () => {
    vi.mocked(taskrApi.getToday).mockResolvedValue(today());
    vi.mocked(taskrApi.createTask).mockResolvedValue({ id: 9, title: "Band plakken", notes: null, due_date: TODAY, completed_at: null });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "+ Taak" }));
    await userEvent.type(screen.getByLabelText("Wat"), "Band plakken");
    await userEvent.click(screen.getByRole("button", { name: "Toevoegen" }));
    expect(taskrApi.createTask).toHaveBeenCalledWith({ title: "Band plakken", due_date: TODAY, notes: null });
  });

  it("lists pinned notes with a link to each and to all notes", async () => {
    vi.mocked(taskrApi.getToday).mockResolvedValue(
      today({
        pinned_notes: [
          { id: 4, title: "Thesis ASML", preview: "Waarom ik het bezit" },
          { id: 5, title: "", preview: "Eerste regel zonder titel" },
        ],
        counts: { gripr_uncategorized: 0, gardnr_due: 0, trainr_today: 0, taskr_overdue: 0, listr_to_get: 0, briefr_unread: 0, notr_pinned: 2 },
      }),
    );
    renderPage();
    const card = await screen.findByRole("region", { name: "Vastgezet" });
    expect(within(card).getByRole("link", { name: /Thesis ASML/ })).toHaveAttribute("href", "/notr/4");
    expect(within(card).getByRole("link", { name: /Eerste regel zonder titel/ })).toHaveAttribute("href", "/notr/5");
    expect(within(card).getByRole("link", { name: "Alle notities ›" })).toHaveAttribute("href", "/notr");
  });

  it("shows no pinned card when nothing is pinned", async () => {
    vi.mocked(taskrApi.getToday).mockResolvedValue(today());
    renderPage();
    await screen.findByText(/Alles bij/);
    expect(screen.queryByRole("region", { name: "Vastgezet" })).not.toBeInTheDocument();
  });

  it("starts a new note from the quick-add row", async () => {
    vi.mocked(taskrApi.getToday).mockResolvedValue(today());
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "+ Notitie" }));
    expect(await screen.findByTestId("where")).toHaveTextContent("/notr/new");
  });

  it("sends an old position link on to gainr Home", async () => {
    vi.mocked(taskrApi.getToday).mockResolvedValue(today());
    renderPage("/?position=7");
    expect(await screen.findByTestId("where")).toHaveTextContent("/gainr?position=7");
  });

  it("offers a retry when it can't load", async () => {
    vi.mocked(taskrApi.getToday).mockRejectedValueOnce(new Error("down")).mockResolvedValue(today());
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Opnieuw proberen" }));
    expect(await screen.findByText(/Alles bij/)).toBeInTheDocument();
  });
});
