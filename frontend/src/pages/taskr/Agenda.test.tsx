import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { taskrApi } from "../../api/taskrClient";
import type { Agenda, AgendaItem } from "../../api/taskrTypes";
import TaskrAgenda from "./Agenda";

vi.mock("../../api/taskrClient", () => ({
  taskrApi: { getAgenda: vi.fn(), createTask: vi.fn(), updateTask: vi.fn(), setTaskCompleted: vi.fn(), deleteTask: vi.fn() },
}));
// The top row's switcher, bell and gear have their own tests and their own queries.
vi.mock("../../components/ModuleSwitcher", () => ({ default: () => null }));
vi.mock("../../components/ModuleIndicators", () => ({ default: () => null }));
vi.mock("../../components/ModuleSettingsButton", () => ({ default: () => null }));

// A fixed "today" (a Wednesday), passed in -- the page never reads the clock in these tests.
const TODAY = "2026-10-14";

const item = (over: Partial<AgendaItem>): AgendaItem => ({
  key: "gardnr:schedule:1",
  source: "gardnr",
  title: "Water Tomaat",
  detail: null,
  due_date: TODAY,
  is_overdue: false,
  link: "/gardnr/vandaag",
  task_id: null,
  ...over,
});

const agenda = (over: Partial<Agenda>): Agenda => ({ date_from: TODAY, date_to: "2026-10-20", overdue: [], days: [], ...over });

function renderAgenda() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/taskr"]}>
        <TaskrAgenda today={TODAY} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TaskrAgenda", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("says it's loading until the agenda arrives", () => {
    vi.mocked(taskrApi.getAgenda).mockReturnValue(new Promise(() => {}));
    renderAgenda();
    expect(screen.getByRole("status")).toHaveTextContent("Agenda laden…");
  });

  it("asks for this week by default: seven days from today", async () => {
    vi.mocked(taskrApi.getAgenda).mockResolvedValue(agenda({}));
    renderAgenda();
    await screen.findByText("Niets te doen");
    expect(taskrApi.getAgenda).toHaveBeenCalledWith(TODAY, "2026-10-20");
    expect(screen.getByText("14 okt – 20 okt")).toBeInTheDocument();
  });

  it("shows overdue items first, then each day with its items and a link to the owning module", async () => {
    vi.mocked(taskrApi.getAgenda).mockResolvedValue(
      agenda({
        overdue: [item({ key: "gardnr:schedule:9", title: "Prune Roos", due_date: "2026-10-12", is_overdue: true })],
        days: [
          {
            date: TODAY,
            items: [item({ key: "trainr:workout:3", source: "trainr", title: "Run", detail: "10 km", link: "/trainr" })],
          },
          {
            date: "2026-10-15",
            items: [
              item({ key: "gardnr:schedule:4", title: "Water Tomaat", due_date: "2026-10-15" }),
            ],
          },
        ],
      }),
    );
    renderAgenda();

    const sections = await screen.findAllByRole("region");
    expect(sections.map((s) => s.getAttribute("aria-label"))).toEqual(["Achterstallig", "Vandaag", "Morgen"]);

    const overdue = within(sections[0]);
    expect(overdue.getByText("Prune Roos")).toBeInTheDocument();
    expect(overdue.getByText("te laat · ma 12 okt")).toBeInTheDocument();
    expect(overdue.getByRole("link", { name: "Prune Roos: open in gardnr" })).toHaveAttribute("href", "/gardnr/vandaag");

    const today = within(sections[1]);
    expect(today.getByText("Run")).toBeInTheDocument();
    expect(today.getByText("10 km")).toBeInTheDocument();
    expect(today.getByRole("link", { name: "Run: open in trainr" })).toHaveTextContent("Open in trainr");

    const tomorrow = within(sections[2]);
    expect(tomorrow.getByRole("link", { name: "Water Tomaat: open in gardnr" })).toHaveAttribute("href", "/gardnr/vandaag");

    expect(screen.getByText("1 te laat · 2 in deze periode")).toBeInTheDocument();
  });

  it("says there is nothing to do when the range and the backlog are empty", async () => {
    vi.mocked(taskrApi.getAgenda).mockResolvedValue(agenda({}));
    renderAgenda();
    expect(await screen.findByText("Niets te doen")).toBeInTheDocument();
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });

  it("offers a retry when the agenda can't be loaded", async () => {
    vi.mocked(taskrApi.getAgenda).mockRejectedValueOnce(new Error("500 Internal Server Error"));
    renderAgenda();
    expect(await screen.findByRole("alert")).toHaveTextContent("Kon de agenda niet laden.");

    vi.mocked(taskrApi.getAgenda).mockResolvedValueOnce(agenda({ days: [{ date: TODAY, items: [item({})] }] }));
    await userEvent.click(screen.getByRole("button", { name: "Opnieuw proberen" }));
    expect(await screen.findByText("Water Tomaat")).toBeInTheDocument();
  });

  it("switches to a single day and pages through days, with a way back to today", async () => {
    vi.mocked(taskrApi.getAgenda).mockResolvedValue(agenda({}));
    renderAgenda();
    await screen.findByText("Niets te doen");

    await userEvent.click(screen.getByRole("button", { name: "Dag" }));
    expect(await screen.findByText("Vandaag · woensdag 14 okt")).toBeInTheDocument();
    expect(taskrApi.getAgenda).toHaveBeenLastCalledWith(TODAY, TODAY);
    expect(screen.queryByRole("button", { name: "Naar vandaag" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(await screen.findByText("Morgen · donderdag 15 okt")).toBeInTheDocument();
    expect(taskrApi.getAgenda).toHaveBeenLastCalledWith("2026-10-15", "2026-10-15");

    await userEvent.click(screen.getByRole("button", { name: "Naar vandaag" }));
    expect(await screen.findByText("Vandaag · woensdag 14 okt")).toBeInTheDocument();
  });

  it("labels the backlog 'before this period' for a week further ahead, where not all of it is late", async () => {
    vi.mocked(taskrApi.getAgenda).mockImplementation(async (from, to) =>
      agenda({ date_from: from, date_to: to, overdue: [item({ due_date: "2026-10-16", is_overdue: false })] }),
    );
    renderAgenda();
    await screen.findByRole("region", { name: "Achterstallig" });

    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(await screen.findByRole("region", { name: "Vóór deze periode" })).toBeInTheDocument();
    expect(taskrApi.getAgenda).toHaveBeenLastCalledWith("2026-10-21", "2026-10-27");
    expect(screen.getByText("vr 16 okt")).toBeInTheDocument();
  });

  describe("taskr's own tasks", () => {
    const task = item({ key: "taskr:task:5", source: "taskr", title: "Bel de loodgieter", detail: "lekkende kraan", link: null, task_id: 5 });

    it("adds a task on the first day on screen, or on the day picked", async () => {
      vi.mocked(taskrApi.getAgenda).mockResolvedValue(agenda({}));
      vi.mocked(taskrApi.createTask).mockResolvedValue({ id: 1, title: "x", notes: null, due_date: TODAY, completed_at: null });
      renderAgenda();
      await screen.findByText("Niets te doen");

      await userEvent.type(screen.getByRole("textbox", { name: "Nieuwe taak" }), "  Fietsband plakken {Enter}");
      expect(taskrApi.createTask).toHaveBeenCalledWith({ title: "Fietsband plakken", due_date: TODAY, notes: null });
      expect(screen.getByRole("textbox", { name: "Nieuwe taak" })).toHaveValue("");

      await userEvent.type(screen.getByRole("textbox", { name: "Nieuwe taak" }), "Belasting");
      // jsdom can't type into a date input; set it the way the picker does.
      fireEvent.change(screen.getByLabelText("Datum van de nieuwe taak"), { target: { value: "2026-10-17" } });
      await userEvent.click(screen.getByRole("button", { name: "Toevoegen" }));
      expect(taskrApi.createTask).toHaveBeenLastCalledWith({ title: "Belasting", due_date: "2026-10-17", notes: null });
    });

    it("ticks a task off with its circle, with an undo, and has no module link", async () => {
      vi.mocked(taskrApi.getAgenda).mockResolvedValue(agenda({ days: [{ date: TODAY, items: [task] }] }));
      vi.mocked(taskrApi.setTaskCompleted).mockResolvedValue({ id: 5, title: "x", notes: null, due_date: TODAY, completed_at: null });
      renderAgenda();

      await userEvent.click(await screen.findByRole("button", { name: "Bel de loodgieter: afvinken" }));
      expect(taskrApi.setTaskCompleted).toHaveBeenCalledWith(5, true);
      expect(screen.queryByRole("link", { name: /Bel de loodgieter/ })).not.toBeInTheDocument();

      await userEvent.click(await screen.findByRole("button", { name: "Ongedaan maken" }));
      expect(taskrApi.setTaskCompleted).toHaveBeenLastCalledWith(5, false);
    });

    it("changes a task's title, day and notes, or deletes it after asking", async () => {
      vi.mocked(taskrApi.getAgenda).mockResolvedValue(agenda({ days: [{ date: TODAY, items: [task] }] }));
      vi.mocked(taskrApi.updateTask).mockResolvedValue({ id: 5, title: "x", notes: null, due_date: TODAY, completed_at: null });
      vi.mocked(taskrApi.deleteTask).mockResolvedValue(undefined);
      renderAgenda();

      await userEvent.click(await screen.findByRole("button", { name: "Bel de loodgieter: wijzigen" }));
      const title = screen.getByRole("textbox", { name: "Taak" });
      await userEvent.clear(title);
      await userEvent.type(title, "Bel de loodgieter terug");
      const notes = screen.getByRole("textbox", { name: "Notitie" });
      expect(notes).toHaveValue("lekkende kraan");
      await userEvent.clear(notes);
      await userEvent.click(screen.getByRole("button", { name: "Opslaan" }));
      expect(taskrApi.updateTask).toHaveBeenCalledWith(5, { title: "Bel de loodgieter terug", due_date: TODAY, notes: null });

      await userEvent.click(await screen.findByRole("button", { name: "Bel de loodgieter: wijzigen" }));
      const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
      await userEvent.click(screen.getByRole("button", { name: "Verwijderen" }));
      expect(taskrApi.deleteTask).not.toHaveBeenCalled();
      await userEvent.click(screen.getByRole("button", { name: "Verwijderen" }));
      expect(taskrApi.deleteTask).toHaveBeenCalledWith(5);
      confirm.mockRestore();
    });
  });
});
