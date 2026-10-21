import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import FontPicker from "./FontPicker";

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-font");
});

describe("FontPicker", () => {
  it("starts on the default package", () => {
    render(<FontPicker />);
    expect(screen.getByRole("radio", { name: /Bricolage/ })).toHaveAttribute("aria-checked", "true");
    expect(document.documentElement).not.toHaveAttribute("data-font");
  });

  it("applies a package to the page and remembers it", async () => {
    render(<FontPicker />);
    await userEvent.click(screen.getByRole("radio", { name: /Fraunces/ }));
    expect(document.documentElement).toHaveAttribute("data-font", "b");
    expect(localStorage.getItem("pdt-font")).toBe("b");
    expect(screen.getByRole("radio", { name: /Fraunces/ })).toHaveAttribute("aria-checked", "true");
  });

  it("goes back to the default by dropping the attribute", async () => {
    render(<FontPicker />);
    await userEvent.click(screen.getByRole("radio", { name: /Manrope/ }));
    await userEvent.click(screen.getByRole("radio", { name: /Bricolage/ }));
    expect(document.documentElement).not.toHaveAttribute("data-font");
  });

  it("picks up a stored choice", () => {
    localStorage.setItem("pdt-font", "c");
    render(<FontPicker />);
    expect(screen.getByRole("radio", { name: /Space Grotesk/ })).toHaveAttribute("aria-checked", "true");
  });
});
