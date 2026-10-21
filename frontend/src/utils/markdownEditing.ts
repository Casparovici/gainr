// Pure text edits behind the Markdown editor's toolbar and Enter key: each takes the text and the
// selection and returns the new text and where the selection should be, so the component only has
// to apply the result (and every rule here is testable without a DOM).

export interface Edit {
  value: string;
  /** Selection after the edit; equal when it is just a caret. */
  start: number;
  end: number;
}

/** Wraps the selection in `before`/`after` (`**` around bold text), or takes them off again when
 * the selection is already wrapped. With nothing selected, `placeholder` is wrapped and selected,
 * so typing replaces it. */
export function wrapSelection(value: string, start: number, end: number, before: string, after = before, placeholder = ""): Edit {
  const selected = value.slice(start, end);
  const wrapped = value.slice(Math.max(0, start - before.length), start) === before && value.slice(end, end + after.length) === after;
  if (wrapped && selected) {
    return {
      value: value.slice(0, start - before.length) + selected + value.slice(end + after.length),
      start: start - before.length,
      end: end - before.length,
    };
  }
  const inner = selected || placeholder;
  return {
    value: value.slice(0, start) + before + inner + after + value.slice(end),
    start: start + before.length,
    end: start + before.length + inner.length,
  };
}

/** Puts `prefix` ("- ", "## ", "> ") at the start of every line the selection touches -- or takes
 * it off when they all have it already, so a toolbar button works as a toggle. */
export function prefixLines(value: string, start: number, end: number, prefix: string): Edit {
  const blockStart = value.lastIndexOf("\n", start - 1) + 1;
  // A selection that ends right after a line break doesn't touch the next line.
  const last = end > start && value[end - 1] === "\n" ? end - 1 : end;
  const found = value.indexOf("\n", last);
  const blockEnd = found === -1 ? value.length : found;
  const lines = value.slice(blockStart, blockEnd).split("\n");
  const allHave = lines.every((line) => line.startsWith(prefix));
  const changed = lines.map((line) => (allHave ? line.slice(prefix.length) : line.startsWith(prefix) ? line : prefix + line));
  const text = changed.join("\n");
  const collapsed = start === end;
  const delta = (allHave ? -1 : 1) * prefix.length;
  return {
    value: value.slice(0, blockStart) + text + value.slice(blockEnd),
    start: collapsed ? Math.max(blockStart, start + delta) : blockStart,
    end: collapsed ? Math.max(blockStart, end + delta) : blockStart + text.length,
  };
}

/** Inserts `text` as a paragraph of its own at the caret (or over the selection), with a blank
 * line between it and what's around it -- how a picture goes into a note. The caret ends up after
 * it. */
export function insertBlock(value: string, start: number, end: number, text: string): Edit {
  // Spaces next to the cut would end up as stray indentation on the lines either side.
  const before = value.slice(0, start).replace(/[ \t]+$/, "");
  const after = value.slice(end).replace(/^[ \t]+/, "");
  const lead = !before ? "" : before.endsWith("\n\n") ? "" : before.endsWith("\n") ? "\n" : "\n\n";
  const trail = !after ? "\n" : after.startsWith("\n\n") ? "" : after.startsWith("\n") ? "\n" : "\n\n";
  const inserted = lead + text + trail;
  const caret = before.length + lead.length + text.length;
  return { value: before + inserted + after, start: caret, end: caret };
}

const LIST_LINE = /^(\s*)([-*+]|(\d+)([.)]))\s+(\[[ xX]\]\s+)?(.*)$/;

/** What Enter does at the end of a list line: start the next item (numbered lists count on, a
 * checklist item starts unticked), or -- on an empty item -- end the list. Null when the caret is
 * not at the end of a list line, and Enter should do its usual thing. */
export function continueList(value: string, caret: number): Edit | null {
  const lineStart = value.lastIndexOf("\n", caret - 1) + 1;
  const found = value.indexOf("\n", caret);
  const lineEnd = found === -1 ? value.length : found;
  if (value.slice(caret, lineEnd).trim() !== "") return null;
  const match = LIST_LINE.exec(value.slice(lineStart, lineEnd));
  if (!match) return null;
  const [, indent, marker, number, delimiter, task, content] = match;
  if (content.trim() === "" ) {
    // An empty item: Enter ends the list.
    return { value: value.slice(0, lineStart) + value.slice(lineEnd), start: lineStart, end: lineStart };
  }
  const next = number ? `${Number(number) + 1}${delimiter}` : marker;
  const insert = `\n${indent}${next} ${task ? "[ ] " : ""}`;
  const at = lineEnd;
  return { value: value.slice(0, at) + insert + value.slice(at), start: at + insert.length, end: at + insert.length };
}

/** The `[ ]` / `[x]` lines of a Markdown text, as 1-based line numbers -- the same lines the server
 * counts when a checkbox is ticked, so a checkbox's position among them is its index. */
export const TASK_LINE = /^\s*(?:[-*+]|\d+[.)])\s+\[[ xX]\]\s/;

export function taskLineNumbers(body: string): number[] {
  const lines: number[] = [];
  body.split("\n").forEach((line, i) => {
    if (TASK_LINE.test(line)) lines.push(i + 1);
  });
  return lines;
}

/** The first line of a note that has some words in it, without its Markdown -- what an untitled
 * note is called in lists. */
export function firstLine(body: string): string {
  const line = body.split("\n").map((l) => l.trim()).find((l) => l && !/^!\[[^\]]*\]\([^)]*\)$/.test(l)) ?? "";
  return line
    .replace(/^(#{1,6}\s+|>\s*|[-*+]\s+(\[[ xX]\]\s+)?|\d+[.)]\s+)/, "")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[*_`~]/g, "")
    .trim();
}

/** The body as plain text for a card's excerpt: no pictures, no Markdown marks, lines joined. */
export function excerpt(body: string, max = 160): string {
  const text = body
    .split("\n")
    .map((l) => l.trim())
    // Pictures and tables read badly as a line of text, so a card leaves them out.
    .filter((l) => l && !/^!\[[^\]]*\]\([^)]*\)$/.test(l) && !l.startsWith("|"))
    .map((l) => l.replace(/^(#{1,6}\s+|>\s*|[-*+]\s+(\[[ xX]\]\s+)?|\d+[.)]\s+)/, ""))
    .join(" · ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[*_`~]/g, "");
  return text.length > max ? `${text.slice(0, max).trimEnd()}…` : text;
}

const IMAGE_REF = /!\[[^\]]*\]\((\/api\/notr\/images\/\d+)\)/;

/** The URL of the first picture in a note's body, for a card's thumbnail. */
export function firstImage(body: string): string | null {
  return IMAGE_REF.exec(body)?.[1] ?? null;
}
