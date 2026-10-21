import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import WeightBar, { weightScale } from "./WeightBar";

describe("weightScale", () => {
  it("is the largest weight or target, so the biggest bar fills", () => {
    expect(weightScale([{ weight_pct: "30.6", target_weight_pct: "35" }, { weight_pct: "12", target_weight_pct: null }])).toBe(35);
    expect(weightScale([])).toBe(0);
  });
});

describe("WeightBar", () => {
  it("writes the weight and target out next to the bar", () => {
    render(<WeightBar weight="30.6" target="35" scale={35} />);
    expect(screen.getByText(/30[,.]6% · target 35[,.]0%/)).toBeInTheDocument();
  });

  it("can leave the target to a column of its own", () => {
    render(<WeightBar weight="12" target="10" scale={35} showTarget={false} />);
    expect(screen.getByText(/^12[,.]0%$/)).toBeInTheDocument();
  });
});
