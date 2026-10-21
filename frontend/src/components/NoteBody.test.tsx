import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import NoteBody from "./NoteBody";

describe("NoteBody", () => {
  it("renders the body as Markdown, pictures of notr included", () => {
    render(
      <NoteBody
        note={{ title: "T", body: "Some **bold** words\n\n![chart](/api/notr/images/4)", created_at: "2026-10-19T09:00:00Z" }}
      />,
    );

    expect(screen.getByText("bold").tagName).toBe("STRONG");
    expect(screen.getByRole("img", { name: "chart" })).toHaveAttribute("src", "/api/notr/images/4");
  });
});
