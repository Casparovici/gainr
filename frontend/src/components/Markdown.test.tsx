import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Markdown from "./Markdown";

describe("Markdown", () => {
  it("renders headings, emphasis, lists, quotes and code", () => {
    render(
      <Markdown text={"# Title\n\nSome **bold**, *italic* and `code`.\n\n- one\n- two\n\n1. first\n\n> quoted\n\n```\nblock\n```"} />,
    );

    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(screen.getByText("bold").tagName).toBe("STRONG");
    expect(screen.getByText("italic").tagName).toBe("EM");
    expect(screen.getByText("code").tagName).toBe("CODE");
    expect(screen.getAllByRole("listitem").map((li) => li.textContent)).toEqual(["one", "two", "first"]);
    expect(screen.getByText("quoted")).toBeInTheDocument();
    expect(screen.getByText("block")).toBeInTheDocument();
  });

  it("renders a table", () => {
    render(<Markdown text={"| a | b |\n|---|--:|\n| 1 | 2 |"} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "b" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "2" })).toBeInTheDocument();
  });

  it("shows notr's own pictures, as a link to the full size", () => {
    render(<Markdown text="![the chart](/api/notr/images/12)" />);

    const image = screen.getByRole("img", { name: "the chart" });
    expect(image).toHaveAttribute("src", "/api/notr/images/12");
    expect(image).toHaveAttribute("loading", "lazy");
    expect(image.closest("a")).toHaveAttribute("href", "/api/notr/images/12");
  });

  it("leaves out a picture from anywhere else, keeping its description", () => {
    render(<Markdown text={"![tracker](https://evil.test/pixel.png)\n\n![](//evil.test/x.png)\n\n![local](/api/other.png)"} />);

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("tracker")).toBeInTheDocument();
    expect(screen.getByText("local")).toBeInTheDocument();
  });

  it("opens web links in a new tab without handing over the opener", () => {
    render(<Markdown text="[the filing](https://example.com/x)" />);

    const link = screen.getByRole("link", { name: "the filing" });
    expect(link).toHaveAttribute("href", "https://example.com/x");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("never makes a link of a script address", () => {
    render(<Markdown text={"[click](javascript:alert(1)) and [data](data:text/html,<b>x</b>)"} />);

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText(/click/)).toBeInTheDocument();
  });

  it("shows raw HTML as text instead of running it", () => {
    const { container } = render(<Markdown text={'<script>window.hacked = true</script><img src="x" onerror="window.hacked = true">'} />);

    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect((window as unknown as { hacked?: boolean }).hacked).toBeUndefined();
  });

  describe("checklists", () => {
    const text = "Plan\n\n- [ ] one\n- [x] two\n\n```\n- [ ] in code\n```\n\n- [ ] three";

    it("shows checkboxes, ticked or not, that can't be changed without a handler", () => {
      render(<Markdown text={text} />);

      const boxes = screen.getAllByRole("checkbox");
      expect(boxes.map((b) => (b as HTMLInputElement).checked)).toEqual([false, true, false]);
      expect(boxes.every((b) => (b as HTMLInputElement).disabled)).toBe(true);
    });

    it("reports which checkbox was ticked, counting the lines the server counts", async () => {
      const onToggle = vi.fn();
      render(<Markdown text={text} onToggleTask={onToggle} />);

      const boxes = screen.getAllByRole("checkbox");
      await userEvent.click(boxes[0]);
      await userEvent.click(boxes[1]);
      // The "- [ ] in code" line is a task line to the server (index 2), so "three" is index 3.
      await userEvent.click(boxes[2]);

      expect(onToggle.mock.calls).toEqual([[0, true], [1, false], [3, true]]);
    });
  });
});
