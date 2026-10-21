import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { trainrApi } from "../../api/trainrClient";
import type { TrainrExercise, TrainrExerciseDemo } from "../../api/trainrTypes";
import ExerciseDemoPicker from "./ExerciseDemoPicker";

vi.mock("../../api/trainrClient", () => ({
  trainrApi: { searchExerciseDemos: vi.fn() },
}));

const demo = (id: string, name: string): TrainrExerciseDemo => ({
  id, name, equipment: "dumbbell", image_urls: [`https://cdn.example/${id}/0.jpg`, `https://cdn.example/${id}/1.jpg`], instructions: [],
});

const exercise = (over: Partial<TrainrExercise> = {}): TrainrExercise => ({
  id: 4, name: "Hammer curl", muscle_group: "arms", equipment: "dumbbell", is_archived: false, times_performed: 0,
  last_performed_on: null, last_sets: null, last_reps: null, last_weight_kg: null, best_weight_kg: null, demo_id: null, demo: null, ...over,
});

function renderPicker(ex: TrainrExercise) {
  const onPick = vi.fn();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ExerciseDemoPicker exercise={ex} isSaving={false} error={null} onPick={onPick} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
  return { onPick };
}

describe("ExerciseDemoPicker", () => {
  beforeEach(() => vi.clearAllMocks());

  it("searches on the exercise's own name and links the one you tap", async () => {
    vi.mocked(trainrApi.searchExerciseDemos).mockResolvedValue([demo("Hammer_Curls", "Hammer Curls"), demo("Alternate_Hammer_Curl", "Alternate Hammer Curl")]);
    const { onPick } = renderPicker(exercise());

    expect(screen.getByText(/Nog geen voorbeeld/)).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: /Hammer Curls/ }));

    expect(trainrApi.searchExerciseDemos).toHaveBeenCalledWith("Hammer curl");
    expect(onPick).toHaveBeenCalledWith("Hammer_Curls");
  });

  it("shows the linked demo, which can be unlinked, and says when a search finds nothing", async () => {
    vi.mocked(trainrApi.searchExerciseDemos).mockResolvedValue([demo("Hammer_Curls", "Hammer Curls")]);
    const linked = demo("Hammer_Curls", "Hammer Curls");
    const { onPick } = renderPicker(exercise({ demo_id: linked.id, demo: linked }));

    // The linked one isn't offered again; with nothing else found, that's said.
    expect(await screen.findByText(/Niets gevonden/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ontkoppelen" }));
    expect(onPick).toHaveBeenCalledWith(null);
  });
});
