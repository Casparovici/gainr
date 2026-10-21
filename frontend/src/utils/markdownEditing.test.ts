import { describe, expect, it } from "vitest";

import { continueList, excerpt, firstImage, firstLine, insertBlock, prefixLines, taskLineNumbers, wrapSelection } from "./markdownEditing";

describe("wrapSelection", () => {
  it("wraps the selected text", () => {
    expect(wrapSelection("a big deal", 2, 5, "**")).toEqual({ value: "a **big** deal", start: 4, end: 7 });
  });

  it("takes the marks off a selection that is already wrapped", () => {
    expect(wrapSelection("a **big** deal", 4, 7, "**")).toEqual({ value: "a big deal", start: 2, end: 5 });
  });

  it("wraps a placeholder, selected, when nothing is selected", () => {
    expect(wrapSelection("x ", 2, 2, "**", "**", "bold")).toEqual({ value: "x **bold**", start: 4, end: 8 });
  });

  it("can wrap in different marks", () => {
    expect(wrapSelection("link", 0, 4, "[", "](https://)")).toEqual({ value: "[link](https://)", start: 1, end: 5 });
  });
});

describe("prefixLines", () => {
  it("prefixes the line the caret is on", () => {
    expect(prefixLines("one\ntwo", 5, 5, "- ")).toEqual({ value: "one\n- two", start: 7, end: 7 });
  });

  it("prefixes every line the selection touches", () => {
    expect(prefixLines("one\ntwo\nthree", 1, 6, "- ")).toEqual({ value: "- one\n- two\nthree", start: 0, end: 11 });
  });

  it("takes the prefix off again when every line has it", () => {
    expect(prefixLines("- one\n- two", 0, 11, "- ")).toEqual({ value: "one\ntwo", start: 0, end: 7 });
  });

  it("adds it to the lines that lack it when only some have it", () => {
    expect(prefixLines("- one\ntwo", 0, 9, "- ").value).toBe("- one\n- two");
  });

  it("doesn't touch the next line when the selection ends at a line break", () => {
    expect(prefixLines("one\ntwo", 0, 4, "> ").value).toBe("> one\ntwo");
  });
});

describe("insertBlock", () => {
  it("puts the text on a paragraph of its own", () => {
    expect(insertBlock("before after", 6, 6, "![](/x)")).toEqual({ value: "before\n\n![](/x)\n\nafter", start: 15, end: 15 });
  });

  it("adds only the blank lines that are missing", () => {
    expect(insertBlock("before\n\n", 8, 8, "P").value).toBe("before\n\nP\n");
    expect(insertBlock("", 0, 0, "P")).toEqual({ value: "P\n", start: 1, end: 1 });
  });

  it("replaces the selection", () => {
    expect(insertBlock("a [x] b", 2, 5, "P").value).toBe("a\n\nP\n\nb");
  });
});

describe("continueList", () => {
  it("starts the next bullet", () => {
    expect(continueList("- one", 5)).toEqual({ value: "- one\n- ", start: 8, end: 8 });
  });

  it("counts on in a numbered list", () => {
    expect(continueList("1. one", 6)?.value).toBe("1. one\n2. ");
    expect(continueList("9) nine", 7)?.value).toBe("9) nine\n10) ");
  });

  it("starts the next checklist item unticked", () => {
    expect(continueList("- [x] done", 10)?.value).toBe("- [x] done\n- [ ] ");
  });

  it("keeps the indent of a nested item", () => {
    expect(continueList("- a\n  - b", 9)?.value).toBe("- a\n  - b\n  - ");
  });

  it("ends the list on an empty item", () => {
    expect(continueList("- one\n- ", 8)).toEqual({ value: "- one\n", start: 6, end: 6 });
    expect(continueList("- [ ] ", 6)).toEqual({ value: "", start: 0, end: 0 });
  });

  it("leaves Enter alone anywhere else", () => {
    expect(continueList("plain text", 10)).toBeNull();
    expect(continueList("- one two", 5)).toBeNull(); // caret in the middle of the line
    expect(continueList("-not a list", 11)).toBeNull();
  });

  it("works on the line the caret is on, in the middle of a text", () => {
    expect(continueList("intro\n- one\noutro", 11)?.value).toBe("intro\n- one\n- \noutro");
  });
});

describe("taskLineNumbers", () => {
  it("lists the checkbox lines, nested and numbered ones too", () => {
    const body = "Plan\n\n- [ ] one\n- [x] two\n  - [ ] nested\n1. [ ] numbered\n- plain\n[ ] not a list\n";
    expect(taskLineNumbers(body)).toEqual([3, 4, 5, 6]);
  });
});

describe("firstLine and excerpt", () => {
  const body = "![chart](/api/notr/images/4)\n\n## Why I own it\n\nA **wide** moat, see [the filing](https://x.test).\n- [ ] check Q3";

  it("names an untitled note by its first line of words", () => {
    expect(firstLine(body)).toBe("Why I own it");
    expect(firstLine("")).toBe("");
    expect(firstLine("> quoted *words*")).toBe("quoted words");
  });

  it("reads as plain text, pictures left out", () => {
    expect(excerpt(body)).toBe("Why I own it · A wide moat, see the filing. · check Q3");
  });

  it("leaves tables out of an excerpt", () => {
    expect(excerpt("Costs\n\n| Task | Cost |\n|---|--:|\n| Pergola | 450 |\n\nDone")).toBe("Costs · Done");
  });

  it("is cut at the limit", () => {
    expect(excerpt("word ".repeat(100), 20)).toBe("word word word word…");
  });
});

describe("firstImage", () => {
  it("finds the first of the note's own pictures", () => {
    expect(firstImage("text ![a](/api/notr/images/12) ![b](/api/notr/images/3)")).toBe("/api/notr/images/12");
    expect(firstImage("![remote](https://x.test/a.png)")).toBeNull();
    expect(firstImage("")).toBeNull();
  });
});
