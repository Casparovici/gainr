import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { gardnrApi } from "../../api/gardnrClient";
import type { GardenAreaDetail } from "../../api/gardnrTypes";
import { todayLocalISO } from "../../utils/gardnr";
import GardnrAreaMap from "./AreaMap";

vi.mock("../../api/gardnrClient", () => ({
  gardnrApi: {
    getAreaDetail: vi.fn(),
    getPlantDetail: vi.fn(),
    createLog: vi.fn(),
    updatePlant: vi.fn(),
    updateZone: vi.fn(),
    createPlant: vi.fn(),
    createZone: vi.fn(),
    listPlants: vi.fn(),
  },
}));

const area: GardenAreaDetail = {
  area: { id: 1, name: "Achtertuin", sort_order: 0, plant_count: 1, overdue_count: 1 },
  zones: [{ id: 5, area_id: 1, name: "Groentebed", shape: "rect", x: "10", y: "10", width: "40", height: "30", color: "#a7c957", sort_order: 0 }],
  plants: [
    {
      id: 7,
      name: "Tomaat",
      species: null,
      type: "plant",
      x: "20",
      y: "20",
      marker_shape: "circle",
      marker_width: "6",
      marker_height: "6",
      icon: null,
      status: "thriving",
      last_action: null,
      next_action: { schedule_id: 3, action_type: "water", custom_label: null, date: "2026-09-01", is_overdue: true },
    },
  ],
};

// jsdom lays nothing out, so give the map a real size for the percent maths.
function mockCanvasRect() {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    left: 0, top: 0, right: 400, bottom: 300, width: 400, height: 300, x: 0, y: 0, toJSON: () => ({}),
  } as DOMRect);
}

function renderMap() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/gardnr/areas/1"]}>
        <Routes>
          <Route path="/gardnr/areas/:id" element={<GardnrAreaMap />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GardnrAreaMap on a phone", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    vi.mocked(gardnrApi.getAreaDetail).mockResolvedValue(area);
    vi.mocked(gardnrApi.createLog).mockResolvedValue({
      id: 99, plant_id: 7, action_type: "water", custom_label: null, performed_on: todayLocalISO(), notes: null, has_photo: false,
    });
  });

  it("peeks at a tapped plant instead of moving it, and logs the due action for today", async () => {
    renderMap();
    const marker = await screen.findByRole("button", { name: "Tomaat" });

    // A slightly wobbly finger tap: in view mode that must never become a move.
    fireEvent.touchStart(marker, { touches: [{ clientX: 100, clientY: 100 }] });
    fireEvent.touchMove(marker, { touches: [{ clientX: 112, clientY: 104 }] });
    fireEvent.touchEnd(marker, { changedTouches: [{ clientX: 112, clientY: 104 }] });
    await userEvent.click(marker);

    // The design's plant sheet: what's due (overdue here) as a tile, and the big button for it.
    const sheet = screen.getByRole("region", { name: "Tomaat" });
    expect(sheet).toHaveTextContent("Water geven");
    expect(sheet).toHaveTextContent(/te laat sinds/);
    expect(gardnrApi.updatePlant).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /Water geven gedaan/ }));
    expect(gardnrApi.createLog).toHaveBeenCalledWith(7, {
      action_type: "water",
      custom_label: null,
      performed_on: todayLocalISO(),
      notes: null,
    });
  });

  it("only offers adding zones and plants after switching to Bewerken", async () => {
    renderMap();
    await screen.findByRole("button", { name: "Tomaat" });
    expect(screen.queryByRole("button", { name: "+ Plant" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Bewerken/ }));
    expect(screen.getByRole("button", { name: "+ Plant" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Vak" })).toBeInTheDocument();
  });

  it("places a new plant even when the tap lands on a bed", async () => {
    renderMap();
    await screen.findByRole("button", { name: "Tomaat" });
    await userEvent.click(screen.getByRole("button", { name: /Bewerken/ }));
    await userEvent.click(screen.getByRole("button", { name: "+ Plant" }));

    // The placement layer covers zones and markers alike, so this tap can't be swallowed by one.
    await userEvent.click(screen.getByTestId("plant-placement-layer"));
    expect(screen.getByText("Nieuwe plant")).toBeInTheDocument();
  });

  it("resizes a bed by dragging its corner handle with the mouse", async () => {
    renderMap();
    await screen.findByRole("button", { name: "Tomaat" });
    await userEvent.click(screen.getByRole("button", { name: /Bewerken/ }));
    mockCanvasRect();
    vi.mocked(gardnrApi.updateZone).mockResolvedValue(area.zones[0]);

    // Only the selected bed gets a handle: tap it first (a press without moving).
    expect(screen.queryByTestId("resize-zone-5")).not.toBeInTheDocument();
    fireEvent.mouseDown(screen.getByText("Groentebed"), { clientX: 100, clientY: 80 });
    fireEvent.mouseUp(screen.getByText("Groentebed"), { clientX: 100, clientY: 80 });

    // Groentebed's top-left corner is at (10%, 10%) of a 400x300 map; dropping the handle at
    // (240px, 150px) = (60%, 50%) makes it 50% wide and 40% tall.
    const handle = await screen.findByTestId("resize-zone-5");
    fireEvent.mouseDown(handle, { clientX: 200, clientY: 120 });
    fireEvent.mouseMove(handle, { clientX: 240, clientY: 150 });
    fireEvent.mouseUp(handle, { clientX: 240, clientY: 150 });

    await waitFor(() => expect(gardnrApi.updateZone).toHaveBeenCalledWith(5, { width: "50.00", height: "40.00" }));
    // The selected bed's editor sits below the map, not in a pop-up.
    expect(screen.getByRole("region", { name: "Vak bewerken" })).toBeInTheDocument();
  });

  it("keeps a round plant marker round when resizing it", async () => {
    renderMap();
    await screen.findByRole("button", { name: "Tomaat" });
    await userEvent.click(screen.getByRole("button", { name: /Bewerken/ }));
    mockCanvasRect();
    vi.mocked(gardnrApi.updatePlant).mockResolvedValue({} as Awaited<ReturnType<typeof gardnrApi.updatePlant>>);

    // Select the marker first (a press without moving) -- only then does it get a handle.
    const marker = screen.getByRole("button", { name: "Tomaat" });
    fireEvent.mouseDown(marker, { clientX: 80, clientY: 60 });
    fireEvent.mouseUp(marker, { clientX: 80, clientY: 60 });

    // Centred at (20%, 20%): a corner 5% right and 2% down of it is a 10%-wide marker, and a
    // circle takes its width for its height too.
    const handle = await screen.findByTestId("resize-plant-7");
    fireEvent.mouseDown(handle, { clientX: 90, clientY: 66 });
    fireEvent.mouseMove(handle, { clientX: 100, clientY: 66 });
    fireEvent.mouseUp(handle, { clientX: 100, clientY: 66 });

    await waitFor(() => expect(gardnrApi.updatePlant).toHaveBeenCalledWith(7, { marker_width: "10.00", marker_height: "10.00" }));
  });

  it("recolours a selected bed with the design's swatches", async () => {
    renderMap();
    await screen.findByRole("button", { name: "Tomaat" });
    await userEvent.click(screen.getByRole("button", { name: /Bewerken/ }));
    mockCanvasRect();
    vi.mocked(gardnrApi.updateZone).mockResolvedValue(area.zones[0]);

    fireEvent.mouseDown(screen.getByText("Groentebed"), { clientX: 100, clientY: 80 });
    fireEvent.mouseUp(screen.getByText("Groentebed"), { clientX: 100, clientY: 80 });
    const editor = await screen.findByRole("region", { name: "Vak bewerken" });
    expect(editor.querySelector("input")).toHaveValue("Groentebed");

    await userEvent.click(screen.getByRole("button", { name: "Kleur water" }));
    expect(gardnrApi.updateZone).toHaveBeenCalledWith(5, { color: "#BCD8DF" });
  });

  it("adds a bed straight away and opens its editor", async () => {
    renderMap();
    await screen.findByRole("button", { name: "Tomaat" });
    await userEvent.click(screen.getByRole("button", { name: /Bewerken/ }));
    const created = { ...area.zones[0], id: 9, name: "Nieuw vak" };
    vi.mocked(gardnrApi.createZone).mockResolvedValue(created);
    vi.mocked(gardnrApi.getAreaDetail).mockResolvedValue({ ...area, zones: [...area.zones, created] });

    await userEvent.click(screen.getByRole("button", { name: "+ Vak" }));

    expect(gardnrApi.createZone).toHaveBeenCalledWith(1, expect.objectContaining({ name: "Nieuw vak", color: "#CFE3B8" }));
    const editor = await screen.findByRole("region", { name: "Vak bewerken" });
    expect(editor.querySelector("input")).toHaveValue("Nieuw vak");
  });

  it("shows the garden's overdue and due-today chips", async () => {
    vi.mocked(gardnrApi.listPlants).mockResolvedValue([
      {
        id: 7, area_id: 1, area_name: "Achtertuin", name: "Tomaat", species: null, type: "plant", status: "thriving", is_archived: false,
        next_action: area.plants[0].next_action, is_overdue: true,
        scheduled_actions: [area.plants[0].next_action!, { schedule_id: 4, action_type: "harvest", custom_label: null, date: todayLocalISO(), is_overdue: false }],
      },
    ]);
    renderMap();
    expect(await screen.findByText("1 te laat")).toBeInTheDocument();
    expect(screen.getByText("1 vandaag")).toBeInTheDocument();
  });

  it("places a plant that was added without a map position", async () => {
    vi.mocked(gardnrApi.getAreaDetail).mockResolvedValue({
      ...area,
      plants: [...area.plants, { ...area.plants[0], id: 8, name: "Lavendel", x: null, y: null }],
    });
    vi.mocked(gardnrApi.updatePlant).mockResolvedValue({} as Awaited<ReturnType<typeof gardnrApi.updatePlant>>);
    renderMap();

    expect(await screen.findByText(/Lavendel staat nog niet op de kaart/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Bewerken/ }));
    await userEvent.click(screen.getByRole("button", { name: "Lavendel" }));
    mockCanvasRect();
    fireEvent.click(screen.getByTestId("plant-placement-layer"), { clientX: 200, clientY: 150 });

    await waitFor(() => expect(gardnrApi.updatePlant).toHaveBeenCalledWith(8, { x: "50.00", y: "50.00" }));
  });

  it("says so, with a retry, when the garden can't be loaded", async () => {
    vi.mocked(gardnrApi.getAreaDetail).mockRejectedValue(new Error("500"));
    renderMap();
    expect(await screen.findByText(/Deze tuin kon niet worden geladen/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Opnieuw proberen" })).toBeInTheDocument();
  });
});
