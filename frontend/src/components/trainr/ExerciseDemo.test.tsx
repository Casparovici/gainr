import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TrainrExerciseDemo } from "../../api/trainrTypes";
import ExerciseDemo, { DEMO_FRAME_MS } from "./ExerciseDemo";

const pressDemo: TrainrExerciseDemo = {
  id: "Dumbbell_Bench_Press",
  name: "Dumbbell Bench Press",
  equipment: "dumbbell",
  image_urls: ["https://cdn.example/press/0.jpg", "https://cdn.example/press/1.jpg"],
  instructions: ["Lie down on a flat bench.", "Press the dumbbells up."],
};

const images = () => document.querySelectorAll("img");
const loadAll = () => images().forEach((img) => fireEvent.load(img));

describe("ExerciseDemo", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("says it's loading, then flips between the start and end position", () => {
    render(<ExerciseDemo demo={pressDemo} />);
    expect(screen.getByText("Voorbeeld laden…")).toBeInTheDocument();

    loadAll();
    expect(screen.queryByText("Voorbeeld laden…")).not.toBeInTheDocument();
    expect(screen.getByAltText("Dumbbell Bench Press, beginpositie")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(DEMO_FRAME_MS));
    expect(screen.getByAltText("Dumbbell Bench Press, eindpositie")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(DEMO_FRAME_MS));
    expect(screen.getByAltText("Dumbbell Bench Press, beginpositie")).toBeInTheDocument();
  });

  it("steps by hand on a tap, and folds the steps away", () => {
    render(<ExerciseDemo demo={pressDemo} />);
    fireEvent.click(screen.getByRole("button", { name: "Voorbeeld: Dumbbell Bench Press" }));
    expect(screen.getByAltText("Dumbbell Bench Press, eindpositie")).toBeInTheDocument();

    expect(screen.getByText("Uitleg (Engels)")).toBeInTheDocument();
    expect(screen.getByText("Press the dumbbells up.")).not.toBeVisible();
  });

  it("says so when a photo can't load", () => {
    render(<ExerciseDemo demo={pressDemo} showSteps={false} />);
    fireEvent.error(images()[0]);

    expect(screen.getByText(/kon niet laden/)).toBeInTheDocument();
    expect(images()).toHaveLength(0);
    expect(screen.queryByText("Uitleg (Engels)")).not.toBeInTheDocument();
  });
});
