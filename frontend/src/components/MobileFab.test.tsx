import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MobileFab from "./MobileFab";

describe("MobileFab", () => {
  it("leaves room after the content so the last row isn't hidden behind the button", () => {
    render(
      <div>
        <p>Last transaction</p>
        <MobileFab label="Add" onClick={() => {}} />
      </div>,
    );

    const spacer = screen.getByTestId("fab-spacer");
    expect(spacer.previousElementSibling).toHaveTextContent("Last transaction");
    expect(spacer).toHaveClass("h-16", "sm:hidden");
    expect(screen.getByRole("button", { name: "Add" })).toHaveClass("fixed", "h-14");
  });
});
