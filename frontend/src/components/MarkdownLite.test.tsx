import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MarkdownLite from "./MarkdownLite";

describe("MarkdownLite", () => {
  it("renders a pipe table with its header, rows, inline marks and right-aligned numbers", () => {
    render(
      <MarkdownLite
        text={"Intro line\n\n| Holding | Price |\n|---|---:|\n| **ASML** | +2.10% |\n| NVDA | −1.00% |\n\nAfter"}
      />,
    );

    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Holding", "Price"]);
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByText("ASML").tagName).toBe("STRONG");
    expect(within(rows[1]).getByText("+2.10%")).toHaveClass("text-right");
    expect(screen.getByText("Intro line")).toBeInTheDocument();
    expect(screen.getByText("After")).toBeInTheDocument();
  });

  it("leaves lines with pipes but no separator row as text", () => {
    render(<MarkdownLite text={"| not | a table |\nstill text"} />);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("fills a short row with empty cells", () => {
    render(<MarkdownLite text={"| A | B |\n|---|---|\n| only a |"} />);
    expect(screen.getAllByRole("cell")).toHaveLength(2);
  });

  it("still renders headings, lists and paragraphs", () => {
    render(<MarkdownLite text={"## Title\n\n- one\n- two\n\n1. first\n\nplain *text*"} />);
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByText("text").tagName).toBe("EM");
  });
});
