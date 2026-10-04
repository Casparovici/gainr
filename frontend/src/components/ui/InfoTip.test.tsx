import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import InfoHeading from "./InfoTip";

describe("InfoHeading", () => {
  it("keeps the explanation folded behind the ⓘ next to the title until asked for", async () => {
    render(
      <InfoHeading label="Virtual pot inside" title={<label htmlFor="pot">Virtual pot inside</label>}>
        For money set aside on paper.
      </InfoHeading>,
    );
    const button = screen.getByRole("button", { name: "About Virtual pot inside" });

    expect(screen.getByText("For money set aside on paper.")).not.toBeVisible();
    expect(button).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(button);
    expect(screen.getByText("For money set aside on paper.")).toBeVisible();
    expect(button).toHaveAttribute("aria-expanded", "true");

    await userEvent.click(button);
    expect(screen.getByText("For money set aside on paper.")).not.toBeVisible();
  });
});
