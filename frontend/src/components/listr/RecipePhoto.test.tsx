import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RecipePhoto from "./RecipePhoto";

const recipe = { id: 7, updated_at: "2026-10-18T10:00:00", has_photo: true };

describe("RecipePhoto", () => {
  it("shows the photo, keyed by the recipe's last change so a new photo is a new URL", () => {
    render(<RecipePhoto recipe={recipe} alt="Pannenkoeken" className="h-10 w-10" />);
    expect(screen.getByRole("img", { name: "Pannenkoeken" })).toHaveAttribute(
      "src",
      "/api/listr/recipes/7/photo?v=2026-10-18T10%3A00%3A00",
    );
  });

  it("falls back to a placeholder, without requesting an image, when there is no photo", () => {
    const { container } = render(<RecipePhoto recipe={{ ...recipe, has_photo: false }} className="h-10 w-10" />);
    expect(container.querySelector("img")).toBeNull();
  });
});
